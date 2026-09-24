import subprocess
import json
import os
import time
from datetime import datetime

INVENTORY_FILE = os.path.expanduser("~/Downloads/courier_work/wall/pty_inventory.json")

def get_system_metrics():
    # RAM and Swap
    vm_stat = subprocess.check_output(["vm_stat"]).decode()
    pages_free = 0
    pages_active = 0
    for line in vm_stat.split('\n'):
        if "Pages free" in line:
            pages_free = int(line.split(':')[1].strip().strip('.'))
        elif "Pages active" in line:
            pages_active = int(line.split(':')[1].strip().strip('.'))
    
    # WindowServer CPU
    try:
        ps_ws = subprocess.check_output(["ps", "-A", "-o", "%cpu,command"]).decode()
        ws_cpu = sum(float(line.strip().split()[0]) for line in ps_ws.split('\n') if "WindowServer" in line)
    except:
        ws_cpu = 0.0

    return {
        "pages_free": pages_free,
        "pages_active": pages_active,
        "window_server_cpu_pct": ws_cpu
    }

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
    with open(INVENTORY_FILE, "w") as f:
        json.dump(slots, f, indent=2)
    return slots

def start_canary(slot_id, cmd):
    print(f"Starting CANARY {slot_id} in background screen...")
    subprocess.run(["screen", "-dmS", slot_id, "bash", "-c", f"{cmd}; exec bash"])
    time.sleep(1)
    
    # Find PID
    try:
        out = subprocess.check_output(["screen", "-ls"]).decode()
    except subprocess.CalledProcessError as e:
        out = e.output.decode() if e.output else ""
        
    pid = None
    for line in out.split('\n'):
        if f".{slot_id}" in line:
            pid = line.strip().split('\t')[0].strip()
            if pid.startswith('.'): pid = pid[1:] # if something is weird
            if '.' in pid:
                pid = pid.split('.')[0]
            break
            
    if pid:
        # Find child TTY
        try:
            ps_out = subprocess.check_output(["ps", "-ax", "-o", "pid,ppid,tty"]).decode()
        except:
            ps_out = ""
        tty = None
        for line in ps_out.split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[1] == pid:
                tty = parts[2]
                break
        return pid, tty
    return None, None

def main():
    print("Capturing baseline metrics...")
    baseline = get_system_metrics()
    print(json.dumps(baseline, indent=2))
    
    os.makedirs(os.path.dirname(INVENTORY_FILE), exist_ok=True)
    if not os.path.exists(INVENTORY_FILE):
        inv = init_inventory()
    else:
        with open(INVENTORY_FILE, "r") as f:
            inv = json.load(f)
            
    # Clean old CANARY sessions if any
    subprocess.run("screen -ls | grep -E 'MUSE-01|CLI-01' | awk '{print $1}' | xargs -I % screen -S % -X quit", shell=True, stderr=subprocess.DEVNULL)
    
    test_slots = {
        "MUSE-01": "echo 'MUSE CANARY' && sleep 100", 
        "CLI-01": "echo 'CLI CANARY' && sleep 100"
    }
    
    for slot_id, cmd in test_slots.items():
        pid, tty = start_canary(slot_id, cmd)
        inv[slot_id]["pid"] = pid
        inv[slot_id]["tty"] = tty
        inv[slot_id]["state"] = "WORKING"
        inv[slot_id]["updated_at"] = datetime.now().isoformat()
            
    with open(INVENTORY_FILE, "w") as f:
        json.dump(inv, f, indent=2)
        
    print("Capturing post-canary metrics...")
    post = get_system_metrics()
    print(json.dumps(post, indent=2))
    
    print("Canary setup complete. Check inventory:")
    print(json.dumps({k:v for k,v in inv.items() if v["state"] != "IDLE"}, indent=2))

if __name__ == "__main__":
    main()
