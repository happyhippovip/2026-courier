"""Safe stop for Windows worker — uses the lock file PID, not broad process matching.

Reads the lock file to find the exact PID of the running daemon, verifies
process identity (PID + create_time), and terminates only that process tree.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import psutil


def find_lock_file(worker_id):
    """Find the daemon lock file for the given worker ID."""
    return Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"


def read_lock_pid(lock_path):
    """Read PID from lock file (supports both plain-PID and structured JSON)."""
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, None

    try:
        pid = int(raw)
        return pid, None
    except ValueError:
        pass

    try:
        meta = json.loads(raw)
        return int(meta["pid"]), meta.get("process_create_time")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None, None


def stop_worker(worker_id=None):
    """Stop the daemon identified by lock file. Returns True if stopped."""
    if worker_id is None:
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                cfg = json.load(f)
            worker_id = cfg.get("WORKER_ID", "default-win-worker")
        else:
            worker_id = "default-win-worker"

    lock_path = find_lock_file(worker_id)
    if not lock_path.exists():
        print(f"[{worker_id}] No lock file found — daemon is not running.")
        return False

    pid, create_time = read_lock_pid(lock_path)
    if pid is None:
        print(f"[{worker_id}] Lock file unreadable.")
        return False

    # Verify process identity
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[{worker_id}] PID {pid} no longer exists. Cleaning stale lock.")
        lock_path.unlink(missing_ok=True)
        return False

    if create_time is not None:
        try:
            actual = proc.create_time()
            if abs(actual - float(create_time)) > 1.0:
                print(f"[{worker_id}] PID {pid} reused by different process. Cleaning stale lock.")
                lock_path.unlink(missing_ok=True)
                return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Terminate the exact process tree
    print(f"[{worker_id}] Stopping daemon PID {pid}...")
    try:
        children = proc.children(recursive=True)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except psutil.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                pass
        # Clean up children that didn't die with parent
        for child in children:
            try:
                if child.is_running():
                    child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except psutil.NoSuchProcess:
        pass  # Already gone

    # Clean lock
    lock_path.unlink(missing_ok=True)
    print(f"[{worker_id}] Daemon stopped.")
    return True


if __name__ == "__main__":
    worker_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    stopped = stop_worker(worker_id_arg)
    sys.exit(0 if stopped else 1)
