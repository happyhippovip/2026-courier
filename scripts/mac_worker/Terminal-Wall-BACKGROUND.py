#!/usr/bin/env python3
import os, sys, subprocess, csv, time, re
from datetime import datetime

STATE_FILE = os.path.expanduser("~/Downloads/courier_work/wall/state.tsv")
CLAIMS_DIR = os.path.expanduser("~/Downloads/courier_work/wall/claims")

class CapacityGovernor:
    def __init__(self, desired_capacity=73, start_capacity=4):
        self.desired_capacity = desired_capacity
        self.admitted_capacity = start_capacity
        self.state = "RAMPING"
        self.last_metrics = None
        self.timeout_count = 0
        
    def get_real_metrics(self):
        m = {"swap_mb": 0.0, "load_1m": 0.0, "free_pages": 0, "ws_cpu": 0.0, "term_cpu": 0.0, "worker_rss_mb": 0.0, "active_procs": 0, "mem_pressure_pct": 100.0, "sys_latency_ms": 0.0}
        
        try:
            # Swap
            swap_out = subprocess.check_output(["sysctl", "vm.swapusage"]).decode()
            match = re.search(r'used = ([\d\.]+)M', swap_out)
            if match: m["swap_mb"] = float(match.group(1))
            
            # Load avg
            load_out = subprocess.check_output(["sysctl", "vm.loadavg"]).decode()
            m["load_1m"] = float(re.findall(r'[\d\.]+', load_out)[0])
            
            # Memory pressure / free pages
            vmstat = subprocess.check_output(["vm_stat"]).decode()
            for line in vmstat.split('\n'):
                if "Pages free" in line:
                    m["free_pages"] = int(line.split(':')[1].strip().strip('.'))
                    
            try:
                mp_out = subprocess.check_output("memory_pressure | grep 'System-wide memory free'", shell=True).decode()
                mp_match = re.search(r'([\d]+)%', mp_out)
                if mp_match: m["mem_pressure_pct"] = float(mp_match.group(1))
            except: pass
            
            # Process & App Metrics (WindowServer, Terminal, Workers)
            ps_out = subprocess.check_output(["ps", "-A", "-o", "%cpu,rss,command"]).decode()
            procs = ps_out.strip().split('\n')
            m["active_procs"] = len(procs)
            
            for line in procs:
                parts = line.strip().split(maxsplit=2)
                if len(parts) < 3: continue
                cpu, rss, cmd = float(parts[0]), float(parts[1])/1024.0, parts[2]
                
                if "WindowServer" in cmd: m["ws_cpu"] += cpu
                if "Terminal.app" in cmd: m["term_cpu"] += cpu
                if "muse --yolo" in cmd or "agy" in cmd: m["worker_rss_mb"] += rss
                
            # System Latency (ping localhost)
            t0 = time.time()
            subprocess.run(["ping", "-c", "1", "-t", "1", "127.0.0.1"], stdout=subprocess.DEVNULL)
            m["sys_latency_ms"] = (time.time() - t0) * 1000.0
            
        except Exception as e:
            print(f"Metric collection error: {e}")
            
        return m
            
    def evaluate(self):
        curr = self.get_real_metrics()
        if self.last_metrics:
            d_swap = curr["swap_mb"] - self.last_metrics["swap_mb"]
            d_ws = curr["ws_cpu"] - self.last_metrics["ws_cpu"]
            d_lat = curr["sys_latency_ms"] - self.last_metrics["sys_latency_ms"]
            
            # Evaluate Backoff conditions (Critical)
            if d_swap > 500 or curr["load_1m"] > 10.0 or curr["mem_pressure_pct"] < 10.0 or curr["sys_latency_ms"] > 1000.0 or self.timeout_count > 3:
                self.state = "BACKOFF"
                self.admitted_capacity = max(4, self.admitted_capacity - 4)
                self.timeout_count = 0 # reset after handling
            # Evaluate Hold conditions (Stressed)
            elif d_swap > 100 or curr["load_1m"] > 5.0 or curr["ws_cpu"] > 60.0 or d_ws > 20.0 or d_lat > 100.0:
                self.state = "HOLD"
            # Stable scale up
            else:
                self.state = "RAMPING"
                if self.admitted_capacity < self.desired_capacity:
                    self.admitted_capacity = min(self.desired_capacity, self.admitted_capacity * 2)
                    
        self.last_metrics = curr
        return self.admitted_capacity

gov = CapacityGovernor(desired_capacity=73, start_capacity=4)

