"""Server idempotency/verification fixes (from claude/keen-gates-8miu4n), exercised
through the P3 cutover patch series in a temp copy of server/app.py."""
import subprocess
from pathlib import Path

import pytest

from p3_preview import PATCHES, VERIFIER, WORKER, load_patched_server


@pytest.fixture
def srv(tmp_path, monkeypatch):
    return load_patched_server(tmp_path, monkeypatch)


def setup_claimed_task(srv):
    http = srv.app.test_client()
    worker = {"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]}
    assert http.post("/workers/register", headers=WORKER, json=worker).status_code == 200
    goal = http.post("/goals", headers=WORKER, json={
        "goal_text": "one bounded task",
        "workflow_plan": [{"task_id": "task-1", "target_agent": "mac",
                           "instruction": "create bounded.txt", "artifacts": ["bounded.txt"]}],
    }).get_json()
    task = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "MAC-01"}).get_json()["task"]
    return http, goal["goal_id"], task


def durable_result(task):
    return {field: task[field] for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")} | {
        "run_id": "run-1", "result_id": "result-1", "status": "SUCCESS",
        "artifacts": [{"path": "bounded.txt", "sha256": "a" * 64}]}


def verify(http, task, result, verdict):
    return http.post("/tasks/verify", headers=VERIFIER, json={
        "task_id": task["task_id"], "result_id": result["result_id"], "verifier_id": "VERIFIER-01",
        "verdict": verdict, "artifacts": result["artifacts"]})





def test_verification_outcome_is_mirrored_into_workflow_step(srv):
    http, goal_id, task = setup_claimed_task(srv)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200
    assert verify(http, task, result, "PASS").status_code == 200
    assert srv.load_state()["goals"][goal_id]["workflow_plan"][0]["status"] == "RECONCILED"


def test_failed_verification_can_be_resumed_with_new_attempt(srv):
    http, goal_id, task = setup_claimed_task(srv)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200
    assert verify(http, task, result, "FAIL").get_json()["status"] == "FAILED_VERIFICATION"
    assert http.post(f"/tasks/{task['task_id']}/resume", headers=WORKER, json={"action": "retry"}).status_code == 200
    state = srv.load_state()
    assert state["goals"][goal_id]["status"] == "ACTIVE"
    assert state["tasks"][task["task_id"]]["status"] == "QUEUED"
    retried = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "MAC-01"}).get_json()["task"]
    assert retried["attempt_id"] == "task-1:attempt:2" and retried["dispatch_id"] != task["dispatch_id"]
    # The superseded attempt's result can no longer bind to the task.
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 400


def test_resume_cannot_force_success_without_bound_evidence(srv):
    http, goal_id, task = setup_claimed_task(srv)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200
    assert verify(http, task, result, "FAIL").status_code == 200
    forced = http.post(f"/tasks/{task['task_id']}/resume", headers=WORKER, json={"action": "force_success"})
    assert forced.status_code == 400
    state = srv.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "FAILED_VERIFICATION"
    assert state["goals"][goal_id]["workflow_plan"][0]["status"] == "FAILED_VERIFICATION"


def test_resume_route_is_registered_when_run_as_script(srv):
    source = Path(srv.__file__).read_text(encoding="utf-8")
    assert source.index("def resume_task") < source.index('if __name__ == "__main__":')


def test_resent_result_is_acknowledged_idempotently(srv):
    http, _, task = setup_claimed_task(srv)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200
    resent = http.post("/tasks/result", headers=WORKER, json=result)
    assert resent.status_code == 200 and resent.get_json()["status"] == "ACK_DUPLICATE"


def test_conflicting_result_for_processed_task_is_rejected(srv):
    http, _, task = setup_claimed_task(srv)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200
    assert http.post("/tasks/result", headers=WORKER, json=dict(result, result_id="result-other")).status_code == 409
    assert srv.load_state()["tasks"][task["task_id"]]["result"]["result_id"] == "result-1"


