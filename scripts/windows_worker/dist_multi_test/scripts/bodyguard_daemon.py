#!/usr/bin/env python3
import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path

API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ.get("COURIER_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

BODYGUARDS = [
    "agent-bodyguard-alpha",
    "agent-bodyguard-bravo",
    "agent-bodyguard-charlie",
    "agent-bodyguard-delta",
    "agent-bodyguard-echo",
    "agent-bodyguard-foxtrot",
    "agent-bodyguard-golf",
    "agent-bodyguard-hotel"
]

def get_temporary_role(worker_id):
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from run_bodyguards import BodyguardPoolManager
        manager = BodyguardPoolManager()
        for bg in manager.get_all_bodyguards():
            if bg["id"] == worker_id:
                return bg.get("temporary_role", "TECHNICAL_WORKER")
    except Exception as e:
        print(f"Failed to read bodyguard state: {e}")
    return "TECHNICAL_WORKER"

def execute_task(task, worker_id, role):
    print(f"[{worker_id}] Executing task {task['task_id']} with role {role}")
    
    # Select adapter based on role
    if role in ("TECHNICAL_WORKER", "DIAGNOSTIC_WORKER", "QA_WORKER"):
        adapter = "scripts/run_codex_bridge.py"
    else:
        adapter = "scripts/run_antigravity_bridge.py"
        
    # Build a temporary file for the task
    task_file = Path(f"events/agent-states/{task['task_id']}.json")
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_file.write_text(json.dumps(task), encoding="utf-8")
    
    
    execution_start_at = time.time()
    try:
        proc = subprocess.run(
            ["python3", adapter, "--task", str(task_file)],
            capture_output=True, text=True, timeout=120
        )
        execution_end_at = time.time()
        status = "SUCCESS" if proc.returncode == 0 else "FAILED"
        stdout = proc.stdout
        stderr = proc.stderr
    except Exception as e:
        execution_end_at = time.time()
        status = "FAILED"
        stdout = ""
        stderr = str(e)
        
    if task_file.exists():
        task_file.unlink()
        
    import uuid
    import hashlib
    run_id = f"run-{uuid.uuid4().hex}"
    identity = {
        "goal_id": task.get("goal_id"),
        "task_id": task.get("task_id"),
        "attempt_id": task.get("attempt_id"),
        "dispatch_id": task.get("dispatch_id"),
        "worker_id": worker_id,
        "run_id": run_id,
        "status": status,
        "artifacts": []
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    identity["result_id"] = f"result-{hashlib.sha256(payload).hexdigest()}"
    identity["stdout"] = stdout
    identity["stderr"] = stderr
    identity["execution_start_at"] = execution_start_at
    identity["execution_end_at"] = execution_end_at
    return identity

def main():
    if not API_KEY:
        print("COURIER_API_KEY is required. Export it and restart.")
        return

    print(f"Starting Bodyguard Daemon connecting to {API_URL}")
    for bg in BODYGUARDS:
        try:
            requests.post(f"{API_URL}/workers/register", json={
                "worker_id": bg, 
                "platform": "linux", 
                "capabilities": ["local_filesystem", "deterministic_execution", "test_runner", "state_aggregation"]
            }, headers=HEADERS, timeout=10)
        except Exception as e:
            print(f"Failed to register {bg}: {e}")

    while True:
        for bg in BODYGUARDS:
            try:
                resp = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": bg}, headers=HEADERS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    task = data.get("task")
                    if task:
                        role = get_temporary_role(bg)
                        res = execute_task(task, bg, role)
                        requests.post(f"{API_URL}/tasks/result", json=res, headers=HEADERS, timeout=10)
            except Exception:
                pass
        time.sleep(5)

if __name__ == "__main__":
    main()
