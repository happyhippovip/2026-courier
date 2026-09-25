import pytest
import copy
import os
os.environ["COURIER_API_KEY"] = "test-secret"
os.environ["COURIER_VERIFIER_API_KEY"] = "verifier-secret"

from server import app as server_app

def auth():
    return {"Authorization": "Bearer test-secret"}

def test_manual():
    motor = server_app.app.test_client()
    
    server_app.API_KEY = "test-secret"
    motor.post("/workers/register", headers=auth(), json={"worker_id": "W1", "platform": "test", "capabilities": ["linux"]})
    
    goal = motor.post("/goals", headers=auth(), json={"goal_text": "Binding test", "workflow_plan": [
        {"task_id": "T1", "target_agent": "linux", "instruction": "Do T1"},
        {"task_id": "T2", "target_agent": "linux", "instruction": "Do T2"}
    ]})
    goal_id = goal.get_json()["goal_id"]

    c1 = motor.post("/tasks/claim", headers=auth(), json={"worker_id": "W1"})
    task1 = c1.get_json().get("task")

    base_payload = {
        "worker_id": "W1",
        "task_id": task1["task_id"],
        "status": "SUCCESS",
        "artifacts": [{"path": "relative_evidence1.txt", "sha256": "a" * 64}],
        "attempt_id": task1["attempt_id"],
        "dispatch_id": task1["dispatch_id"],
        "execution_ref": task1["execution_ref"],
        "goal_id": task1["goal_id"],
        "run_id": "run-1",
        "runtime_identity": task1["server_binding"]
    }
    
    from scripts.integration_contract import _canonical_hash
    identity = dict(base_payload)
    base_payload["result_id"] = f"result-{_canonical_hash(identity)}"

    r1 = motor.post("/tasks/result", headers=auth(), json=base_payload)
    print("r1 status:", r1.status_code)

    c2 = motor.post("/tasks/claim", headers=auth(), json={"worker_id": "W1"})
    task2 = c2.get_json().get("task")
    
    print("task2:", task2)

    p2 = copy.deepcopy(base_payload)
    if task2:
        p2["task_id"] = task2["task_id"]
        p2["attempt_id"] = task2["attempt_id"]
        p2["dispatch_id"] = task2["dispatch_id"]
        p2["execution_ref"] = task2["execution_ref"]
        p2["runtime_identity"] = task2["server_binding"]
        
        # WHAT DOES THE HASH SAY?
        identity2 = dict(p2)
        expected_result_id = f"result-{_canonical_hash(identity2)}"
        print("Expected result id for p2:", expected_result_id)
        print("Actual result id in p2:", p2["result_id"])

        r2 = motor.post("/tasks/result", headers=auth(), json=p2)
        print("r2 status:", r2.status_code)
        print("r2 text:", r2.get_data(as_text=True))

if __name__ == "__main__":
    test_manual()
