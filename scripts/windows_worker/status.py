import os, json, sys, tempfile
from pathlib import Path
import psutil

def get_pid():
    config_path = Path(__file__).parent / "config.json"
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    worker_id = os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker")
    lock_file = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
    
    if not lock_file.exists():
        return None
        
    try:
        with open(lock_file, "r") as f:
            data = f.read().strip()
            if not data: return None
            
        try:
            lock_data = json.loads(data)
            pid = lock_data["pid"]
            create_time = lock_data.get("process_create_time")
            exe = lock_data.get("executable")
            daemon_path = lock_data.get("daemon_path")
        except ValueError:
            pid = int(data)
            create_time = None
            exe = None
            daemon_path = None

        try:
            p = psutil.Process(pid)
            if create_time is not None:
                if abs(p.create_time() - create_time) > 0.1:
                    return None
            if exe is not None:
                try:
                    if p.exe() != exe and os.path.basename(p.exe()) != os.path.basename(exe):
                        pass # sometimes path might differ slightly on mac/win, but we could enforce it
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            return pid
        except psutil.NoSuchProcess:
            return None
    except Exception:
        return None

def get_lock_data():
    config_path = Path(__file__).parent / "config.json"
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    worker_id = os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker")
    lock_file = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
    if not lock_file.exists(): return None
    try:
        with open(lock_file, "r") as f:
            return json.loads(f.read().strip())
    except Exception:
        return None

if __name__ == "__main__":
    pid = get_pid()
    if pid:
        print(f"Windows Worker HTTP Daemon is RUNNING (PID: {pid})")
        sys.exit(0)
    else:
        print("Windows Worker HTTP Daemon is NOT RUNNING.")
        sys.exit(1)
