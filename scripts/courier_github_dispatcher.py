#!/usr/bin/env python3
import os
import re
import sys
import tempfile
import time
import requests
import json
import subprocess

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
WORKER_ID = "GITHUB-DISPATCHER"
# Resolve repo-root-relative paths from the script location, not the cwd the
# dispatcher happened to start in.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

def log(msg):
    print(f"[GitHub Dispatcher] {msg}", flush=True)

def task_tmp_file(task_id):
    """Return the adapter input path for a task, or None if unsafe.

    task_id arrives from the server; interpolating it raw into a path allows
    directory traversal (e.g. "../../x"). Only accept a safe basename shape.
    """
    if not isinstance(task_id, str) or not _SAFE_TASK_ID.match(task_id):
        return None
    return os.path.join(tempfile.gettempdir(), f"{task_id}.json")

def python_bin():
    venv_python = os.path.join(REPO_ROOT, "venv", "bin", "python3")
    return venv_python if os.path.exists(venv_python) else "python3"

def reap_children(children):
    """Poll tracked adapter processes; reap finished ones, keep live ones.

    Without this, every spawned adapter stays a zombie until the dispatcher
    itself exits (process leak), and adapter failures go unnoticed.
    `children` is a list of (task_id, Popen). Returns the still-live list.
    """
    live = []
    for task_id, child in children:
        code = child.poll()
        if code is None:
            live.append((task_id, child))
        elif code != 0:
            log(f"Adapter for task {task_id} exited with code {code}")
    return live

def run_loop():
    if not API_KEY:
        raise SystemExit("COURIER_API_KEY is required")
    log(f"Starting GitHub Dispatcher ({WORKER_ID}) pointing to {API_URL}")
    
    # Register
    try:
        requests.post(f"{API_URL}/workers/register", json={"worker_id": WORKER_ID, "platform": "linux", "capabilities": ["github"]}, headers=HEADERS, timeout=10)
    except Exception as e:
        log(f"Failed to register: {e}")

    children = []
    while True:
        try:
            children = reap_children(children)

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
                    tmp_file = task_tmp_file(task_id)
                    if tmp_file is None:
                        log(f"Refusing task with unsafe task_id: {task_id!r}")
                        continue
                    with open(tmp_file, "w") as f:
                        json.dump(task, f)

                    adapter = os.path.join(REPO_ROOT, "scripts", "github_worker_adapter.py")
                    children.append((task_id, subprocess.Popen([python_bin(), adapter, tmp_file])))
        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    run_loop()