def start_screen_session(slot_id, cmd):
    subprocess.run(["screen", "-dmS", slot_id, "bash", "-c", f"{cmd}"])
    time.sleep(1)
    try: out = subprocess.check_output(["screen", "-ls"]).decode()
    except subprocess.CalledProcessError as e: out = e.output.decode() if e.output else ""
    pid = None
    for line in out.split('\n'):
        if f".{slot_id}" in line:
            pid = line.strip().split('\t')[0].strip()
            if pid.startswith('.'): pid = pid[1:]
            if '.' in pid: pid = pid.split('.')[0]
            break
    tty = None
    if pid:
        try: ps_out = subprocess.check_output(["ps", "-ax", "-o", "pid,ppid,tty"]).decode()
        except: ps_out = ""
        for line in ps_out.split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[1] == pid:
                tty = parts[2]
                break
    return pid, tty

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

def get_slot_command(slot_id):
    return "muse --yolo" if slot_id.startswith("MUSE") else "HOME=/Users/user/.gemini_alt agy"

def verify_proof(proof_ref):
    return os.path.exists(proof_ref) if proof_ref else False

def supervise_loop(run_once=False, canary_mode=False):
    print("Starting Central Supervisor Loop (with Adaptive Governor)...")
    while True:
        rows = load_state()
        changed = False
        admitted = gov.evaluate()
        active_count = len([r for r in rows if r["state"] == "WORKING"])
        
        for row in rows:
            if row["state"] == "WORKING" and row["pid"]:
                try: os.kill(int(row["pid"]), 0)
                except OSError:
                    row["state"], row["pid"], row["tty/pty"] = "IDLE", "", ""
                    changed = True
            elif row["state"] == "RESULT_READY":
                if verify_proof(row["proof_ref"]):
                    row["state"], row["next_action"], row["proof_ref"] = "WORKING", "start_next_task", ""
                else:
                    row["state"], row["blocker"] = "BLOCKED", "missing_deterministic_proof"
                    gov.timeout_count += 1
                row["updated_at"] = datetime.now().isoformat()
                changed = True
                
        if active_count < admitted and gov.state != "BACKOFF":
            for row in rows:
                if active_count >= admitted: break
                if row["state"] == "IDLE":
                    slot_id = row["slot_id"]
                    if not canary_mode: pid, tty = start_screen_session(slot_id, get_slot_command(slot_id))
                    else: pid, tty = "CANARY_PID", "CANARY_TTY"
                    if pid:
                        row["pid"], row["tty/pty"], row["state"] = pid, tty, "WORKING"
                        row["updated_at"] = datetime.now().isoformat()
                        claim_path = os.path.join(CLAIMS_DIR, slot_id)
                        os.makedirs(claim_path, exist_ok=True)
                        with open(os.path.join(claim_path, "owner.txt"), "w") as f:
                            f.write(f"session:{slot_id}\npid:{pid}\n")
                        active_count += 1
                        changed = True

        if changed: save_state(rows)
        print(f"[GOVERNOR] Active: {active_count} | Admitted: {admitted} | State: {gov.state}")
        if run_once: break
        time.sleep(5)

def show_dashboard():
    print("\033[2J\033[H=== COURIER 73-WORKER ZENTRALE ===")
    rows = load_state()
    if not rows: return
    stats = {"WORKING": 0, "VERIFYING": 0, "WAITING": 0, "BLOCKED": 0, "DONE": 0, "IDLE": 0, "RESULT_READY": 0}
    for i, row in enumerate(rows):
        state = row['state']
        if state in stats: stats[state] += 1
        col = "\033[92m" if state=="WORKING" else "\033[91m" if state=="BLOCKED" else "\033[90m" if state=="IDLE" else "\033[93m" if state in ["RESULT_READY","VERIFYING"] else "\033[0m"
        print(f"{col}{row['slot_id']}:{state[:3]:<4}\033[0m", end="")
        if (i + 1) % 8 == 0: print()
    print("\n\n=== METRICS ===")
    print(" | ".join(f"{k}: {v}" for k, v in stats.items()))
    print(f"ADMITTED_CAPACITY: {gov.admitted_capacity} / {gov.desired_capacity} [{gov.state}]")

def main():
    if len(sys.argv) < 2: sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "dashboard": show_dashboard()
    elif cmd == "attach": os.execvp("screen", ["screen", "-r", sys.argv[2]])
    elif cmd == "supervise": supervise_loop(run_once=("--once" in sys.argv))
    elif cmd == "canary": supervise_loop(run_once=("--once" in sys.argv), canary_mode=True)

if __name__ == "__main__": main()
