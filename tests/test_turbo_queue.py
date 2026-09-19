from scripts.integration_contract import _canonical_hash
import pytest
import os
import tempfile
from pathlib import Path

@pytest.fixture
def app_state(monkeypatch):
    import server.app
    temp_dir = tempfile.mkdtemp()
    state_file = Path(temp_dir) / "central_state.json"
    monkeypatch.setattr(server.app, "STATE_FILE", str(state_file))
    
    server.app.app.config['TESTING'] = True
    with server.app.app.test_client() as client:
        yield client

def test_turbo_queue_parallel_fixture_state(app_state):
    import server.app
    server.app.API_KEY = "test"
    auth = {"Authorization": "Bearer test"}
    r1 = app_state.post("/workers/register", json={"worker_id": "w1", "capabilities": ["mock"]}, headers=auth)
    w1_id = "w1"
    
    r2 = app_state.post("/workers/register", json={"worker_id": "w2", "capabilities": ["mock"]}, headers=auth)
    w2_id = "w2"

    goal_data = {
        "goal_text": "Turbo test",
        "workflow_plan": [
            {"task_id": "A", "target_agent": "mock", "instruction": "Do A"},
            {"task_id": "B", "target_agent": "mock", "instruction": "Do B"},
            {"task_id": "C", "target_agent": "mock", "instruction": "Do C", "depends_on": ["A", "B"]}
        ]
    }
    app_state.post("/goals", json=goal_data, headers=auth)

    # In server/app.py claim_task(), worker claims ONE task.
    t1 = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth).json.get("task")
    t2 = app_state.post("/tasks/claim", json={"worker_id": w2_id}, headers=auth).json.get("task")

    assert t1 is not None
    assert t2 is not None
    assert set([t1["task_id"], t2["task_id"]]) == {"A", "B"}
    
    # Finish A
    state = server.app.load_state()
    state["tasks"]["A"]["status"] = "RECONCILED"
    state["goals"][t1["goal_id"]]["workflow_plan"][0]["status"] = "RECONCILED"
    # Also free up worker 1
    state["workers"]["w1"]["current_task"] = None
    state["workers"]["w1"]["available"] = True
    server.app.save_state(state)
    
    # Claim with w1 -> Should be None because C is blocked by B
    t3 = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth).json.get("task")
    assert t3 is None, "C should wait for B to finish"

    # Finish B
    state = server.app.load_state()
    state["tasks"]["B"]["status"] = "RECONCILED"
    state["goals"][t1["goal_id"]]["workflow_plan"][1]["status"] = "RECONCILED"
    server.app.save_state(state)

    # Claim with w1 -> Should be C
    t_c = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth).json.get("task")
    assert t_c is not None
    assert t_c["task_id"] == "C"



