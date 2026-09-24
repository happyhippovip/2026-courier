#!/usr/bin/env python3
import os, sys, subprocess, csv, time
from datetime import datetime

STATE_FILE = os.path.expanduser("~/Downloads/courier_work/wall/state.tsv")
CLAIMS_DIR = os.path.expanduser("~/Downloads/courier_work/wall/claims")

def start_screen_session(slot_id, cmd):
    subprocess.run(["screen", "-dmS", slot_id, "bash", "-c", f"{cmd}"])
    time.sleep(1)
    
    try:
        out = subprocess.check_output(["screen", "-ls"]).decode()
    except subprocess.CalledProcessError as e:
        out = e.output.decode() if e.output else ""
        
    pid = None
    for line in out.split('\n'):
        if f".{slot_id}" in line:
            pid = line.strip().split('\t')[0].strip()
            if pid.startswith('.'): pid = pid[1:]
            if '.' in pid: pid = pid.split('.')[0]
            break
            
    tty = None
    if pid:
        try:
            ps_out = subprocess.check_output(["ps", "-ax", "-o", "pid,ppid,tty"]).decode()
        except:
            ps_out = ""
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

def ramp_up(count):
    rows = load_state()
    launched = 0
    for row in rows:
        if launched >= count: break
        if row["state"] == "IDLE":
            slot_id = row["slot_id"]
            pid, tty = start_screen_session(slot_id, get_slot_command(slot_id))
            if pid:
                row["pid"] = pid
                row["tty/pty"] = tty
                row["state"] = "WORKING"
                row["updated_at"] = datetime.now().isoformat()
                claim_path = os.path.join(CLAIMS_DIR, slot_id)
                os.makedirs(claim_path, exist_ok=True)
                with open(os.path.join(claim_path, "owner.txt"), "w") as f:
                    f.write(f"session:{slot_id}\npid:{pid}\n")
                launched += 1
    save_state(rows)

def verify_proof(proof_ref):
    return os.path.exists(proof_ref) if proof_ref else False

def supervise_loop(run_once=False):
    while True:
        rows = load_state()
        changed = False
        for row in rows:
            if row["state"] == "WORKING" and row["pid"]:
                try: os.kill(int(row["pid"]), 0)
                except OSError:
                    row["state"] = "IDLE"
                    changed = True
            elif row["state"] == "RESULT_READY":
                if verify_proof(row["proof_ref"]):
                    row["state"], row["next_action"], row["proof_ref"] = "WORKING", "start_next_task", ""
                else:
                    row["state"], row["blocker"] = "BLOCKED", "missing_deterministic_proof"
                row["updated_at"] = datetime.now().isoformat()
                changed = True
        if changed: save_state(rows)
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

def main():
    if len(sys.argv) < 2: sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "ramp": ramp_up(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    elif cmd == "dashboard": show_dashboard()
    elif cmd == "attach": os.execvp("screen", ["screen", "-r", sys.argv[2]])
    elif cmd == "supervise": supervise_loop(run_once=("--once" in sys.argv))

if __name__ == "__main__": main()
