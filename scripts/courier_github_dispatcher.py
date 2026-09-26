#!/usr/bin/env python3
import os
import sys
import time
import requests
import json
import re
import subprocess
from pathlib import Path

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
WORKER_ID = "GITHUB-DISPATCHER"
# Durable (not /tmp): packets must survive a dispatcher crash or host reboot.
DISPATCH_DIR = Path(os.environ.get("COURIER_GITHUB_DISPATCH_DIR", "events/github-dispatch"))
IDENTITY_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")
SAFE_DISPATCH_ID = re.compile(r"^dispatch-[A-Za-z0-9_-]+$")

def log(msg):
    print(f"[GitHub Dispatcher] {msg}", flush=True)

def persist_packet(task):
    """Atomically write the TaskPacket; return its path, or None if it is not bindable."""
    missing = [f for f in IDENTITY_FIELDS if not isinstance(task.get(f), str) or not task[f]]
    if missing:
        log(f"Refusing task without identity fields: {', '.join(missing)}")
        return None
    if not SAFE_DISPATCH_ID.match(task["dispatch_id"]):
        log("Refusing task with unsafe dispatch_id")
        return None
    DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
    path = DISPATCH_DIR / f"{task['dispatch_id']}.json"
    if path.exists():
        return None  # already persisted; resume_pending() owns it
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(task, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path

def spawn_adapter(path):
    python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else "python3"
    subprocess.Popen([python_bin, "scripts/github_worker_adapter.py", str(path)])

def handle_claimed_task(task):
    """Persist identity first; only then start execution."""
    path = persist_packet(task)
    if path is None:
        return False
    spawn_adapter(path)
    return True

def resume_pending():
    """Restart adapters for persisted dispatches that were never POSTED."""
    resumed = 0
    if not DISPATCH_DIR.is_dir():
        return 0
    for path in sorted(DISPATCH_DIR.glob("dispatch-*.json")):
        if path.name.endswith(".github-worker-state.json"):
            continue
        state_file = path.with_name(f"{path.stem}.github-worker-state.json")
        if state_file.is_file():
            try:
                if json.loads(state_file.read_text(encoding="utf-8")).get("status") == "POSTED":
                    continue
            except (OSError, ValueError) as exc:
                quarantine = path.with_name(
                    f"{path.stem}.github-worker-state.json.corrupt-{int(time.time())}")
                try:
                    os.replace(state_file, quarantine)
                except OSError:
                    pass
                log(f"Quarantined corrupt worker state {state_file.name}: {exc}")
                continue
        spawn_adapter(path)
        resumed += 1
    return resumed

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting GitHub Dispatcher ({WORKER_ID}) pointing to {API_URL}")
    resumed = resume_pending()
    if resumed:
        log(f"Resumed {resumed} persisted dispatch(es).")
    
    # Register
    try:
        requests.post(f"{API_URL}/workers/register", json={"worker_id": WORKER_ID, "platform": "linux", "capabilities": ["github"]}, headers=HEADERS, timeout=10)
    except Exception as e:
        log(f"Failed to register: {e}")

    while True:
        try:
            # Heartbeat
            requests.post(f"{API_URL}/workers/heartbeat", json={"worker_id": WORKER_ID}, headers=HEADERS, timeout=10)
            
            # Claim
            res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": WORKER_ID}, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                task = res.json().get("task")
                if task:
                    task_id = task.get("task_id")
                    log(f"Claimed task {task_id} for GitHub.")
                    handle_claimed_task(task)
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
