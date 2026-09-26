"""Worker status: reports daemon health, lock state, and queue statistics.

Safe read-only check — never modifies state.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import psutil


def worker_status(worker_id=None):
    """Return a dict describing the current worker state."""
    worker_dir = Path(__file__).parent
    config_path = worker_dir / "config.json"
    state_dir = worker_dir / "state"

    if worker_id is None:
        if config_path.exists():
            with open(config_path, "r") as f:
                cfg = json.load(f)
            worker_id = cfg.get("WORKER_ID", "default-win-worker")
        else:
            worker_id = "default-win-worker"

    status = {
        "worker_id": worker_id,
        "daemon_running": False,
        "daemon_pid": None,
        "lock_file": None,
        "effect_marker": None,
        "result_marker": None,
        "queue_db_exists": False,
        "queue_db_rows": 0,
    }

    # Check lock file
    lock_path = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
    if lock_path.exists():
        status["lock_file"] = str(lock_path)
        try:
            raw = lock_path.read_text(encoding="utf-8").strip()
            meta = None
            try:
                pid = int(raw)
            except ValueError:
                meta = json.loads(raw)
                pid = int(meta["pid"])
            status["daemon_pid"] = pid
            
            is_running = psutil.pid_exists(pid)
            if is_running and meta and "process_create_time" in meta:
                try:
                    actual_create = psutil.Process(pid).create_time()
                    if abs(actual_create - float(meta["process_create_time"])) > 1.0:
                        is_running = False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    is_running = False
            status["daemon_running"] = is_running
        except Exception:
            status["daemon_running"] = False

    # Check markers
    effect_marker = state_dir / "effect_marker.json"
    result_marker = state_dir / "result_marker.json"
    if effect_marker.exists():
        try:
            data = json.loads(effect_marker.read_text(encoding="utf-8"))
            status["effect_marker"] = data.get("task_id", "unknown")
        except Exception:
            status["effect_marker"] = "UNREADABLE"

    if result_marker.exists():
        try:
            data = json.loads(result_marker.read_text(encoding="utf-8"))
            status["result_marker"] = data.get("task_id", "unknown")
        except Exception:
            status["result_marker"] = "UNREADABLE"

    # Check queue DB
    queue_db = state_dir / "queue.db"
    if queue_db.exists():
        status["queue_db_exists"] = True
        try:
            import sqlite3
            conn = sqlite3.connect(str(queue_db))
            count = conn.execute("SELECT count(*) FROM background_jobs").fetchone()[0]
            status["queue_db_rows"] = count
            conn.close()
        except Exception:
            pass

    return status


def print_status():
    """Print a human-readable status report."""
    s = worker_status()
    print(f"Worker: {s['worker_id']}")
    print(f"  Daemon Running: {s['daemon_running']}")
    print(f"  Daemon PID:     {s['daemon_pid']}")
    print(f"  Lock File:      {s['lock_file']}")
    print(f"  Effect Marker:  {s['effect_marker'] or 'None'}")
    print(f"  Result Marker:  {s['result_marker'] or 'None'}")
    print(f"  Queue DB:       {s['queue_db_exists']} ({s['queue_db_rows']} rows)")


if __name__ == "__main__":
    print_status()
