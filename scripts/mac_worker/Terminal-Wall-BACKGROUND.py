#!/usr/bin/env python3
import os, sys, subprocess, json, time
from datetime import datetime

INVENTORY_FILE = os.path.expanduser("~/Downloads/courier_work/wall/pty_inventory.json")

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

def init_inventory():
    slots = {}
    for i in range(1, 65):
        slots[f"MUSE-{i:02d}"] = {
            "slot_id": f"MUSE-{i:02d}", "provider_account": "default", "pid": None, "tty": None,
            "task_id": None, "scope": "courier", "state": "IDLE", "updated_at": datetime.now().isoformat(),
            "proof_ref": None, "next_action": "start", "blocker": None
        }
    for i in range(1, 10):
        slots[f"CLI-{i:02d}"] = {
            "slot_id": f"CLI-{i:02d}", "provider_account": "default", "pid": None, "tty": None,
            "task_id": None, "scope": "courier", "state": "IDLE", "updated_at": datetime.now().isoformat(),
            "proof_ref": None, "next_action": "start", "blocker": None
        }
    return slots

def get_slot_command(slot_id):
    if slot_id.startswith("MUSE"):
        return "muse --yolo"
    elif slot_id.startswith("CLI"):
        return "HOME=/Users/user/.gemini_alt agy"
    return "echo 'Unknown'"

def ramp_up(count):
    if not os.path.exists(INVENTORY_FILE):
        inv = init_inventory()
    else:
        with open(INVENTORY_FILE, "r") as f:
            inv = json.load(f)
            
    launched = 0
    for slot_id, data in inv.items():
        if launched >= count:
            break
        if data["state"] == "IDLE":
            cmd = get_slot_command(slot_id)
            pid, tty = start_screen_session(slot_id, cmd)
            if pid:
                data["pid"] = pid
                data["tty"] = tty
                data["state"] = "WORKING"
                data["updated_at"] = datetime.now().isoformat()
                launched += 1
                
    with open(INVENTORY_FILE, "w") as f:
        json.dump(inv, f, indent=2)
        
    print(f"Ramp up complete: started {launched} new worker slots.")

def main():
    if len(sys.argv) < 2:
        print("Usage: Terminal-Wall-BACKGROUND.py [ramp <count> | status | attach <slot>]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "ramp":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        ramp_up(count)
    elif cmd == "status":
        if os.path.exists(INVENTORY_FILE):
            with open(INVENTORY_FILE, "r") as f:
                inv = json.load(f)
            active = {k: v for k, v in inv.items() if v["state"] != "IDLE"}
            print(f"Active Slots ({len(active)}/73):")
            for k, v in active.items():
                print(f"  {k} -> PID: {v['pid']}, TTY: {v['tty']}, Task: {v['task_id']}, Status: {v['state']}")
    elif cmd == "attach":
        slot = sys.argv[2]
        print(f"Attaching to {slot}... (Press Ctrl+A, D to detach again)")
        os.execvp("screen", ["screen", "-r", slot])
        
if __name__ == "__main__":
    main()
