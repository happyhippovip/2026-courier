import os
import sys
import time
import requests
import uuid

API_KEY = "test-key-123"
os.environ["COURIER_API_KEY"] = API_KEY
os.environ["COURIER_VERIFIER_API_KEY"] = "test-key-456"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
VERIFIER_HEADERS = {"Authorization": f"Bearer test-key-456"}

# Import after setting env vars
from server.app import app, load_state
import threading

def run_server():
    app.run(port=5001, debug=False, use_reloader=False)

threading.Thread(target=run_server, daemon=True).start()
time.sleep(2)

BASE_URL = "http://localhost:5001"

# 1. Register worker
worker_id = f"w9-worker-{uuid.uuid4().hex}"
res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": worker_id, "capabilities": ["windows"]}, headers=HEADERS)
assert res.status_code == 200, res.text

# 2. Submit Goal
res = requests.post(f"{BASE_URL}/goals", json={"goal_text": "W9 Test Goal", "workflow_plan": [{"instruction": "W9 Test Task", "target_agent": "windows"}]}, headers=HEADERS)
assert res.status_code == 200, res.text
goal_id = res.json()["goal_id"]

# 3. Claim Task
res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
print("Claim response:", res.status_code, res.text)
assert res.status_code == 200, res.text
task = res.json().get("task")
if task is None:
    print("Error: task is None. Reason:", res.json().get("reason"), res.json().get("error"))
    sys.exit(1)

task_id = task["task_id"]
goal_id = task["goal_id"]
attempt_id = task["attempt_id"]
dispatch_id = task["dispatch_id"]
execution_ref = task["execution_ref"]
assert task_id, "task_id missing"
assert attempt_id, "attempt_id missing"
assert dispatch_id, "dispatch_id missing"
assert execution_ref, "execution_ref missing"

# 4. Submit Result
result_id = f"res-{uuid.uuid4().hex}"
res = requests.post(f"{BASE_URL}/tasks/result", json={
    "task_id": task_id,
    "worker_id": worker_id,
    "result_id": result_id,
    "status": "SUCCESS",
    "artifacts": [{"path": name, "sha256": "0"*64} for name in task.get("artifacts", [])],
    "attempt_id": attempt_id,
    "dispatch_id": dispatch_id,
    "execution_ref": execution_ref,
    "goal_id": goal_id,
    "run_id": "test-run"
}, headers=HEADERS)
assert res.status_code == 200, res.text

# 5. Verify Result
verifier_id = "w9-verifier"
res = requests.post(f"{BASE_URL}/tasks/verify", json={
    "task_id": task_id,
    "verifier_id": verifier_id,
    "result_id": result_id,
    "verdict": "PASS",
    "artifacts": [{"path": name, "sha256": "0"*64} for name in task.get("artifacts", [])]
}, headers=VERIFIER_HEADERS)
assert res.status_code == 200, res.text

# Check state
state = load_state()
final_task = state["tasks"][task_id]

assert final_task["goal_id"] == goal_id
assert final_task["task_id"] == task_id
assert final_task["attempt_id"] == attempt_id
assert final_task["dispatch_id"] == dispatch_id
assert final_task["execution_ref"] == execution_ref
assert final_task["result"]["result_id"] == result_id
assert final_task["verification"]["result_id"] == result_id
assert final_task["verification"]["verifier_id"] == verifier_id

print("W9: EXACT IDENTITY CHAIN proven. All identifiers are linked and persist through reconcile.")

