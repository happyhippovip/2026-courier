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

# Mock ChiefCommander before it's used
import server.app
mock_chief = MagicMock()
mock_chief.formulate_workflow_plan.return_value = (None, [
    {"task_id": "Task-Replenished", "instruction": "Auto Replenished Task", "target_agent": "windows"}
])
server.app.ChiefCommander = lambda: mock_chief

from server.app import app, load_state

def run_server():
    # Use a different port to avoid conflicts
    app.run(port=5003, debug=False, use_reloader=False)

threading.Thread(target=run_server, daemon=True).start()
time.sleep(2)

BASE_URL = "http://localhost:5003"

worker_id = f"w13-worker-{uuid.uuid4().hex}"
res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": worker_id, "capabilities": ["windows"]}, headers=HEADERS)
assert res.status_code == 200

# Submit a nonterminal Goal with 1 task
plan = [
    {"task_id": f"Task1-{uuid.uuid4().hex}", "instruction": "Initial Task", "target_agent": "windows"}
]
res = requests.post(f"{BASE_URL}/goals", json={
    "goal_text": "W13 Test Nonterminal",
    "workflow_plan": plan,
    "terminal": False
}, headers=HEADERS)
assert res.status_code == 200
goal_id = res.json()["goal_id"]

# Claim Task 1
res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
assert res.status_code == 200
task_1 = res.json()["task"]
assert task_1["goal_id"] == goal_id

# Result Task 1
res = requests.post(f"{BASE_URL}/tasks/result", json={
    "task_id": task_1["task_id"],
    "worker_id": worker_id,
    "result_id": "res-1",
    "status": "SUCCESS",
    "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
    "attempt_id": task_1["attempt_id"],
    "dispatch_id": task_1["dispatch_id"],
    "execution_ref": task_1["execution_ref"],
    "goal_id": goal_id,
    "run_id": "test-run"
}, headers=HEADERS)
assert res.status_code == 200

# Verify Task 1 (This should trigger replenish)
res = requests.post(f"{BASE_URL}/tasks/verify", json={
    "task_id": task_1["task_id"],
    "verifier_id": "verifier-1",
    "result_id": "res-1",
    "verdict": "PASS",
    "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
}, headers=VERIFIER_HEADERS)
assert res.status_code == 200

# Now try to claim the replenished task
res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
assert res.status_code == 200
task_replenished = res.json().get("task")

if task_replenished and task_replenished.get("goal_id") == goal_id and task_replenished.get("task_id") == "Task-Replenished":
    print("W13: BOUNDED AUTO-REPLENISH ON OPEN GOAL proven. Task replenished and claimed successfully.")
    sys.exit(0)
else:
    print("W13 FAILED: Replenished task was not dispatched.", task_replenished)
    sys.exit(1)
