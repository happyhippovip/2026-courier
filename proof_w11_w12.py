import os
import sys
import time
import requests
import uuid
import threading

API_KEY = "test-key-123"
os.environ["COURIER_API_KEY"] = API_KEY
os.environ["COURIER_VERIFIER_API_KEY"] = "test-key-456"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
VERIFIER_HEADERS = {"Authorization": f"Bearer test-key-456"}

from server.app import app, load_state

def run_server():
    app.run(port=5001, debug=False, use_reloader=False)

threading.Thread(target=run_server, daemon=True).start()
time.sleep(2)

BASE_URL = "http://localhost:5001"

# Register worker
worker_id = f"w11-worker-{uuid.uuid4().hex}"
res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": worker_id, "capabilities": ["windows"]}, headers=HEADERS)
assert res.status_code == 200

# Submit Goal with A and B
plan = [
    {"task_id": "TaskA", "instruction": "Task A", "target_agent": "windows"},
    {"task_id": "TaskB", "instruction": "Task B", "target_agent": "windows", "depends_on": "TaskA"}
]
res = requests.post(f"{BASE_URL}/goals", json={"goal_text": "W11 Test", "workflow_plan": plan}, headers=HEADERS)
assert res.status_code == 200
goal_id = res.json()["goal_id"]

# Claim Task A
res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
assert res.status_code == 200
task_a = res.json()["task"]
assert task_a["goal_id"] == goal_id
assert task_a["task_id"] == "TaskA"

# Submit Result for Task A
res = requests.post(f"{BASE_URL}/tasks/result", json={
    "task_id": task_a["task_id"],
    "worker_id": worker_id,
    "result_id": "res-A",
    "status": "SUCCESS",
    "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
    "attempt_id": task_a["attempt_id"],
    "dispatch_id": task_a["dispatch_id"],
    "execution_ref": task_a["execution_ref"],
    "goal_id": goal_id,
    "run_id": "test-run"
}, headers=HEADERS)
assert res.status_code == 200

# Verify Task A
res = requests.post(f"{BASE_URL}/tasks/verify", json={
    "task_id": task_a["task_id"],
    "verifier_id": "verifier-1",
    "result_id": "res-A",
    "verdict": "PASS",
    "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
}, headers=VERIFIER_HEADERS)
assert res.status_code == 200

# Now try to claim Task B
res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
assert res.status_code == 200
task_b = res.json().get("task")
if task_b and task_b.get("goal_id") == goal_id and task_b.get("task_id") == "TaskB":
    print("W11 & W12: AUTOMATIC NEXT DISPATCH proven. Task B claimed successfully.")
    sys.exit(0)
else:
    print("W11/W12 FAILED: Task B was not dispatched.", task_b)
    sys.exit(1)

