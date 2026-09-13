#!/usr/bin/env python3
import json
import time
import subprocess
import os
import sys
import datetime
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
QUEUE_FILE = str(WORKSPACE_DIR / "events" / "mission-queue" / "queue.json")
STATE_FILE = str(WORKSPACE_DIR / "mac_state.json")

def log(msg):
    print(f"[{datetime.datetime.now().isoformat()}] {msg}")
    sys.stdout.flush()

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading {path}: {e}")
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def main_loop():
    log(f"Courier Daemon Started. PID: {os.getpid()}")
    while True:
        try:
            # Check backoff
            queue = load_json(QUEUE_FILE, {})
            if not queue:
                time.sleep(5)
                continue

            # Check state
            status = queue.get("MISSION_STATUS")
            if status == "HUMAN_GATE":
                time.sleep(5)
                continue
            elif status == "IN_PROGRESS":
                time.sleep(5)
                continue
            elif status != "WAITING_AUTHORIZED_WORK":
                time.sleep(5)
                continue

            # Backoff check
            backoff = queue.get("BACKOFF_UNTIL")
            if backoff:
                if datetime.datetime.now().timestamp() < backoff:
                    time.sleep(5)
                    continue
                else:
                    queue["BACKOFF_UNTIL"] = None

            # Get pending tasks
            assignments = queue.get("ACTIVE_ASSIGNMENTS", [])
            pending = [t for t in assignments if t.get("status") == "PENDING"]

            if not pending:
                time.sleep(5)
                continue

            task = pending[0]
            task_id = task["id"]
            task_desc = task["desc"]

            log(f"Dispatching fresh worker for {task_id}: {task_desc}")

            # Update State
            queue["MISSION_STATUS"] = "IN_PROGRESS"
            queue["ACTIVE_TASK_ID"] = task_id
            save_json(QUEUE_FILE, queue)

            # Worker Invocation
            cmd = [
                "agy", "-p",
                f"Execute task {task_id}: {task_desc}. Output success. Do not ask for user input.",
                "--dangerously-skip-permissions",
                "--new-project"
            ]

            start_time = time.time()
            with open(os.devnull, "r") as devnull:
                proc = subprocess.run(cmd, stdin=devnull, capture_output=True, text=True, timeout=300)

            duration = time.time() - start_time
            log(f"Worker finished in {duration:.1f}s. Exit code: {proc.returncode}")

            # Check progress / watchdog
            queue = load_json(QUEUE_FILE, {})
            if proc.returncode == 0:
                for t in queue.get("ACTIVE_ASSIGNMENTS", []):
                    if t["id"] == task_id:
                        t["status"] = "DONE"
                queue["MISSION_STATUS"] = "WAITING_AUTHORIZED_WORK"
                queue["FAILURE_COUNT"] = 0
                queue["LAST_VERIFIED_TASK"] = task_id
                log(f"Task {task_id} marked DONE.")
            else:
                fails = queue.get("FAILURE_COUNT", 0) + 1
                queue["FAILURE_COUNT"] = fails
                log(f"Worker failed. Failures: {fails}")
                if fails >= 3:
                    queue["MISSION_STATUS"] = "HUMAN_GATE"
                    queue["BLOCK_REASON"] = "NO_PROGRESS_WATCHDOG_TRIPPED"
                else:
                    queue["MISSION_STATUS"] = "WAITING_AUTHORIZED_WORK"

            save_json(QUEUE_FILE, queue)

        except subprocess.TimeoutExpired:
            log("Worker timed out.")
            queue = load_json(QUEUE_FILE, {})
            queue["MISSION_STATUS"] = "WAITING_AUTHORIZED_WORK"
            queue["FAILURE_COUNT"] = queue.get("FAILURE_COUNT", 0) + 1
            save_json(QUEUE_FILE, queue)
        except Exception as e:
            log(f"Daemon error: {e}")

        time.sleep(5)

if __name__ == "__main__":
    main_loop()
