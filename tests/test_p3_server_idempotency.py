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
