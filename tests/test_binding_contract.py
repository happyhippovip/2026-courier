import pytest
import copy
from server import app as server_app
from scripts.integration_contract import _canonical_hash

def auth():
    return {"Authorization": "Bearer test-secret"}

def v_auth():
    return {"Authorization": "Bearer verifier-secret"}

@pytest.fixture
def motor(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    monkeypatch.setenv("COURIER_STRICT_HASH", "1")
    return server_app.app.test_client()

def test_binding_contract(motor):
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
    identity = dict(base_payload)
    base_payload["result_id"] = f"result-{_canonical_hash(identity)}"

    payload_bad_task = copy.deepcopy(base_payload)
    payload_bad_task["task_id"] = "T2"
    assert motor.post("/tasks/result", headers=auth(), json=payload_bad_task).json.get("status") == "IGNORED"

    payload_bad_attempt = copy.deepcopy(base_payload)
    payload_bad_attempt["attempt_id"] = "bad-attempt"
    assert motor.post("/tasks/result", headers=auth(), json=payload_bad_attempt).status_code == 400

    r1 = motor.post("/tasks/result", headers=auth(), json=base_payload)
    assert r1.status_code == 200

    v_base = {
        "task_id": task1["task_id"], 
        "verdict": "PASS", 
        "received_runtime_identity": task1["server_binding"], 
        "verifier_id": "V1", 
        "result_id": base_payload["result_id"], 
        "artifacts": base_payload["artifacts"]
    }

    v_bad_runtime = copy.deepcopy(v_base)
    v_bad_runtime["received_runtime_identity"] = {"forged": "runtime"}
    assert motor.post("/tasks/verify", headers=v_auth(), json=v_bad_runtime).status_code == 400

    v_bad_art = copy.deepcopy(v_base)
    v_bad_art["artifacts"] = [{"path": "relative_evidence1.txt", "sha256": "b" * 64}]
    assert motor.post("/tasks/verify", headers=v_auth(), json=v_bad_art).status_code == 400

    c2 = motor.post("/tasks/claim", headers=auth(), json={"worker_id": "W1"})
    task2 = c2.get_json().get("task")
    p2 = copy.deepcopy(base_payload)
    p2["task_id"] = task2["task_id"]
    p2["attempt_id"] = task2["attempt_id"]
    p2["dispatch_id"] = task2["dispatch_id"]
    p2["execution_ref"] = task2["execution_ref"]
    p2["runtime_identity"] = task2["server_binding"]
    
    # Cross task evidence!
    # If we don't update result_id, the server should reject it because result_id is mathematically bound!
    r2 = motor.post("/tasks/result", headers=auth(), json=p2)
    assert r2.status_code == 400 # NOW IT REJECTS IT!

    r_v = motor.post("/tasks/verify", headers=v_auth(), json=v_base)
    assert r_v.status_code == 200

    r_dup = motor.post("/tasks/verify", headers=v_auth(), json=v_base)
    assert r_dup.status_code == 200
    assert r_dup.get_json()["status"] == "ACK_DUPLICATE"

