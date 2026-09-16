import os
import json
import time
import sys
from unittest import mock

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from server.app import app, load_state, save_state

def test_retries():
    client = app.test_client()
    
    # 1. Clear state
    state = load_state()
    state["goals"] = {}
    state["tasks"] = {}
    state["workers"] = {}
    save_state(state)

    if not os.environ.get("COURIER_API_KEY"):
        os.environ["COURIER_API_KEY"] = "test-key"
        import server.app
        server.app.API_KEY = "test-key"
        server.app.INSECURE_API_KEYS = set()
    if not os.environ.get("COURIER_VERIFIER_API_KEY"):
        os.environ["COURIER_VERIFIER_API_KEY"] = "verifier-key"
        import server.app
        server.app.VERIFIER_API_KEY = "verifier-key"
    auth_headers = {"Authorization": "Bearer test-key"}
    ver_headers = {"Authorization": "Bearer verifier-key"}

    # Register worker
    res = client.post("/workers/register", json={"worker_id": "test-worker", "capabilities": ["linux"]}, headers=auth_headers)
    assert res.status_code == 200

    def create_task():
        res = client.post("/goals", json={"goal_text": "test", "workflow_plan": [{"target_agent": "linux", "status": "QUEUED"}]}, headers=auth_headers)
        assert res.status_code == 200

    # Test Execution Retries
    print("Testing Execution Retries")
    create_task()
    for attempt in range(5): # initial + 3 retries max
        # Bypass backoff for testing claim
        state = load_state()
        for t in state["tasks"].values():
            t["next_retry_at"] = 0
        for g in state["goals"].values():
            for step in g.get("workflow_plan", []):
                step["next_retry_at"] = 0
        save_state(state)
        
        res = client.post("/tasks/claim", json={"worker_id": "test-worker"}, headers=auth_headers)
        data = res.get_json()
        if attempt < 4:
            assert data.get("task") is not None, f"Failed to claim on attempt {attempt}"
            task_id = data["task"]["task_id"]
            # submit failure
            task = data["task"]
            res = client.post("/tasks/result", json={
                "task_id": task_id, 
                "worker_id": "test-worker", 
                "result_id": f"exec-fail-{attempt}", 
                "status": "FAILED", 
                "stderr": "Error",
                "artifacts": [],
                "attempt_id": task.get("attempt_id") or "",
                "dispatch_id": task.get("dispatch_id") or "",
                "execution_ref": task.get("execution_ref") or "",
                "goal_id": task.get("goal_id") or "",
                "run_id": task.get("run_id") or "run-1"
            }, headers=auth_headers)
            if res.status_code != 200:
                print(f"FAILED with {res.status_code}: {res.get_json()}")
            assert res.status_code == 200
            
            state = load_state()
            print(f"Goal after attempt {attempt}:", state["goals"].get(task["goal_id"]))
        else:
            if data.get("task") is not None:
                state = load_state()
                print("GOAL:", state["goals"].get(data["task"]["goal_id"]))
            assert data.get("task") is None, f"Should not claim after max retries: {data.get('task')}"

    state = load_state()
    task = list(state["tasks"].values())[0]
    assert task["status"] == "FAILED_TERMINAL", f"Expected FAILED_TERMINAL, got {task['status']}"
    assert "MAX_ATTEMPTS_REACHED" in task["blocker"]
    print("PASS: Execution retries bounded")

    # Clear tasks
    state["goals"] = {}
    state["tasks"] = {}
    save_state(state)

    # Test Verification Retries
    print("Testing Verification Retries")
    create_task()
    
    for attempt in range(3): # 2 retries max, 3rd should fail
        state = load_state()
        for t in state["tasks"].values():
            t["next_retry_at"] = 0
        for g in state["goals"].values():
            for step in g.get("workflow_plan", []):
                step["next_retry_at"] = 0
        save_state(state)
        
        # claim
        res = client.post("/tasks/claim", json={"worker_id": "test-worker"}, headers=auth_headers)
        data = res.get_json()
        assert data.get("task") is not None
        task_id = data["task"]["task_id"]
        
        # success result
        task = data["task"]
        artifacts_payload = [{"path": a, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"} for a in task.get("artifacts", [])]
        # must succeed execution first
        res = client.post("/tasks/result", json={
            "task_id": task_id, "worker_id": "test-worker", "result_id": f"exec-succ-{attempt}", "status": "SUCCESS", "artifacts": artifacts_payload,
            "attempt_id": task.get("attempt_id") or "", "dispatch_id": task.get("dispatch_id") or "", "execution_ref": task.get("execution_ref") or "", "goal_id": task.get("goal_id") or "", "run_id": task.get("run_id") or "run-1"
        }, headers=auth_headers)
        if res.status_code != 200:
            print(f"FAILED with {res.status_code}: {res.get_json()}")
        assert res.status_code == 200
        
        # verify fail
        res = client.post("/tasks/verify", json={"task_id": task_id, "verifier_id": "verifier-1", "result_id": f"exec-succ-{attempt}", "artifacts": artifacts_payload, "verdict": "FAIL", "reason": "bad"}, headers=ver_headers)
        if res.status_code != 200:
            print(f"FAILED with {res.status_code}: {res.get_json()}")
        assert res.status_code == 200
        
        state = load_state()
        task = list(state["tasks"].values())[0]
        if attempt < 2:
            assert task["status"] == "QUEUED"
        else:
            assert task["status"] == "FAILED_VERIFICATION"
            assert "VERIFICATION_REJECTED_MAX_RETRIES" in task["blocker"]

    print("PASS: Verification retries bounded")

    # Clear tasks
    state["goals"] = {}
    state["tasks"] = {}
    save_state(state)

    # Test Provider Wait Retries
    print("Testing Provider Wait Retries")
    create_task()
    
    # Claim once
    res = client.post("/tasks/claim", json={"worker_id": "test-worker"}, headers=auth_headers)
    task_id = res.get_json()["task"]["task_id"]
    
    for attempt in range(11): # max 10
        state = load_state()
        task = list(state["tasks"].values())[0]

        if attempt > 0:
            res_resume = client.post(f"/tasks/{task_id}/resume", json={"worker_id": "test-worker"}, headers=auth_headers)
            if res_resume.status_code != 200:
                print(f"RESUME FAILED: {res_resume.status_code} {res_resume.get_json()}")
            assert res_resume.status_code == 200

        res = client.post(f"/tasks/{task_id}/provider_wait", json={"worker_id": "test-worker", "wait_type": "WAITING_PROVIDER"}, headers=auth_headers)
        if res.status_code != 200:
            print(f"FAILED with {res.status_code}: {res.get_json()}")
        if attempt < 10:
            assert res.status_code == 200
            assert res.get_json()["status"] == "WAITING_PROVIDER"
        else:
            assert res.status_code == 200
            assert res.get_json()["status"] == "FAILED_TERMINAL"
            assert "MAX_PROVIDER_WAITS_REACHED" in res.get_json()["blocker"]
            
    print("PASS: Provider wait retries bounded")

    # Clear tasks
    state["goals"] = {}
    state["tasks"] = {}
    save_state(state)

    # Test Transport Retries
    print("Testing Transport Retries")
    create_task()
    
    res = client.post("/tasks/claim", json={"worker_id": "test-worker"}, headers=auth_headers)
    task_id = res.get_json()["task"]["task_id"]

    for attempt in range(6): # max 5
        # Set to BLOCKED_TRANSIENT to allow transport retry
        state = load_state()
        task = state["tasks"][task_id]
        task["status"] = "BLOCKED_TRANSIENT"
        for step in state["goals"][task["goal_id"]]["workflow_plan"]:
            if step["task_id"] == task_id:
                step["status"] = "BLOCKED_TRANSIENT"
        save_state(state)

        res = client.post(f"/tasks/{task_id}/resume", json={"action": "retry"}, headers=auth_headers)
        if res.status_code != 200 and attempt < 5:
            print(f"RESUME FAILED: {res.status_code} {res.get_json()}")
        if attempt < 5:
            assert res.status_code == 200
            assert res.get_json()["status"] == "RESUMED"
        else:
            assert res.status_code == 400
            assert "Max transport retries reached" in res.get_json()["error"]
            
    state = load_state()
    task = list(state["tasks"].values())[0]
    assert task["status"] == "FAILED_TERMINAL"
    print("PASS: Transport retries bounded")

    print("ALL TESTS PASSED")

if __name__ == "__main__":
    test_retries()
