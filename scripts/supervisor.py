#!/usr/bin/env python3
import os, sys, subprocess, csv, time, re, json
from datetime import datetime

WALL_DIR = os.path.expanduser("~/Downloads/courier_work/wall")
STATE_FILE = os.path.join(WALL_DIR, "state.tsv")
CLAIMS_DIR = os.path.join(WALL_DIR, "claims")
LOGS_DIR = os.path.join(WALL_DIR, "logs")
CONFIG_FILE = os.path.join(WALL_DIR, "supervisor_config.json")
PID_FILE = os.path.join(WALL_DIR, "supervisor.pid")
PROMPT_FILE = os.path.join(WALL_DIR, "master_prompt.txt")
QUEUE_SCRIPT = os.path.join(os.path.dirname(__file__), "work_queue.py")

for d in [WALL_DIR, CLAIMS_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"max_workers": 0}

def save_config(max_workers):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"max_workers": max_workers}, f, indent=2)

class CapacityGovernor:
    def __init__(self):
        self.state = "RAMPING"
        self.resource_health = "HEALTHY"
        self.last_metrics = None
        self.consecutive_memory_pressure = 0

    def get_real_metrics(self):
        m = {"mem_pressure_pct": 100.0}
        try:
            mp_out = subprocess.check_output("memory_pressure | grep 'System-wide memory free'", shell=True).decode()
            match = re.search(r'([\d]+)%', mp_out)
            if match: m["mem_pressure_pct"] = float(match.group(1))
        except: pass
        return m

    def evaluate(self, requested_max, active_count):
        curr = self.get_real_metrics()
        
        # Resource guard: memory pressure
        # if free memory pressure is below 15%, we are under pressure
        if curr["mem_pressure_pct"] < 15.0:
            self.consecutive_memory_pressure += 1
            self.state = "BACKOFF"
            self.resource_health = "CRITICAL"
            # Return current active or less, never increase during pressure
            return min(active_count, requested_max)
        else:
            self.consecutive_memory_pressure = 0
            self.state = "RAMPING"
            self.resource_health = "HEALTHY"
            # Can start up to requested max, but let's ramp up slowly or just return requested_max
            return requested_max

gov = CapacityGovernor()

def try_claim_task(slot_id):
    try:
        out = subprocess.check_output(["python3", QUEUE_SCRIPT, "claim", "--worker", slot_id]).decode()
        result = json.loads(out)
        if result.get("claimed"):
            return result["claimed"], ",".join(result.get("scopes", []))
    except:
        pass
    return None, None

def mark_task_complete(task_id, success=True):
    try:
        res = '{"status": "PASS"}' if success else '{"status": "FAIL"}'
        subprocess.check_output(["python3", QUEUE_SCRIPT, "complete", task_id, "--result-json", res, "--stage", "VERIFYING"])
    except:
        pass

def load_state():
    if not os.path.exists(STATE_FILE): return []
    with open(STATE_FILE, "r") as f:
        reader = csv.DictReader(f, delimiter='\t')
        return list(reader)

def save_state(rows):
    if not rows: return
    with open(STATE_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)

def initialize_slots(target_count):
    rows = load_state()
    existing_slots = {r["slot_id"]: r for r in rows}
    
    new_rows = []
    # We maintain up to 32 slots. Let's just create them if they don't exist.
    for i in range(1, 33):
        slot_id = f"MUSE-{i:02d}"
        if slot_id in existing_slots:
            new_rows.append(existing_slots[slot_id])
        else:
            new_rows.append({
                "slot_id": slot_id, "wid": "", "worker_type": "muse", "account_provider": "default",
                "task_id": "", "scope": "", "state": "IDLE", "claim_created_at": "",
                "pid": "", "pty": "", "proof_ref": "", "next_action": "start", "blocker": "",
                "crash_count": "0", "last_crash": "0", "updated_at": datetime.now().isoformat()
            })
    save_state(new_rows)
    return new_rows

def is_pid_running(pid):
    if not pid: return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False

def start_worker_process(slot_id, task_id, master_prompt):
    env = os.environ.copy()
    env["COURIER_TASK_ID"] = str(task_id)
    log_file = os.path.join(LOGS_DIR, f"{slot_id}.log")
    exit_file = os.path.join(LOGS_DIR, f"{slot_id}.exit")
    if os.path.exists(exit_file):
        try: os.remove(exit_file)
        except: pass

    f = open(log_file, "a")
    
    import shlex
    cmd = "muse --yolo"
    if master_prompt:
        cmd = f"muse --yolo {shlex.quote(master_prompt)}"
        
    cmd_full = f"({cmd}) ; echo $? > {shlex.quote(exit_file)}"
    p = subprocess.Popen(["bash", "-c", cmd_full], stdout=f, stderr=subprocess.STDOUT, env=env)
    return str(p.pid)

