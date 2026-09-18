import os
import sys
import time
import requests
import uuid
import threading
from unittest.mock import MagicMock

API_KEY = "test-key-123"
os.environ["COURIER_API_KEY"] = API_KEY
os.environ["COURIER_VERIFIER_API_KEY"] = "test-key-456"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
VERIFIER_HEADERS = {"Authorization": f"Bearer test-key-456"}

import server.app

mock_chief = MagicMock()
replenish_calls = 0
def fake_formulate(*args, **kwargs):
    global replenish_calls
    replenish_calls += 1
    if replenish_calls == 1:
        return (None, [{"task_id": "Task-2", "instruction": "Task 2", "target_agent": "windows"}])
    elif replenish_calls == 2:
        return (None, [{"task_id": "Task-3", "instruction": "Task 3", "target_agent": "windows"}])
    else:
        return (None, []) # Terminal

mock_chief.formulate_workflow_plan.side_effect = fake_formulate
server.app.ChiefCommander = lambda: mock_chief

from server.app import app, load_state

def run_server():
    app.run(port=5004, debug=False, use_reloader=False)

threading.Thread(target=run_server, daemon=True).start()
time.sleep(2)

BASE_URL = "http://localhost:5004"
worker_id = f"w14-worker-{uuid.uuid4().hex}"
res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": worker_id, "capabilities": ["windows"]}, headers=HEADERS)
assert res.status_code == 200

# Submit Nonterminal Goal
plan = [{"task_id": "Task-1", "instruction": "Initial Task", "target_agent": "windows"}]
res = requests.post(f"{BASE_URL}/goals", json={
    "goal_text": "W14 Test", "workflow_plan": plan, "terminal": False
}, headers=HEADERS)
assert res.status_code == 200
goal_id = res.json()["goal_id"]

def complete_task(task_id_expected):
    res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
    assert res.status_code == 200
    task = res.json().get("task")
    if not task:
        return False
    assert task["task_id"] == task_id_expected
    
    res = requests.post(f"{BASE_URL}/tasks/result", json={
        "task_id": task["task_id"], "worker_id": worker_id, "result_id": f"res-{task['task_id']}",
        "status": "SUCCESS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
        "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"], "goal_id": goal_id, "run_id": "test-run"
    }, headers=HEADERS)
    assert res.status_code == 200
    
    res = requests.post(f"{BASE_URL}/tasks/verify", json={
        "task_id": task["task_id"], "verifier_id": "verifier-1", "result_id": f"res-{task['task_id']}",
        "verdict": "PASS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
    }, headers=VERIFIER_HEADERS)
    assert res.status_code == 200
    return True

# Complete Task 1 (Triggers replenish 1)
assert complete_task("Task-1")
# Complete Task 2 (Triggers replenish 2)
assert complete_task("Task-2")
# Complete Task 3 (Triggers replenish 3 - empty)
assert complete_task("Task-3")

# Goal should now be DONE
res = requests.get(f"{BASE_URL}/goals/{goal_id}", headers=HEADERS)
goal = res.json().get("goal")
if goal["status"] == "DONE" and goal.get("replenish_count", 0) == 3:
    print("W14: NO FALSE DONE AFTER ONE REPLENISH proven.")
    sys.exit(0)
else:
    print("W14 FAILED.", goal)
    sys.exit(1)
