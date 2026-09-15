#!/usr/bin/env python3
import os
import sys
import time
import requests
import json
import subprocess

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY", "prod-secret-12345")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
WORKER_ID = "GITHUB-DISPATCHER"

def log(msg):
    print(f"[GitHub Dispatcher] {msg}", flush=True)

def run_loop():
    log(f"Starting GitHub Dispatcher ({WORKER_ID}) pointing to {API_URL}")
    
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
                    
                    # Write to temp file for the adapter
                    tmp_file = f"/tmp/{task_id}.json"
                    with open(tmp_file, "w") as f:
                        json.dump(task, f)
                    
                    python_bin = "venv/bin/python3" if os.path.exists("venv/bin/python3") else "python3"
                    subprocess.Popen([python_bin, "scripts/github_worker_adapter.py", tmp_file])
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