def supervise_loop():
    print(f"Starting Supervisor Loop (PID: {os.getpid()})")
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
        
    while True:
        cfg = load_config()
        requested_max = cfg.get("max_workers", 0)
        
        rows = initialize_slots(requested_max)
        changed = False
        
        # 1. Update states and detect exits
        active_count = 0
        for row in rows:
            if row["state"] == "WORKING":
                if is_pid_running(row["pid"]):
                    active_count += 1
                else:
                    # Exited!
                    exit_file = os.path.join(LOGS_DIR, f"{row['slot_id']}.exit")
                    exit_code = -1
                    if os.path.exists(exit_file):
                        try:
                            with open(exit_file, "r") as f:
                                exit_code = int(f.read().strip())
                        except: pass

                    if exit_code == 0:
                        # Normal exit
                        row["crash_count"] = "0"
                        row["state"] = "IDLE"
                    else:
                        # Crash
                        crash_count = int(row.get("crash_count", "0"))
                        row["crash_count"] = str(crash_count + 1)
                        row["last_crash"] = str(time.time())
                        row["state"] = "BACKOFF"
                    
                    row["pid"] = ""
                    row["task_id"] = ""
                    changed = True
            elif row["state"] == "BACKOFF":
                last_crash = float(row.get("last_crash", "0"))
                crash_count = int(row.get("crash_count", "0"))
                backoff_time = min(300, 2 ** crash_count)
                if time.time() - last_crash > backoff_time:
                    row["state"] = "IDLE"
                    changed = True

        admitted = gov.evaluate(requested_max, active_count)
        
        # Read master prompt
        master_prompt = ""
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, "r") as f:
                master_prompt = f.read().strip()
                
        # 2. Start new tasks if under capacity
        if active_count < admitted:
            for row in rows:
                if active_count >= admitted: break
                if row["state"] == "IDLE":
                    # Check duplicate process guard just in case
                    if row["pid"] and is_pid_running(row["pid"]):
                        row["state"] = "WORKING"
                        active_count += 1
                        changed = True
                        continue

                    task_id, scope = try_claim_task(row["slot_id"])
                    if task_id:
                        pid = start_worker_process(row["slot_id"], task_id, master_prompt)
                        row["pid"] = pid
                        row["state"] = "WORKING"
                        row["task_id"] = task_id
                        row["scope"] = scope
                        row["crash_count"] = "0" # reset on successful start
                        active_count += 1
                        changed = True
                        
        if changed:
            save_state(rows)
            
        time.sleep(2)

def status():
    rows = load_state()
    cfg = load_config()
    requested_max = cfg.get("max_workers", 0)
    print("=== SUPERVISOR STATUS ===")
    print(f"Target Workers: {requested_max}")
    print(f"Resource Guard: {gov.resource_health} (State: {gov.state})")
    print("---")
    active = 0
    for r in rows:
        if r["state"] == "WORKING":
            active += 1
        if r["state"] != "IDLE" or requested_max > 0:
            print(f"{r['slot_id']:<10} | {r['state']:<10} | PID: {r['pid']:<6} | Task: {r['task_id']}")
    print(f"Active Slots: {active}/{requested_max}")

def stop_supervisor():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            pid = f.read().strip()
        if is_pid_running(pid):
            os.kill(int(pid), 15)
            print(f"Killed supervisor (PID {pid})")
    
    # Kill workers
    rows = load_state()
    for row in rows:
        if row["pid"] and is_pid_running(row["pid"]):
            os.kill(int(row["pid"]), 15)
            print(f"Killed slot {row['slot_id']} (PID {row['pid']})")
            row["pid"] = ""
            row["state"] = "IDLE"
    save_state(rows)
    save_config(0)
    print("Supervisor and all slots stopped.")

def main():
    if len(sys.argv) < 2:
        print("Commands: start <N>, status, stop, daemon")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "start":
        if len(sys.argv) < 3:
            print("Usage: start <N>")
            sys.exit(1)
        n = int(sys.argv[2])
        save_config(n)
        print(f"Set target workers to {n}.")
        
        # Ensure daemon is running
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                pid = f.read().strip()
            if is_pid_running(pid):
                print(f"Supervisor already running (PID {pid}).")
                return
                
        print("Starting supervisor daemon...")
        subprocess.Popen(["python3", os.path.abspath(__file__), "daemon"], 
                         stdout=open(os.path.join(LOGS_DIR, "supervisor.log"), "a"),
                         stderr=subprocess.STDOUT)
    elif cmd == "status":
        status()
    elif cmd == "stop":
        stop_supervisor()
    elif cmd == "daemon":
        supervise_loop()

if __name__ == "__main__":
    main()
