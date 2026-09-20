import os
import sys
import time
import requests
import uuid
import threading
from unittest.mock import MagicMock

STATE_FILE = os.environ.get("COURIER_STATE_FILE", r"C:\ProgramData\Courier\central_state.json")
if os.path.exists(STATE_FILE):
    os.remove(STATE_FILE)
if os.path.exists(STATE_FILE + ".lock"):
    os.remove(STATE_FILE + ".lock")

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
        return (None, [{"task_id": "T-Replenish-1", "instruction": "Task R", "target_agent": "windows"}])
    else:
        return (None, [])

mock_chief.formulate_workflow_plan.side_effect = fake_formulate
server.app.ChiefCommander = lambda: mock_chief

from server.app import app

def run_server():
    app.run(port=5008, debug=False, use_reloader=False)

threading.Thread(target=run_server, daemon=True).start()
time.sleep(2)

BASE_URL = "http://localhost:5008"
worker_id = f"w15-worker-{uuid.uuid4().hex}"
res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": worker_id, "capabilities": ["windows"]}, headers=HEADERS)
assert res.status_code == 200

# SCENARIO 1: Terminal Goal -> queue empty -> DONE
plan1 = [{"task_id": "T-Term-1", "instruction": "Initial Task", "target_agent": "windows"}]
res = requests.post(f"{BASE_URL}/goals", json={
    "goal_text": "W15 Term", "workflow_plan": plan1, "terminal": True
}, headers=HEADERS)
g_term = res.json()["goal_id"]

res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
task = res.json().get("task")
r2 = requests.post(f"{BASE_URL}/tasks/result", json={
    "task_id": task["task_id"], "worker_id": worker_id, "result_id": f"res-{task['task_id']}",
    "status": "SUCCESS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
    "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
    "execution_ref": task["execution_ref"], "goal_id": g_term, "run_id": "test-run"
}, headers=HEADERS)
if r2.status_code != 200:
    print("S1 result:", r2.text)

r3 = requests.post(f"{BASE_URL}/tasks/verify", json={
    "task_id": task["task_id"], "verifier_id": "verifier-1", "result_id": f"res-{task['task_id']}",
    "verdict": "PASS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
}, headers=VERIFIER_HEADERS)

res = requests.get(f"{BASE_URL}/goals/{g_term}", headers=HEADERS)
if res.json()["goal"]["status"] != "DONE":
    print("Scenario 1 failed")
    sys.exit(1)

# SCENARIO 2: Nonterminal Goal -> queue empty -> Replenish (ACTIVE)
plan2 = [{"task_id": "T-NonTerm-1", "instruction": "Initial Task", "target_agent": "windows"}]
res = requests.post(f"{BASE_URL}/goals", json={
    "goal_text": "W15 NonTerm", "workflow_plan": plan2, "terminal": False
}, headers=HEADERS)
g_nonterm = res.json()["goal_id"]

res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
task = res.json().get("task")
r2 = requests.post(f"{BASE_URL}/tasks/result", json={
    "task_id": task["task_id"], "worker_id": worker_id, "result_id": f"res-{task['task_id']}",
    "status": "SUCCESS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
    "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
    "execution_ref": task["execution_ref"], "goal_id": g_nonterm, "run_id": "test-run"
}, headers=HEADERS)
if r2.status_code != 200:
    print("S2 result:", r2.text)

requests.post(f"{BASE_URL}/tasks/verify", json={
    "task_id": task["task_id"], "verifier_id": "verifier-1", "result_id": f"res-{task['task_id']}",
    "verdict": "PASS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
}, headers=VERIFIER_HEADERS)

res = requests.get(f"{BASE_URL}/goals/{g_nonterm}", headers=HEADERS)
if res.json()["goal"]["status"] != "ACTIVE":
    print("Scenario 2 failed, status is", res.json()["goal"]["status"])
    sys.exit(1)

# SCENARIO 3: Wall Goal -> BLOCKED
plan3 = [{"task_id": "T-Wall-1", "instruction": "Initial Task", "target_agent": "windows"}]
res = requests.post(f"{BASE_URL}/goals", json={
    "goal_text": "W15 Wall", "workflow_plan": plan3, "terminal": False
}, headers=HEADERS)
g_wall = res.json()["goal_id"]

# Because of replenish in S2, there might be a task queued from S2 replenish!
# Wait, let's claim until we get the task for g_wall
task = None
while True:
    res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
    t = res.json().get("task")
    if t and t["goal_id"] == g_wall:
        task = t
        break
    elif t:
        # Complete the task from S2
        requests.post(f"{BASE_URL}/tasks/result", json={
            "task_id": t["task_id"], "worker_id": worker_id, "result_id": f"res-{t['task_id']}",
            "status": "SUCCESS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
            "attempt_id": t["attempt_id"], "dispatch_id": t["dispatch_id"],
            "execution_ref": t["execution_ref"], "goal_id": t["goal_id"], "run_id": "test-run"
        }, headers=HEADERS)
        requests.post(f"{BASE_URL}/tasks/verify", json={
            "task_id": t["task_id"], "verifier_id": "verifier-1", "result_id": f"res-{t['task_id']}",
            "verdict": "PASS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
        }, headers=VERIFIER_HEADERS)
    else:
        break

r2 = requests.post(f"{BASE_URL}/tasks/result", json={
    "task_id": task["task_id"], "worker_id": worker_id, "result_id": f"res-{task['task_id']}",
    "status": "FAILED", "stderr": "Error: MONEY_REQUIRED to proceed.", "artifacts": [],
    "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
    "execution_ref": task["execution_ref"], "goal_id": g_wall, "run_id": "test-run"
}, headers=HEADERS)
if r2.status_code != 200:
    print("S3 result:", r2.text)

res = requests.get(f"{BASE_URL}/goals/{g_wall}", headers=HEADERS)
goal = res.json()["goal"]
if goal["status"] == "BLOCKED" and "MONEY_REQUIRED" in goal["workflow_plan"][0].get("recovery_reason", ""):
    print("W15: CLEAN IDLE ONLY WHEN TERMINAL / REAL WALL proven.")
    sys.exit(0)
else:
    print("Scenario 3 failed. Goal:", goal)
    sys.exit(1)
