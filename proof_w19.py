import sys
import time
import requests
import subprocess
import threading
import os
import json

API_URL = "http://127.0.0.1:8080"
API_KEY = "test-key"

def start_server():
    env = os.environ.copy()
    env["COURIER_API_KEY"] = API_KEY
    env["COURIER_VERIFIER_API_KEY"] = "verifier-test-key"
    env["FLASK_APP"] = "server/app.py"
    env["PORT"] = "8080"
    env["PYTHONPATH"] = os.getcwd()
    env["PYTHONUNBUFFERED"] = "1"
    env["COURIER_DATA_DIR"] = os.path.join(os.getcwd(), "test_courier_data")
    env["COURIER_STATE_FILE"] = os.path.join(env["COURIER_DATA_DIR"], "central_state.json")
    return subprocess.Popen(
        [sys.executable, "server/app.py"],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

def start_worker():
    env = os.environ.copy()
    env["COURIER_API_KEY"] = API_KEY
    env["COURIER_SERVER"] = API_URL
    env["COURIER_WORKER_ID"] = "w19-worker"
    env["PYTHONPATH"] = os.getcwd()
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(
        [sys.executable, "scripts/windows_worker/daemon.py"],
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

def main():
    print("Cleaning up old state...")
    try:
        os.remove("test_courier_data/central_state.json")
    except OSError:
        pass
    try:
        os.remove("scripts/windows_worker/state/effect_marker.json")
    except OSError:
        pass

    print("Starting server...")
    server = start_server()
    time.sleep(5)

    print("Starting worker...")
    worker = start_worker()
    time.sleep(3)
    
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    print("Waiting for server to be up...")
    up = False
    for _ in range(30):
        try:
            requests.get(f"{API_URL}/goals", headers=headers)
            up = True
            break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            
    if not up:
        print("Server failed to start")
        server.kill()
        sys.exit(1)

    print("Submitting goal T-W19-1 (long running task)...")
    res = requests.post(f"{API_URL}/goals", headers=headers, json={
        "goal_text": "Long Task",
        "workflow_plan": [
            {
                "task_id": "T-W19-1-task1",
                "instruction": "Start-Sleep -Seconds 10",
                "target_agent": "windows"
            }
        ]
    })
    res.raise_for_status()
    goal_id_1 = res.json()["goal_id"]

    print("Waiting for task to be claimed...")
    claimed = False
    for _ in range(20):
        time.sleep(1)
        r = requests.get(f"{API_URL}/goals/{goal_id_1}", headers=headers)
        r.raise_for_status()
        state = r.json()
        task = next((t for t in state.get("tasks", []) if t["task_id"] == "T-W19-1-task1"), None)
        if not task:
            task = next((t for t in state.get("goal", {}).get("workflow_plan", []) if t["task_id"] == "T-W19-1-task1"), None)
        
        if task and task.get("status") in ["IN_PROGRESS", "DISPATCHED"]:
            claimed = True
            break

    if not claimed:
        print("Task was not claimed!")
        worker.kill()
        server.kill()
        sys.exit(1)

    print("Task claimed. Waiting a moment for worker to write marker...")
    time.sleep(2)

    print("Killing worker forcefully...")
    worker.kill()
    time.sleep(2)

    print("Restarting worker...")
    worker2 = start_worker()
    time.sleep(3)

    print("Waiting for crash to be reported...")
    reported = False
    for _ in range(20):
        time.sleep(1)
        r = requests.get(f"{API_URL}/goals/{goal_id_1}", headers=headers)
        r.raise_for_status()
        state = r.json()
        task = next((t for t in state.get("tasks", []) if t["task_id"] == "T-W19-1-task1"), None)
        if not task:
            task = next((t for t in state.get("goal", {}).get("workflow_plan", []) if t["task_id"] == "T-W19-1-task1"), None)
        
        if task and task.get("status") == "HUMAN_REQUIRED" and "AMBIGUOUS_CRASH" in task.get("result", {}).get("stderr", ""):
            reported = True
            break

    if not reported:
        print("Crash was not reported correctly!")
        worker2.kill()
        server.kill()
        sys.exit(1)
        
    print("Submitting goal T-W19-2 to ensure worker can take new tasks...")
    res = requests.post(f"{API_URL}/goals", headers=headers, json={
        "goal_text": "Quick Task",
        "workflow_plan": [
            {
                "task_id": "T-W19-2-task1",
                "instruction": "echo SUCCESS > courier_canary_T-W19-2-task1.txt",
                "target_agent": "windows"
            }
        ]
    })
    res.raise_for_status()
    goal_id_2 = res.json()["goal_id"]

    success = False
    for _ in range(15):
        time.sleep(1)
        r = requests.get(f"{API_URL}/goals/{goal_id_2}", headers=headers)
        r.raise_for_status()
        state = r.json()
        task = next((t for t in state.get("tasks", []) if t["task_id"] == "T-W19-2-task1"), None)
        if not task:
            task = next((t for t in state.get("goal", {}).get("workflow_plan", []) if t["task_id"] == "T-W19-2-task1"), None)
        
        if task:
            print(f"Task status is {task.get('status')} - Tasks List: {json.dumps(state.get('tasks', []))}")
            if task.get("status") in ["RESULT_RECEIVED", "SUCCESS", "RECONCILED", "DONE"]:
                success = True
                break
            
    worker2.kill()
    server.kill()
    
    if not success:
        print("Worker did not process new task!")
        sys.exit(1)
        
    print("W19 PROOF SUCCESS")
    sys.exit(0)

if __name__ == "__main__":
    main()
