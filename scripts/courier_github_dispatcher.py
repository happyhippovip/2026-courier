#!/usr/bin/env python3
import os
import sys
import time
import requests
import json
import subprocess
try:
    import keyring
except ImportError:
    keyring = None

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY") or (keyring.get_password if keyring else lambda *args: None)("courier_worker", "COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
WORKER_ID = "GITHUB-DISPATCHER"
WAITING_EXIT_CODE = 75

def log(msg):
    print(f"[GitHub Dispatcher] {msg}", flush=True)


def launch_adapter(task_file):
    python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else "python3"
    return subprocess.Popen([python_bin, "scripts/github_worker_adapter.py", task_file])


def reap_adapters(active_procs):
    """Re-enter bounded hosted waits without asking Central for a second claim."""
    for task_id, entry in list(active_procs.items()):
        process = entry["process"]
        returncode = process.poll()
        if returncode is None:
            continue
        if returncode == WAITING_EXIT_CODE:
            log(f"Hosted task {task_id} still waiting; resuming its durable dispatch.")
            entry["process"] = launch_adapter(entry["task_file"])
            continue
        del active_procs[task_id]
        if returncode != 0:
            log(f"Hosted task {task_id} adapter stopped with code {returncode}; task remains fail-closed.")

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting GitHub Dispatcher ({WORKER_ID}) pointing to {API_URL}")
    
    # Register
    try:
        requests.post(f"{API_URL}/workers/register", json={"worker_id": WORKER_ID, "platform": "linux", "capabilities": ["github"]}, headers=HEADERS, timeout=10)
    except Exception as e:
        log(f"Failed to register: {e}")

    active_procs = {}
    while True:
        reap_adapters(active_procs)
        try:
            # Heartbeat
            requests.post(f"{API_URL}/workers/heartbeat", json={"worker_id": WORKER_ID}, headers=HEADERS, timeout=10)
            
            # Claim
            if active_procs:
                time.sleep(5)
                continue
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
                    
                    active_procs[task_id] = {
                        "process": launch_adapter(tmp_file),
                        "task_file": tmp_file,
                    }
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