def test_turbo_queue_integration_api_path(app_state):
    import server.app
    server.app.API_KEY = "test"
    server.app.VERIFIER_API_KEY = "test_verifier"
    
    auth_worker = {"Authorization": "Bearer test"}
    auth_verifier = {"Authorization": "Bearer test_verifier"}
    
    r1 = app_state.post("/workers/register", json={"worker_id": "w1", "capabilities": ["mock"]}, headers=auth_worker)
    assert r1.status_code == 200
    w1_id = "w1"
    
    r2 = app_state.post("/workers/register", json={"worker_id": "w2", "capabilities": ["mock"]}, headers=auth_worker)
    assert r2.status_code == 200
    w2_id = "w2"

    goal_data = {
        "goal_text": "Turbo API test",
        "workflow_plan": [
            {"task_id": "A2", "target_agent": "mock", "instruction": "Do A2"},
            {"task_id": "B2", "target_agent": "mock", "instruction": "Do B2"},
            {"task_id": "C2", "target_agent": "mock", "instruction": "Do C2", "depends_on": ["A2", "B2"]}
        ]
    }
    r = app_state.post("/goals", json=goal_data, headers=auth_worker)
    assert r.status_code == 200

    # Claim A2 and B2
    t1_res = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth_worker)
    t1 = t1_res.json.get("task")
    t2_res = app_state.post("/tasks/claim", json={"worker_id": w2_id}, headers=auth_worker)
    t2 = t2_res.json.get("task")

    assert t1 is not None and t2 is not None
    assert set([t1["task_id"], t2["task_id"]]) == {"A2", "B2"}

    # Submit Result for t1
    result_A = {
        "goal_id": t1["goal_id"],
        "task_id": t1["task_id"],
        "attempt_id": t1["attempt_id"],
        "dispatch_id": t1["dispatch_id"],
        "execution_ref": t1["execution_ref"],
        "worker_id": w1_id,
        "run_id": "r1",
        "status": "SUCCESS",
        "artifacts": [],
        "runtime_identity": t1.get("server_binding")
    }
    result_A["result_id"] = f"result-{_canonical_hash(result_A)}"
    r = app_state.post(f"/tasks/result", json=result_A, headers=auth_worker)
    assert r.status_code == 200

    # Submit Result for t2
    result_B = {
        "goal_id": t2["goal_id"],
        "task_id": t2["task_id"],
        "attempt_id": t2["attempt_id"],
        "dispatch_id": t2["dispatch_id"],
        "execution_ref": t2["execution_ref"],
        "worker_id": w2_id,
        "run_id": "r2",
        "status": "SUCCESS",
        "artifacts": [],
        "runtime_identity": t2.get("server_binding")
    }
    result_B["result_id"] = f"result-{_canonical_hash(result_B)}"
    r = app_state.post(f"/tasks/result", json=result_B, headers=auth_worker)
    assert r.status_code == 200
    
    # Try an INVALID verify (using producer key instead of verifier key)
    verify_invalid_payload = {
        "task_id": t1["task_id"],
        "verifier_id": "v1",
        "result_id": "res_A2",
        "artifacts": [],
        "verdict": "PASS",
        "received_runtime_identity": t1.get("server_binding")
    }
    r = app_state.post(f"/tasks/verify", json=verify_invalid_payload, headers=auth_worker)
    assert r.status_code == 401
    assert "Verifier authority required" in r.json.get("error", "")

    # Try an INVALID verify (missing runtime identity)
    verify_missing_runtime = {
        "task_id": t1["task_id"],
        "verifier_id": "v1",
        "result_id": "res_A2",
        "artifacts": [],
        "verdict": "PASS"
    }
    r = app_state.post(f"/tasks/verify", json=verify_missing_runtime, headers=auth_verifier)
    assert r.status_code == 400
    assert "missing runtime identity" in r.json.get("error", "")

    # VALID verify for t1
    verify_valid_A = {
        "task_id": t1["task_id"],
        "verifier_id": "v1",
        "result_id": "res_A2",
        "artifacts": [],
        "verdict": "PASS",
        "received_runtime_identity": t1.get("server_binding")
    }
    r = app_state.post(f"/tasks/verify", json=verify_valid_A, headers=auth_verifier)
    assert r.status_code == 200
    
    # After A is verified, w1 asks for task. C should NOT be returned because B is not verified yet.
    r = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth_worker)
    assert r.status_code == 200
    t3 = r.json.get("task")
    assert t3 is None, "C2 should wait for B2"
    
    # VALID verify for t2
    verify_valid_B = {
        "task_id": t2["task_id"],
        "verifier_id": "v2",
        "result_id": "res_B2",
        "artifacts": [],
        "verdict": "PASS",
        "received_runtime_identity": t2.get("server_binding")
    }
    r = app_state.post(f"/tasks/verify", json=verify_valid_B, headers=auth_verifier)
    assert r.status_code == 200
    
    # Now w1 can claim C
    r = app_state.post("/tasks/claim", json={"worker_id": w1_id}, headers=auth_worker)
    assert r.status_code == 200
    t_c = r.json.get("task")
    assert t_c is not None
    assert t_c["task_id"] == "C2"

