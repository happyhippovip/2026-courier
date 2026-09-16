#!/usr/bin/env python3
import os
import sys
import time
import random
import requests
import json
import subprocess

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
WORKER_ID = os.environ.get("GITHUB_WORKER_ID", "GITHUB-DISPATCHER")

def log(msg):
    print(f"[GitHub Dispatcher] {msg}", flush=True)


import fcntl
def acquire_single_instance_lock():
    lock_file = "/tmp/courier_github_dispatcher.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("Another instance of github dispatcher is already running. Exiting.")
        sys.exit(0)

def run_loop():
    _lock_fd = acquire_single_instance_lock()

    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting GitHub Dispatcher ({WORKER_ID}) pointing to {API_URL}")
    
    # Register
    try:
        requests.post(f"{API_URL}/workers/register", json={"worker_id": WORKER_ID, "platform": "linux", "capabilities": ["github"], "cost_class": "free"}, headers=HEADERS, timeout=10)
    except Exception as e:
        log(f"Failed to register: {e}")

    error_backoff = 2
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
                    
                    # Write to temp file for the adapter
                    tmp_file = f"/tmp/{task_id}.json"
                    with open(tmp_file, "w") as f:
                        json.dump(task, f)
                    
                    python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else "python3"
                    subprocess.Popen([python_bin, "scripts/github_worker_adapter.py", tmp_file])
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            import random
            time.sleep(error_backoff + random.uniform(0, 2))
            error_backoff = min(60, error_backoff * 2)
            continue
            
        import random
        time.sleep(5 + random.uniform(0, 1))
        error_backoff = 2

if __name__ == "__main__":
    run_loop()