def test_resent_failed_result_is_acknowledged_after_requeue(srv):
    http, _, task = setup_claimed_task(srv)
    failed = dict(durable_result(task), status="FAILED", artifacts=[])
    assert http.post("/tasks/result", headers=WORKER, json=failed).status_code == 200
    resent = http.post("/tasks/result", headers=WORKER, json=failed)
    assert resent.status_code == 200 and resent.get_json()["status"] == "ACK_DUPLICATE"
    state = srv.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "QUEUED"
    assert state["tasks"][task["task_id"]]["attempts"] == 1


def test_unregistered_worker_stays_stopped_despite_heartbeat(srv):
    http = srv.app.test_client()
    worker = {"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]}
    assert http.post("/workers/register", headers=WORKER, json=worker).status_code == 200
    http.post("/goals", headers=WORKER, json={
        "goal_text": "must not run on a stopped worker",
        "workflow_plan": [{"task_id": "task-stop", "target_agent": "mac", "artifacts": ["x.txt"]}]})
    assert http.post("/workers/unregister", headers=WORKER, json={"worker_id": "MAC-01"}).status_code == 200
    assert http.post("/workers/heartbeat", headers=WORKER, json={"worker_id": "MAC-01"}).status_code == 200
    assert http.post("/tasks/claim", headers=WORKER, json={"worker_id": "MAC-01"}).get_json()["task"] is None
    assert srv.load_state()["tasks"] == {}
    # An explicit re-registration is the only way back into service.
    assert http.post("/workers/register", headers=WORKER, json=worker).status_code == 200
    claimed = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "MAC-01"}).get_json()["task"]
    assert claimed["task_id"] == "task-stop"

def test_task_result_persists_exact_timestamp_ordering_fields(srv):
    http, goal_id, task = setup_claimed_task(srv)
    assert "dispatched_at" in srv.load_state()["tasks"][task["task_id"]]
    
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200
    
    state = srv.load_state()
    assert "received_at" in state["tasks"][task["task_id"]]["result"]
    
    verify(http, task, result, "PASS")
    state = srv.load_state()
    assert "verified_at" in state["tasks"][task["task_id"]]["verification"]

def test_resume_task_in_invalid_status_is_rejected(srv):
    http, goal_id, task = setup_claimed_task(srv)
    # The task is DISPATCHED, which is invalid for resume
    resp = http.post(f"/tasks/{task['task_id']}/resume", headers=WORKER, json={"action": "retry"})
    assert resp.status_code == 400
    assert "cannot be resumed from status DISPATCHED" in resp.get_json()["error"]

def test_create_goal_rejects_duplicate_task_ids(srv):
    http, goal_id, task = setup_claimed_task(srv)
    resp = http.post(
        "/goals",
        headers=WORKER,
        json={
            "goal_text": "duplicate test",
            "workflow_plan": [{"task_id": task["task_id"], "target_agent": "linux"}],
        },
    )
    assert resp.status_code == 400
    assert "duplicate task_id" in resp.get_json()["error"]

