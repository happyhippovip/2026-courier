import os
import sys
import time
import requests
import uuid
import subprocess

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

BASE_URL = "http://localhost:5008"

def start_server():
    script = "import os; os.environ['COURIER_API_KEY']='test-key-123'; os.environ['COURIER_VERIFIER_API_KEY']='test-key-456'; from server.app import app, ChiefCommander; from unittest.mock import MagicMock; mock_chief = MagicMock(); mock_chief.formulate_workflow_plan.return_value = (None, []); import server.app; server.app.ChiefCommander = lambda: mock_chief; app.run(port=5008, debug=False, use_reloader=False)"
    proc = subprocess.Popen([sys.executable, "-c", script], env=os.environ.copy())
    time.sleep(3)
    return proc

print("Starting server...")
server_proc = start_server()

try:
    worker_id = f"w16-worker-{uuid.uuid4().hex}"
    res = requests.post(f"{BASE_URL}/workers/register", json={"worker_id": worker_id, "capabilities": ["windows"]}, headers=HEADERS)
    assert res.status_code == 200

    plan = [{"task_id": "T-W16-1", "instruction": "Initial Task", "target_agent": "windows"}]
    res = requests.post(f"{BASE_URL}/goals", json={
        "goal_text": "W16 Restart", "workflow_plan": plan, "terminal": True
    }, headers=HEADERS)
    goal_id = res.json()["goal_id"]

    res = requests.post(f"{BASE_URL}/tasks/claim", json={"worker_id": worker_id}, headers=HEADERS)
    task = res.json().get("task")
    assert task is not None
    assert task["task_id"] == "T-W16-1"

    print("Task claimed. Killing server...")
    server_proc.terminate()
    server_proc.wait(timeout=5)

    print("Restarting server...")
    server_proc = start_server()

    print("Sending result to restarted server...")
    r2 = requests.post(f"{BASE_URL}/tasks/result", json={
        "task_id": task["task_id"], "worker_id": worker_id, "result_id": f"res-{task['task_id']}",
        "status": "SUCCESS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}],
        "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"], "goal_id": goal_id, "run_id": "test-run"
    }, headers=HEADERS)
    
    if r2.status_code != 200:
        print("Failed to send result:", r2.text)
        sys.exit(1)

    r3 = requests.post(f"{BASE_URL}/tasks/verify", json={
        "task_id": task["task_id"], "verifier_id": "verifier-1", "result_id": f"res-{task['task_id']}",
        "verdict": "PASS", "artifacts": [{"path": "dummy.txt", "sha256": "0"*64}]
    }, headers=VERIFIER_HEADERS)

    res = requests.get(f"{BASE_URL}/goals/{goal_id}", headers=HEADERS)
    if res.json()["goal"]["status"] == "DONE":
        print("W16: SERVER RESTART RECOVERY proven.")
        sys.exit(0)
    else:
        print("Goal not DONE:", res.json())
        sys.exit(1)

finally:
    server_proc.terminate()
