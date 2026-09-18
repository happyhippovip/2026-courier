import os, json, sys, tempfile, time
from pathlib import Path
import psutil
from status import get_pid

def stop_worker():
    config_path = Path(__file__).parent / "config.json"
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    worker_id = os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker")
    lock_file = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"

    pid = get_pid()
    if pid:
        print(f"Stopping Courier Windows Worker (PID: {pid})...")
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            try:
                parent.terminate()
            except psutil.NoSuchProcess:
                pass
            
            gone, alive = psutil.wait_procs(children + [parent], timeout=5)
            for p in alive:
                p.kill()
            print("Stopped.")
        except psutil.NoSuchProcess:
            print("Process already gone.")
        except Exception as e:
            print(f"Failed to stop: {e}")
            
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass
    else:
        print("Windows Worker is not running.")
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass

if __name__ == "__main__":
    stop_worker()