def test_validate_durable_result_checks_run_attempt(srv):
    http, goal_id, task = setup_claimed_task(srv)
    result = {
        **{f: task[f] for f in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")},
        "run_id": "r1",
        "result_id": "result-1",
        "status": "SUCCESS",
        "artifacts": [],
        "run_attempt": "not-numeric",
    }
    resp = http.post("/tasks/result", headers=WORKER, json=result)
    assert resp.status_code == 400
    assert "run_attempt is invalid" in resp.get_json()["error"]

def test_goal_without_manual_plan_sets_queued_status_for_generated_tasks(srv):
    from scripts.run_chief_commander import ChiefCommander
    srv.app.test_client().post("/workers/register", headers=WORKER, json={"worker_id": "MAC-01", "capabilities": ["macos"]})
    class MockChief:
        def formulate_workflow_plan(self, *args, **kwargs):
            return "wf1", [{"task_id": "test-gen-1", "target_agent": "mac", "artifacts": []}]
    import server.app
    server.app.ChiefCommander = MockChief
    
    resp = srv.app.test_client().post("/goals", headers=WORKER, json={"goal_text": "gen task"})
    assert resp.status_code == 200
    
    claim = srv.app.test_client().post("/tasks/claim", headers=WORKER, json={"worker_id": "MAC-01"}).get_json()
    assert claim.get("task"), "Should be able to claim generated task"
    assert claim["task"]["status"] == "DISPATCHED"

def test_goal_with_ai_generated_duplicate_task_id_fails(srv):
    from scripts.run_chief_commander import ChiefCommander
    class MockChief:
        def formulate_workflow_plan(self, *args, **kwargs):
            return "wf1", [
                {"task_id": "dup-gen", "target_agent": "mac", "artifacts": []},
                {"task_id": "dup-gen", "target_agent": "mac", "artifacts": []}
            ]
    srv.ChiefCommander = MockChief
    
    resp = srv.app.test_client().post("/goals", headers=WORKER, json={"goal_text": "gen task with duplicates"})
    assert resp.status_code == 503
    assert "duplicate task_id from planner" in resp.get_json()["error"]

def test_resume_task_updates_instruction_override(srv):
    http = srv.app.test_client()
    goal_id = http.post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": [{"task_id": "r3", "target_agent": "windows"}]}).get_json()["goal_id"]
    http.post("/workers/register", headers=WORKER, json={"worker_id": "WINDOWS-01", "capabilities": ["windows"]})
    task = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    
    # Force state to HUMAN_REQUIRED so it can be resumed
    state = srv.load_state()
    state["tasks"][task["task_id"]]["status"] = "HUMAN_REQUIRED"
    srv.save_state(state)
    
    resp = http.post(f"/tasks/{task['task_id']}/resume", headers=WORKER, json={
        "action": "retry", 
        "instruction_override": "New instruction!"
    })
    assert resp.status_code == 200
    
    state = srv.load_state()
    assert state["goals"][goal_id]["workflow_plan"][0]["instruction"] == "New instruction!"

def test_resume_task_rejects_invalid_instruction_override(srv):
    http = srv.app.test_client()
    goal_id = http.post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": [{"task_id": "r4", "target_agent": "windows"}]}).get_json()["goal_id"]
    http.post("/workers/register", headers=WORKER, json={"worker_id": "WINDOWS-01", "capabilities": ["windows"]})
    task = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    
    state = srv.load_state()
    state["tasks"][task["task_id"]]["status"] = "HUMAN_REQUIRED"
    srv.save_state(state)
    
    resp = http.post(f"/tasks/{task['task_id']}/resume", headers=WORKER, json={
        "action": "retry", 
        "instruction_override": {"invalid": "type"}
    })
    assert resp.status_code == 400
    assert "instruction_override must be a non-empty string" in resp.get_json()["error"]

def test_workflow_plan_must_be_list(srv):
    resp = srv.app.test_client().post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": {"evil": "dict"}})
    assert resp.status_code == 400
    assert "workflow_plan must be a list" in resp.get_json()["error"]

def test_reclaim_stale_quarantines_ambiguous_tasks(srv):
    http = srv.app.test_client()
    goal_id = http.post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": [{"task_id": "r5", "target_agent": "windows"}]}).get_json()["goal_id"]
    http.post("/workers/register", headers=WORKER, json={"worker_id": "WINDOWS-01", "capabilities": ["windows"]})
    task = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "WINDOWS-01"}).get_json()["task"]
    
    # Backdate the worker's last_seen
    state = srv.load_state()
    state["workers"]["WINDOWS-01"]["last_seen"] -= 400
    srv.save_state(state)
    
    resp = http.post("/tasks/reclaim_stale", headers=WORKER)
    assert resp.status_code == 200
    assert resp.get_json()["quarantined_tasks"] == 1
    
    state = srv.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "HUMAN_REQUIRED"
    assert state["goals"][goal_id]["status"] == "BLOCKED"

