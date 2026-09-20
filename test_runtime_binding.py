import pytest, requests, time, uuid, json

API_URL = "http://localhost:8099"
HEADERS = {"Authorization": "Bearer TEST_API_KEY"}
VERIFIER_HEADERS = {"Authorization": "Bearer TEST_VERIFIER_KEY"}

def test_runtime_binding():
    import os
    os.system("python3 sweep_queue.py")
    requests.post(f"{API_URL}/workers/register", json={"worker_id": "W6", "capabilities": ["solaris"]}, headers=HEADERS)

    res = requests.post(f"{API_URL}/goals", json={"goal_text": "hello", "workflow_plan": [{"task_id": uuid.uuid4().hex, "capabilities": ["solaris"], "target_agent": "solaris", "instruction": "Test"}]}, headers=HEADERS)
    print("GOALS:", res.json())
    goal_id = res.json()["goal_id"]
    time.sleep(1)
    
    res = requests.post(f"{API_URL}/tasks/claim", json={"worker_id": "W6", "capabilities": ["solaris"]}, headers=HEADERS)
    task = res.json().get("task")
    print("CLAIM:", task)
    if not task:
        return
    task_id = task["task_id"]
    server_binding = task["server_binding"]
    
    result = {
        "goal_id": task["goal_id"],
        "task_id": task_id,
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "worker_id": "W6",
        "run_id": "run-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": []
    }
    res = requests.post(f"{API_URL}/tasks/result", json={"worker_id": "W6", "task_id": task_id, "status": "SUCCESS", **result}, headers=HEADERS)
    if res.status_code != 200:
        print("RESULT FAIL:", res.text)
        return

    verify_payload = {
        "task_id": task_id,
        "verifier_id": "V1",
        "result_id": "res-1",
        "verdict": "PASS",
        "artifacts": []
    }
    
    res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS)
    assert res.status_code == 400 and "missing runtime identity" in res.json()["error"]
    
    verify_payload["received_runtime_identity"] = {"sha": "fake", "runtime": "fake"}
    res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS)
    assert res.status_code == 400 and "runtime identity mismatch" in res.json()["error"]
    
    verify_payload["received_runtime_identity"] = server_binding
    verify_payload["artifacts"] = [{"path": "b.txt", "sha256": "def"}]
    res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS)
    assert res.status_code == 400 and "artifact evidence mismatch" in res.json()["error"]
    
    verify_payload["artifacts"] = result["artifacts"]
    res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS)
    assert res.status_code == 200
    
    verify_payload["result_id"] = "res-2"
    res = requests.post(f"{API_URL}/tasks/verify", json=verify_payload, headers=VERIFIER_HEADERS)
    assert res.status_code == 409
    
    print("ALL RUNTIME BINDING TESTS PASSED")

test_runtime_binding()
