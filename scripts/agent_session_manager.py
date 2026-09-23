import json
import os
import subprocess
import signal
import time
from pathlib import Path
import sys

REGISTRY_FILE = Path(".agents/state/background_monitors.json")

def _load():
    if not REGISTRY_FILE.exists():
        return {}
    try:
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data):
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_process_info(pid):
    if sys.platform == "win32":
        try:
            import psutil
            p = psutil.Process(pid)
            return f"{p.create_time()} {' '.join(p.cmdline())}"
        except Exception:
            return None
    try:
        # Get start time and command line
        out = subprocess.check_output(["ps", "-p", str(pid), "-o", "lstart=,args="], stderr=subprocess.DEVNULL).decode().strip()
        if not out:
            return None
        return out
    except subprocess.CalledProcessError:
        return None

def register_task(pid, owner, purpose):
    data = _load()
    if owner not in data:
        data[owner] = []
    
    info = get_process_info(pid)
    if not info:
        return False
        
    data[owner].append({
        "pid": pid,
        "purpose": purpose,
        "proc_info": info
    })
    _save(data)
    return True

def kill_pid(pid):
    try:
        if sys.platform == "win32":
            import psutil
            try:
                p = psutil.Process(pid)
                p.kill()
                p.wait(timeout=3)
                return True
            except psutil.NoSuchProcess:
                return True
            except Exception:
                return False
        
        os.kill(pid, signal.SIGTERM)
        for _ in range(30): # 3 seconds
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                return True
        os.kill(pid, signal.SIGKILL)
        return True
    except OSError:
        return False

def cleanup_session(owner):
    data = _load()
    if owner not in data:
        return 0
    
    killed_count = 0
    for task in data[owner]:
        pid = task["pid"]
        info = get_process_info(pid)
        # Verify it's the exact same process (start time matches)
        if info and info == task.get("proc_info"):
            if kill_pid(pid):
                killed_count += 1
            
    del data[owner]
    _save(data)
    return killed_count

def audit_orphans():
    """Removes dead processes from the registry without killing active ones."""
    data = _load()
    changed = False
    for owner, tasks in list(data.items()):
        alive_tasks = []
        for task in tasks:
            pid = task["pid"]
            info = get_process_info(pid)
            if info and info == task.get("proc_info"):
                alive_tasks.append(task)
            else:
                changed = True
        
        if alive_tasks:
            data[owner] = alive_tasks
        else:
            del data[owner]
            changed = True
            
    if changed:
        _save(data)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python agent_session_manager.py [register|cleanup|audit] ...")
        sys.exit(1)
        
    action = sys.argv[1]
    if action == "register" and len(sys.argv) == 5:
        pid = int(sys.argv[2])
        owner = sys.argv[3]
        purpose = sys.argv[4]
        if register_task(pid, owner, purpose):
            print(f"Registered {pid} to {owner}")
        else:
            print("Process not found")
    elif action == "cleanup" and len(sys.argv) == 3:
        owner = sys.argv[2]
        killed = cleanup_session(owner)
        print(f"Killed {killed} tasks for {owner}")
    elif action == "audit":
        audit_orphans()
        print("Audit complete")