def test_workflow_plan_step_instruction_must_be_string(srv):
    resp = srv.app.test_client().post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": [{"instruction": {"evil": "dict"}}]})
    assert resp.status_code == 400
    assert "instruction must be a string" in resp.get_json()["error"]

import time
def test_cost_routing(srv):
    http = srv.app.test_client()
    # add goal
    goal = http.post("/goals", headers=WORKER, json={"goal_text": "foo", "workflow_plan": [{"task_id": "t1", "target_agent": "mac"}]}).get_json()
    
    # register high cost worker
    http.post("/workers/register", headers=WORKER, json={"worker_id": "HIGH", "capabilities": ["macos"], "cost_class": "high"})
    
    # register low cost worker
    http.post("/workers/register", headers=WORKER, json={"worker_id": "LOW", "capabilities": ["macos"], "cost_class": "low"})
    
    # claim with HIGH
    res = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "HIGH"}).get_json()
    assert res.get("task") is None, res
    
    # claim with LOW
    res2 = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "LOW"}).get_json()
    assert res2.get("task") is not None, res2
    assert res2["task"]["task_id"] == "t1"
def test_manual_plan_target_agent_normalization(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER
    # manual plan
    http.post("/goals", headers=WORKER, json={
        "goal_text": "foo", 
        "workflow_plan": [{"task_id": "t1", "target_agent": "codex", "instruction": "echo hi"}]
    })
    
    # register windows worker
    http.post("/workers/register", headers=WORKER, json={"worker_id": "W1", "capabilities": ["windows"]})
    
    # attempt claim
    res = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "W1"}).get_json()
    assert res.get("task") is not None, res
def test_prepare_task_capability_bug(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER
    # manual plan
    http.post("/goals", headers=WORKER, json={
        "goal_text": "foo", 
        "workflow_plan": [{"task_id": "t1", "target_agent": "mac", "instruction": "echo hi"}]
    })
    
    # register mac worker
    http.post("/workers/register", headers=WORKER, json={"worker_id": "M1", "capabilities": ["macos"]})
    
    # attempt claim
    res = http.post("/tasks/claim", headers=WORKER, json={"worker_id": "M1"})
    print("STATUS:", res.status_code)
    print("BODY:", res.get_json())
    assert res.status_code == 200, res.get_json()
    assert res.get_json().get("task") is not None
def test_empty_workflow_plan_is_rejected(srv):
    http = srv.app.test_client()
    from tests.test_p3_server_idempotency import WORKER
    resp = http.post("/goals", headers=WORKER, json={"goal_text": "t", "workflow_plan": []})
    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"].lower()

def test_verify_fail_duplicate_returns_ack_not_409(srv):
    """Retrying a FAIL verdict after a lost HTTP response must return ACK_DUPLICATE, not 409."""
    http, goal_id, task = setup_claimed_task(srv)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=WORKER, json=result).status_code == 200

    # First FAIL verdict
    resp1 = verify(http, task, result, "FAIL")
    assert resp1.status_code == 200
    assert srv.load_state()["tasks"]["task-1"]["status"] == "FAILED_VERIFICATION"

    # Retry the same FAIL verdict (simulates lost HTTP response)
    resp2 = verify(http, task, result, "FAIL")
    assert resp2.status_code == 200, f"Expected ACK_DUPLICATE (200), got {resp2.status_code}: {resp2.get_json()}"
    assert resp2.get_json()["status"] == "ACK_DUPLICATE"

    # A conflicting result_id on a FAILED_VERIFICATION task must still 409
    resp3 = http.post("/tasks/verify", headers=VERIFIER, json={
        "task_id": task["task_id"], "result_id": "different-result",
        "verifier_id": "VERIFIER-01", "verdict": "FAIL",
        "artifacts": result["artifacts"]})
    assert resp3.status_code == 409
