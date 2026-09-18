import os, json, sys, tempfile
from pathlib import Path

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
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            return pid
        except (OSError, ProcessLookupError):
            return None
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
