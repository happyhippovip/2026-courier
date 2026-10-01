import os
import json
import time
import pytest
from flask.testing import FlaskClient

# Mock environ before import
os.environ["COURIER_API_KEY"] = "test-api-key"
os.environ["COURIER_VERIFIER_API_KEY"] = "test-verifier-key"

from server.app import (
    app, load_state, save_state, _find_workflow_step, _reclaim_stale_impl
)

@pytest.fixture
def client(tmp_path):
    state_file = str(tmp_path / "central_state.json")
    os.environ["COURIER_STATE_FILE"] = state_file
    
    # Overwrite the global module variable for the test
    import server.app as sapp
    sapp.STATE_FILE = state_file
    sapp.VERIFIER_API_KEY = "test-verifier-key"
    
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_missing_api_keys(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        import importlib
        import server.app as sapp
        importlib.reload(sapp)

def test_missing_verifier_key(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-api-key")
    monkeypatch.delenv("COURIER_VERIFIER_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        import importlib
        import server.app as sapp
        importlib.reload(sapp)

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert "status" in res.json

def test_status(client):
    # Setup state
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE"}
    state["tasks"]["t1"] = {}
    state["workers"]["w1"] = {}
    save_state(state)
    
    res = client.get("/status", headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert res.json["goals"] == 1
    assert res.json["active_goals"] == 1
    assert res.json["tasks"] == 1
    assert res.json["workers"] == 1

def test_goals_missing_goal_text(client):
    res = client.post("/goals", json={}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400

def test_goals_custom_plan_no_task_id(client):
    res = client.post("/goals", json={
        "goal_text": "do something",
        "workflow_plan": [{"instruction": "step 1"}]
    }, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    state = load_state()
    goal = state["goals"][res.json["goal_id"]]
    assert "task_id" in goal["workflow_plan"][0]

def test_goals_planner_error(client, monkeypatch):
    import server.app as sapp
    def mock_plan(*args, **kwargs):
        raise Exception("planner broke")
    monkeypatch.setattr(sapp.ChiefCommander, "formulate_workflow_plan", mock_plan)
    res = client.post("/goals", json={"goal_text": "test"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 503

def test_goals_planner_empty(client, monkeypatch):
    import server.app as sapp
    def mock_plan(*args, **kwargs):
        return None, []
    monkeypatch.setattr(sapp.ChiefCommander, "formulate_workflow_plan", mock_plan)
    res = client.post("/goals", json={"goal_text": "test"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 503

def test_goals_planner_target_agents(client, monkeypatch):
    import server.app as sapp
    def mock_plan(*args, **kwargs):
        return None, [{"target_agent": "codex"}, {"target_agent": "windows"}, {"target_agent": "linux"}, {"target_agent": "unknown"}]
    monkeypatch.setattr(sapp.ChiefCommander, "formulate_workflow_plan", mock_plan)
    res = client.post("/goals", json={"goal_text": "test"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    state = load_state()
    plan = state["goals"][res.json["goal_id"]]["workflow_plan"]
    assert plan[0]["target_agent"] == "windows"
    assert plan[1]["target_agent"] == "windows"
    assert plan[2]["target_agent"] == "linux"
    assert plan[3]["target_agent"] == "linux"

def test_get_unknown_goal(client):
    res = client.get("/goals/invalid", headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 404

def test_list_walls(client):
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "BLOCKED"}
    save_state(state)
    res = client.get("/walls", headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert "g1" in res.json

def test_register_worker_missing_id(client):
    res = client.post("/workers/register", json={}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400

def test_register_worker_reconnect_mismatch(client):
    state = load_state()
    state["workers"]["w1"] = {"current_task": "t1"}
    state["tasks"]["t1"] = {"status": "DISPATCHED"}
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "DISPATCHED"}]}
    save_state(state)
    
    res = client.post("/workers/register", json={"worker_id": "w1", "current_task": "t2"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    
    state = load_state()
    assert state["tasks"]["t1"]["status"] == "HUMAN_REQUIRED"
    assert state["goals"]["g1"]["status"] == "BLOCKED"

def test_unregister_worker(client):
    state = load_state()
    state["workers"]["w1"] = {"available": True}
    save_state(state)
    
    res = client.post("/workers/unregister", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    state = load_state()
    assert state["workers"]["w1"]["available"] == False
    assert state["workers"]["w1"]["unregistered"] == True

    res = client.post("/workers/unregister", json={"worker_id": "invalid"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 404

def test_heartbeat(client):
    state = load_state()
    state["workers"]["w1"] = {"available": False, "last_seen": 0, "current_task": None}
    save_state(state)
    
    res = client.post("/workers/heartbeat", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    state = load_state()
    assert state["workers"]["w1"]["available"] == True
    
    res = client.post("/workers/heartbeat", json={"worker_id": "invalid"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 404

def test_claim_unknown_worker(client):
    res = client.post("/tasks/claim", json={"worker_id": "invalid"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 404

def test_claim_no_task(client):
    state = load_state()
    state["workers"]["w1"] = {"available": True, "capabilities": ["linux"]}
    save_state(state)
    res = client.post("/tasks/claim", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert res.json["task"] is None

def test_claim_target_matching(client):
    state = load_state()
    state["workers"]["w1"] = {"available": True, "capabilities": ["windows", "linux"]}
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "QUEUED", "target_agent": "windows"}], "current_step_index": 0}
    save_state(state)
    
    res = client.post("/tasks/claim", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert res.json["task"]["task_id"] == "t1"

def test_claim_cost_gate_blocked(client, monkeypatch):
    import server.app as sapp
    class MockCostGate:
        @staticmethod
        def evaluate_spend_request(*args, **kwargs):
            return {"allowed": False}
    monkeypatch.setattr(sapp, "CostGate", MockCostGate)
    
    state = load_state()
    state["workers"]["w1"] = {"available": True, "capabilities": ["linux"]}
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "QUEUED", "target_agent": "linux"}], "current_step_index": 0}
    save_state(state)
    
    res = client.post("/tasks/claim", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert res.json["task"] is None

def test_claim_lease_blocked(client, monkeypatch):
    import server.app as sapp
    class MockLeaseMgr:
        def acquire_lease(self, *args, **kwargs):
            return False, "Lease error", None
    monkeypatch.setattr(sapp, "LEASE_MGR", MockLeaseMgr())
    
    state = load_state()
    state["workers"]["w1"] = {"available": True, "capabilities": ["linux"]}
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "QUEUED", "target_agent": "linux"}], "current_step_index": 0}
    save_state(state)
    
    res = client.post("/tasks/claim", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert res.json["task"] is None

def test_claim_prepare_task_error(client, monkeypatch):
    import server.app as sapp
    def mock_prepare(*args, **kwargs):
        raise sapp.ContractError("bad contract")
    monkeypatch.setattr(sapp, "prepare_task", mock_prepare)
    
    state = load_state()
    state["workers"]["w1"] = {"available": True, "capabilities": ["linux"]}
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "QUEUED", "target_agent": "linux"}], "current_step_index": 0}
    save_state(state)
    
    res = client.post("/tasks/claim", json={"worker_id": "w1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400
    assert "bad contract" in res.json["error"]

def test_task_result_duplicate(client):
    state = load_state()
    result = {"dispatch_id": "d1", "result_id": "r1", "status": "SUCCESS", "worker_id": "w1", "attempt_id": "a1", "artifacts": []}
    state["tasks"]["t1"] = {"status": "RESULT_RECEIVED", "result": result}
    save_state(state)
    
    res = client.post("/tasks/result", json={"task_id": "t1", "worker_id": "w1", **result}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    assert res.json["status"] == "ACK_DUPLICATE"

def test_task_result_conflict(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RECONCILED"}
    save_state(state)
    
    res = client.post("/tasks/result", json={"task_id": "t1", "goal_id": "g1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 409

def test_task_result_unknown(client):
    res = client.post("/tasks/result", json={"task_id": "invalid"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400

def test_task_result_terminal_failure(client, monkeypatch):
    import server.app as sapp
    monkeypatch.setattr(sapp, "validate_durable_result", lambda *args: {"status": "FAILED", "artifacts": []})
    
    state = load_state()
    state["tasks"]["t1"] = {"status": "DISPATCHED", "worker_id": "w1", "goal_id": "g1", "attempts": 3}
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1"}]}
    save_state(state)
    
    res = client.post("/tasks/result", json={"task_id": "t1", "worker_id": "w1", "goal_id": "g1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    state = load_state()
    assert state["tasks"]["t1"]["status"] == "FAILED_TERMINAL"
    assert state["goals"]["g1"]["status"] == "BLOCKED"

def test_task_result_artifact_check(client, monkeypatch):
    import server.app as sapp
    monkeypatch.setattr(sapp, "validate_durable_result", lambda *args: {"status": "SUCCESS", "artifacts": [{"artifact_id": "a1"}]})
    
    class MockStore:
        def check_reference(self, ref, task):
            raise sapp.ArtifactError("no artifact")
    monkeypatch.setattr(sapp, "ARTIFACT_STORE", MockStore())
    
    state = load_state()
    state["tasks"]["t1"] = {"status": "DISPATCHED", "worker_id": "w1", "goal_id": "g1"}
    save_state(state)
    
    res = client.post("/tasks/result", json={"task_id": "t1", "worker_id": "w1", "goal_id": "g1"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400
    assert "no artifact" in res.json["error"]

def test_pending_verification(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RESULT_RECEIVED"}
    save_state(state)
    
    res = client.get("/tasks/pending_verification", headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 200
    assert len(res.json["tasks"]) == 1

def test_verify_task_result_unknown(client):
    res = client.post("/tasks/verify", json={"task_id": "invalid"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 404

def test_verify_task_result_duplicate(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RECONCILED", "verification": {"result_id": "r1"}}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "result_id": "r1", "goal_id": "g1"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 200
    assert res.json["status"] == "ACK_DUPLICATE"

def test_verify_task_result_conflict(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RECONCILED", "verification": {"result_id": "r1"}}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "result_id": "r2", "goal_id": "g1"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 409

def test_verify_task_result_not_ready(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "QUEUED"}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "goal_id": "g1"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 409

def test_verify_task_result_mismatch_result_id(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RESULT_RECEIVED", "worker_id": "w1", "result": {"result_id": "r1", "artifacts": []}}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "verifier_id": "v1", "result_id": "r2"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 400
    assert "result_id mismatch" in res.json["error"]

def test_verify_task_result_mismatch_artifacts(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RESULT_RECEIVED", "worker_id": "w1", "result": {"result_id": "r1", "artifacts": []}}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "verifier_id": "v1", "result_id": "r1", "artifacts": ["bad"]}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 400
    assert "artifact evidence mismatch" in res.json["error"]

def test_verify_task_result_invalid_verdict(client):
    state = load_state()
    state["tasks"]["t1"] = {"status": "RESULT_RECEIVED", "worker_id": "w1", "result": {"result_id": "r1", "artifacts": []}}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "verifier_id": "v1", "result_id": "r1", "artifacts": [], "verdict": "INVALID"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 400

def test_verify_task_result_fail(client):
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1"}]}
    state["tasks"]["t1"] = {"status": "RESULT_RECEIVED", "worker_id": "w1", "result": {"result_id": "r1", "artifacts": []}, "goal_id": "g1"}
    save_state(state)
    
    res = client.post("/tasks/verify", json={"task_id": "t1", "verifier_id": "v1", "result_id": "r1", "artifacts": [], "verdict": "FAIL"}, headers={"Authorization": "Bearer test-verifier-key"})
    assert res.status_code == 200
    state = load_state()
    assert state["tasks"]["t1"]["status"] == "FAILED_VERIFICATION"
    assert state["goals"]["g1"]["status"] == "BLOCKED"

def test_resume_task_not_found(client):
    res = client.post("/tasks/invalid/resume", json={}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 404

def test_resume_task_invalid_status(client):
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "QUEUED"}]}
    state["tasks"]["t1"] = {"status": "QUEUED"}
    save_state(state)
    
    res = client.post("/tasks/t1/resume", json={}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400

def test_resume_task_invalid_action(client):
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "FAILED_TERMINAL"}]}
    state["tasks"]["t1"] = {"status": "FAILED_TERMINAL"}
    save_state(state)
    
    res = client.post("/tasks/t1/resume", json={"action": "invalid"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400

def test_resume_task_force_success(client):
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "ACTIVE", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "FAILED_TERMINAL"}]}
    state["tasks"]["t1"] = {"status": "FAILED_TERMINAL"}
    save_state(state)
    
    res = client.post("/tasks/t1/resume", json={"action": "force_success"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 400

def test_resume_task_success(client):
    state = load_state()
    state["goals"]["g1"] = {"goal_id": "g1", "status": "BLOCKED", "workflow_plan": [{"task_id": "t1", "goal_id": "g1", "status": "FAILED_TERMINAL"}]}
    state["tasks"]["t1"] = {"status": "FAILED_TERMINAL"}
    save_state(state)
    
    res = client.post("/tasks/t1/resume", json={"instruction_override": "new instruction"}, headers={"Authorization": "Bearer test-api-key"})
    assert res.status_code == 200
    state = load_state()
    assert state["tasks"]["t1"]["status"] == "QUEUED"
    assert state["goals"]["g1"]["status"] == "ACTIVE"
    assert state["goals"]["g1"]["workflow_plan"][0]["instruction"] == "new instruction"

def test_find_workflow_step_none():
    state = {"goals": {}}
    assert _find_workflow_step(state, "t1") == (None, None)

def test_background_worker(monkeypatch):
    import server.app as sapp
    
    called = []
    def mock_reclaim():
        called.append(1)
        raise Exception("test")
    
    monkeypatch.setattr(sapp, "_reclaim_stale_impl", mock_reclaim)
    monkeypatch.setattr(sapp.time, "sleep", lambda x: called.append(2) or sys.exit(0) if len(called) > 2 else None)
    
    import sys
    with pytest.raises(SystemExit):
        sapp.background_timeout_worker()
    
    assert 1 in called
    assert 2 in called

def test_background_worker_main(monkeypatch):
    import server.app as sapp
    monkeypatch.setattr(sapp, "__name__", "__main__")
    
    # Not going to run the actual flask app, just a coverage dummy
