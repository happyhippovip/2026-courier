#!/usr/bin/env python3
import os, sys, subprocess, csv, time
from datetime import datetime

STATE_FILE = os.path.expanduser("~/Downloads/courier_work/wall/state.tsv")
CLAIMS_DIR = os.path.expanduser("~/Downloads/courier_work/wall/claims")
LEDGER_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "agent_handoff_ledger.json")

def start_screen_session(slot_id, cmd):
    print(f"[{slot_id}] Starting in background mode...")
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
    if not os.path.exists(STATE_FILE):
        return []
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
    if slot_id.startswith("MUSE"):
        return "muse --yolo"
    elif slot_id.startswith("CLI"):
        return "HOME=/Users/user/.gemini_alt agy"
    return "echo 'Unknown'"

def ramp_up(count):
    rows = load_state()
    launched = 0
    
    for row in rows:
        if launched >= count:
            break
        if row["state"] == "IDLE":
            slot_id = row["slot_id"]
            cmd = get_slot_command(slot_id)
            pid, tty = start_screen_session(slot_id, cmd)
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
    print(f"Ramp up complete: started {launched} new worker slots.")

def verify_proof(proof_ref):
    # Micro-verification: check deterministic proof file existence
    if not proof_ref: return False
    return os.path.exists(proof_ref)

def supervise_loop(run_once=False):
    print("Starting Supervisor Loop...")
    while True:
        rows = load_state()
        changed = False
        
        for row in rows:
            if row["state"] == "WORKING":
                # Check if process is still alive
                if row["pid"]:
                    try:
                        os.kill(int(row["pid"]), 0)
                    except OSError:
                        row["state"] = "IDLE"
                        changed = True
                        
            elif row["state"] == "RESULT_READY":
                print(f"[{row['slot_id']}] RESULT_READY. Verifying proof_ref: {row['proof_ref']}")
                if verify_proof(row["proof_ref"]):
                    print(f"[{row['slot_id']}] PROOF PASS! Dispatching next task.")
                    row["state"] = "WORKING"
                    row["next_action"] = "start_next_task"
                    row["proof_ref"] = ""
                    row["updated_at"] = datetime.now().isoformat()
                    changed = True
                else:
                    print(f"[{row['slot_id']}] PROOF FAILED/MISSING.")
                    row["state"] = "BLOCKED"
                    row["blocker"] = "missing_deterministic_proof"
                    row["updated_at"] = datetime.now().isoformat()
                    changed = True
                    
        if changed:
            save_state(rows)
            
        if run_once:
            break
        time.sleep(5)

def main():
    if len(sys.argv) < 2:
        print("Usage: Terminal-Wall-BACKGROUND.py [ramp <count> | status | attach <slot> | supervise]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "ramp":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        ramp_up(count)
    elif cmd == "status":
        rows = load_state()
        active = [r for r in rows if r["state"] != "IDLE"]
        print(f"Active Slots ({len(active)}/73):")
        for r in active:
            print(f"  {r['slot_id']} -> PID: {r['pid']}, TTY: {r['tty/pty']}, Status: {r['state']}")
    elif cmd == "attach":
        slot = sys.argv[2]
        print(f"Attaching to {slot}... (Press Ctrl+A, D to detach again)")
        os.execvp("screen", ["screen", "-r", slot])
    elif cmd == "supervise":
        supervise_loop(run_once=("--once" in sys.argv))
        
if __name__ == "__main__":
    main()
