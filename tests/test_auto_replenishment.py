from scripts.integration_contract import _canonical_hash
import pytest
import os
import json
import time
import subprocess
import sys
import shutil
from pathlib import Path
import urllib.request
import urllib.error
import uuid

REPO_ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture(scope="module", autouse=True)
def start_server():
    print("Starting server for test...")
    python_exe = sys.executable
    env = os.environ.copy()
    env["PORT"] = "8081"
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["COURIER_SERVER"] = "http://127.0.0.1:8081"
    env["COURIER_MOCK_CHIEF"] = "1"
    env["COURIER_API_KEY"] = "321606503a874d39b50f6137e3321b7f"
    env["COURIER_VERIFIER_API_KEY"] = "421606503a874d39b50f6137e3321b7f"
    
    if os.path.exists("/tmp/mock_replenish.txt"):
        os.remove("/tmp/mock_replenish.txt")

    state_file = Path.home() / ".courier_runtime" / "server" / "state" / "central_state.json"
    if state_file.exists():
        state_file.unlink()

    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(Path.home() / ".courier_runtime"))
    verifier_proc = subprocess.Popen([python_exe, str(REPO_ROOT / "scripts/courier_verifier.py")], env=env, cwd=str(Path.home() / ".courier_runtime"))
    time.sleep(3)
    yield
    print("Stopping server...")
    server_proc.terminate()
    verifier_proc.terminate()
    try:
        server_proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()
    try:
        verifier_proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        verifier_proc.kill()
        verifier_proc.wait()

def http_post(path, data):
    url = f"http://127.0.0.1:8081{path}"
    req = urllib.request.Request(url, method="POST", data=json.dumps(data).encode("utf-8"))
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer 321606503a874d39b50f6137e3321b7f")
    try:
        res = urllib.request.urlopen(req, timeout=5)
        return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())

def http_get(path):
    url = f"http://127.0.0.1:8081{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer 321606503a874d39b50f6137e3321b7f")
    res = urllib.request.urlopen(req, timeout=5)
    return json.loads(res.read().decode())


def test_zero_chat_auto_replenishment():
    # 1. Create a Goal that triggers the mocked Auto-Replenishment
    payload = {
        "goal_id": "goal-replenish-test",
        "goal_text": "REPLENISHMENT_TEST",
        "terminal": False
    }

    res = http_post("/goals", payload)
    assert res.get("status") in ["ACTIVE", "created", "updated"]
    actual_goal_id = res.get("goal_id", "goal-replenish-test")

    
    time.sleep(1)
    
    # Worker register
    http_post("/workers/register", {"worker_id": "linux-worker", "platform": "linux", "capabilities": ["github-actions-safety-baseline-v1", "linux"]})
    time.sleep(1)
    
    tasks_completed = 0
    
    for i in range(3):
        # 2. Worker claims task
        claim_res = http_post("/tasks/claim", {"worker_id": "linux-worker"})
        task = claim_res.get("task")
        if not task:
            time.sleep(2) # Wait for auto-replenish if it didn't happen yet
            claim_res = http_post("/tasks/claim", {"worker_id": "linux-worker"})
            task = claim_res.get("task")
            
        assert task is not None, f"Expected to claim a task on iteration {i}"
        
        # 3. Worker executes task (mock)
        task_id = task["task_id"]
        result_payload = {
            "task_id": task_id,
            "worker_id": "linux-worker",
            "status": "SUCCESS",
            "result_file_path": f"/tmp/result_{task_id}.json",
            "stderr": "",
            "stdout": "success",
            "artifacts": [],
            "attempt_id": task.get("attempt_id"),
            "dispatch_id": task.get("dispatch_id"),
            "execution_ref": task.get("execution_ref"),
            "goal_id": task.get("goal_id"),
            "run_id": f"run-{uuid.uuid4().hex[:8]}",
            "runtime_identity": task.get("server_binding")
        }
        identity = {
            "goal_id": result_payload.get("goal_id"),
            "task_id": result_payload.get("task_id"),
            "attempt_id": result_payload.get("attempt_id"),
            "dispatch_id": result_payload.get("dispatch_id"),
            "execution_ref": result_payload.get("execution_ref"),
            "worker_id": result_payload.get("worker_id"),
            "run_id": result_payload.get("run_id"),
            "status": result_payload.get("status"),
            "artifacts": result_payload.get("artifacts", []),
            "runtime_identity": result_payload.get("runtime_identity")
        }
        if "batch_id" in task: identity["batch_id"] = task["batch_id"]
        if "prompt_id" in task: identity["prompt_id"] = task["prompt_id"]
        result_payload["result_id"] = f"result-{_canonical_hash(identity)}"
        
        # 4. Worker posts result
        post_res = http_post("/tasks/result", result_payload)
        assert post_res.get("status") in ("success", "ACK_RESULT_RECEIVED"), f"Failed to post result: {post_res}"
        tasks_completed += 1
        
        # 5. Verifier picks it up and reconciles
        time.sleep(2)
        
        # 6. Check the goal to see if it replenished
        goal = http_get(f"/goals/{actual_goal_id}").get("goal")
        
        # 7. Check if USER_CONTINUE_MESSAGES is zero
        assert goal.get("user_continue_messages", 0) == 0, "USER_CONTINUE_MESSAGES must be 0"
        
    goal = http_get(f"/goals/{actual_goal_id}").get("goal")
    assert goal.get("replenish_count", 0) >= 2, f"Expected at least 2 replenishment cycles, got {goal.get('replenish_count')}"
    assert tasks_completed >= 3, "Expected at least 3 tasks to be completed"

    print(f"USER_CONTINUE_MESSAGES={goal.get('user_continue_messages', 0)}")
    print(f"TASKS_COMPLETED={tasks_completed}")
    print(f"REPLENISH_CYCLES={goal.get('replenish_count')}")
