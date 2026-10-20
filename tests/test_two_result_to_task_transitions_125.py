"""Deterministic tests for SEED 125 — ZWEI RESULT-ZU-TASK-ÜBERGÄNGE PRÜFEN.

Verifies the two contract-guaranteed Result-to-Task transitions:
1. Transition 1: SUCCESS Result -> Task transitions from DISPATCHED to RESULT_RECEIVED
   - Worker released (available=True, current_task=None)
   - Goal step synced to RESULT_RECEIVED (awaiting independent verifier)
   - Idempotent duplicate acknowledges with 200 ACK_DUPLICATE without state mutation
   - Conflicting result on processed task rejected with 409 Conflict

2. Transition 2A: FAILED Result (attempts < 3) -> Task transitions from DISPATCHED to QUEUED
   - Worker released (available=True, current_task=None)
   - Task worker_id cleared to None for re-dispatch
   - Workflow step synced to QUEUED
   - Idempotent duplicate acknowledges with 200 ACK_DUPLICATE
   - Task can be safely claimed for attempt 2 with fresh attempt_id and dispatch_id

3. Transition 2B: FAILED Result (attempts >= 3) -> Task transitions from DISPATCHED to FAILED_TERMINAL
   - Worker released
   - Workflow step set to FAILED_TERMINAL
   - Goal status transitioned to BLOCKED
   - Task cannot be claimed again
   - Idempotent duplicate acknowledges with 200 ACK_DUPLICATE

4. Negative Guard: Result intake rejected on non-dispatched states
   - Submission on QUEUED task returns 409 Conflict
   - Submission on RECONCILED task returns 409 Conflict
   - Submission on unknown task returns 400 Bad Request
"""

import hashlib
import json
import pytest
from server import app as server_app

TEST_SECRET = "test-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}
VERIFIER_HEADERS = {"Authorization": "Bearer verifier-secret", "Content-Type": "application/json"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    init_state = {
        "goals": {},
        "tasks": {},
        "workers": {},
        "walls": {},
        "seq": 0,
    }
    state_file.write_text(json.dumps(init_state), encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", TEST_SECRET)
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    with server_app.app.test_client() as client:
        yield client, state_file


def setup_dispatched_task(client, worker_id="WORKER-125", task_id="task-seed-125"):
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"]},
    )
    client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": f"goal-for-{task_id}",
            "workflow_plan": [
                {
                    "task_id": task_id,
                    "target_agent": "windows",
                    "instruction": "perform test operation",
                    "artifacts": ["out_125.txt"],
                }
            ],
        },
    )
    claim_res = client.post(
        "/tasks/claim",
        headers=AUTH_HEADERS,
        json={"worker_id": worker_id},
    )
    task = claim_res.get_json()["task"]
    assert task is not None
    assert task["task_id"] == task_id
    assert task["status"] == "DISPATCHED"
    return task


def make_success_result(task):
    return {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-success-125",
        "result_id": f"result-success-{task['attempt_id']}",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [
            {
                "path": "out_125.txt",
                "sha256": hashlib.sha256(b"seed 125 test output\n").hexdigest(),
            }
        ],
    }


def make_failed_result(task):
    return {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": f"run-failed-{task['attempt_id']}",
        "result_id": f"result-failed-{task['attempt_id']}",
        "status": "FAILED",
        "source_sha": "0" * 40,
        "artifacts": [],
    }


def test_transition_1_success_result_to_task_result_received(env):
    """Transition 1: SUCCESS result moves task from DISPATCHED to RESULT_RECEIVED."""
    client, _ = env
    task = setup_dispatched_task(client, worker_id="WORKER-SUCCESS", task_id="task-trans-1")
    worker_id = task["worker_id"]

    success_payload = make_success_result(task)
    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=success_payload)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # State validation
    state = server_app.load_state()
    stored_task = state["tasks"][task["task_id"]]
    assert stored_task["status"] == "RESULT_RECEIVED"
    assert stored_task["result"]["status"] == "SUCCESS"
    assert stored_task["result"]["result_id"] == success_payload["result_id"]
    assert stored_task["worker_id"] == worker_id

    # Worker released
    worker = state["workers"][worker_id]
    assert worker["current_task"] is None
    assert worker["available"] is True

    # Goal workflow step updated, goal remains ACTIVE until independent /verify
    goal = state["goals"][task["goal_id"]]
    assert goal["status"] == "ACTIVE"
    step = goal["workflow_plan"][0]
    assert step["status"] == "RESULT_RECEIVED"

    # Idempotent re-send of the identical result returns ACK_DUPLICATE
    res_dupe = client.post("/tasks/result", headers=AUTH_HEADERS, json=success_payload)
    assert res_dupe.status_code == 200
    assert res_dupe.get_json()["status"] == "ACK_DUPLICATE"

    # Conflicting second result is rejected with 409
    conflicting = dict(success_payload, result_id="result-different-125")
    res_conflict = client.post("/tasks/result", headers=AUTH_HEADERS, json=conflicting)
    assert res_conflict.status_code == 409
    assert "Task is not awaiting a result" in res_conflict.get_json()["error"]


def test_transition_2a_failure_result_with_retries_remaining_to_task_queued(env):
    """Transition 2A: FAILED result with attempts < 3 moves task from DISPATCHED to QUEUED for retry."""
    client, _ = env
    task = setup_dispatched_task(client, worker_id="WORKER-FAIL-1", task_id="task-trans-2a")
    worker_id = task["worker_id"]
    assert task.get("attempts") == 1

    failed_payload = make_failed_result(task)
    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=failed_payload)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # State validation: Task re-queued for retry, worker unassigned
    state = server_app.load_state()
    stored_task = state["tasks"][task["task_id"]]
    assert stored_task["status"] == "QUEUED"
    assert stored_task["worker_id"] is None
    assert stored_task["attempts"] == 1

    # Worker released
    worker = state["workers"][worker_id]
    assert worker["current_task"] is None
    assert worker["available"] is True

    # Workflow step updated to QUEUED
    goal = state["goals"][task["goal_id"]]
    assert goal["status"] == "ACTIVE"
    step = goal["workflow_plan"][0]
    assert step["status"] == "QUEUED"
    assert step["worker_id"] is None

    # Idempotent re-send of the identical failed result returns ACK_DUPLICATE
    res_dupe = client.post("/tasks/result", headers=AUTH_HEADERS, json=failed_payload)
    assert res_dupe.status_code == 200
    assert res_dupe.get_json()["status"] == "ACK_DUPLICATE"

    # Re-dispatch / Claim: Task can be claimed again as attempt 2
    claim_res = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id})
    retried_task = claim_res.get_json()["task"]
    assert retried_task is not None
    assert retried_task["task_id"] == task["task_id"]
    assert retried_task["attempts"] == 2
    assert retried_task["attempt_id"] == f"{task['task_id']}:attempt:2"
    assert retried_task["dispatch_id"] != task["dispatch_id"]
    assert retried_task["status"] == "DISPATCHED"


def test_transition_2b_failure_result_with_retries_exhausted_to_task_failed_terminal(env):
    """Transition 2B: FAILED result with attempts >= 3 moves task to FAILED_TERMINAL and blocks goal."""
    client, _ = env
    task_id = "task-trans-2b"
    worker_id = "WORKER-FAIL-3"

    # Cycle through 3 attempts
    task = setup_dispatched_task(client, worker_id=worker_id, task_id=task_id)
    # Attempt 1 failure
    res1 = client.post("/tasks/result", headers=AUTH_HEADERS, json=make_failed_result(task))
    assert res1.status_code == 200

    # Claim attempt 2
    task2 = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id}).get_json()["task"]
    assert task2["attempts"] == 2
    # Attempt 2 failure
    res2 = client.post("/tasks/result", headers=AUTH_HEADERS, json=make_failed_result(task2))
    assert res2.status_code == 200

    # Claim attempt 3
    task3 = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id}).get_json()["task"]
    assert task3["attempts"] == 3
    # Attempt 3 failure (exhausted retries: attempts >= 3)
    failed3_payload = make_failed_result(task3)
    res3 = client.post("/tasks/result", headers=AUTH_HEADERS, json=failed3_payload)
    assert res3.status_code == 200
    assert res3.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # State validation: FAILED_TERMINAL and Goal BLOCKED
    state = server_app.load_state()
    stored_task = state["tasks"][task_id]
    assert stored_task["status"] == "FAILED_TERMINAL"
    assert stored_task["attempts"] == 3

    goal = state["goals"][task["goal_id"]]
    assert goal["status"] == "BLOCKED"
    step = goal["workflow_plan"][0]
    assert step["status"] == "FAILED_TERMINAL"

    # Worker released
    worker = state["workers"][worker_id]
    assert worker["current_task"] is None
    assert worker["available"] is True

    # Idempotent re-send returns ACK_DUPLICATE
    res_dupe = client.post("/tasks/result", headers=AUTH_HEADERS, json=failed3_payload)
    assert res_dupe.status_code == 200
    assert res_dupe.get_json()["status"] == "ACK_DUPLICATE"

    # Cannot claim terminal task anymore
    claim_res = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id})
    assert claim_res.get_json()["task"] is None


def test_negative_transition_cannot_submit_result_on_queued_task(env):
    """Negative transition: Submitting a result on a QUEUED task returns 409 Conflict."""
    client, _ = env
    task = setup_dispatched_task(client, worker_id="WORKER-NEG-QUEUED", task_id="task-neg-queued")
    # Fail once so task is now in state["tasks"] with status QUEUED
    client.post("/tasks/result", headers=AUTH_HEADERS, json=make_failed_result(task))
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "QUEUED"

    # Submitting a new/different result while task is QUEUED is rejected
    new_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WORKER-NEG-QUEUED",
        "run_id": "run-premature",
        "result_id": "res-premature-125",
        "status": "SUCCESS",
        "artifacts": [{"path": "out_125.txt", "sha256": hashlib.sha256(b"out\n").hexdigest()}],
    }
    res_queued = client.post("/tasks/result", headers=AUTH_HEADERS, json=new_result)
    assert res_queued.status_code == 409
    assert "Task is not awaiting a result" in res_queued.get_json()["error"]


def test_negative_transition_cannot_submit_result_on_reconciled_task(env):
    """Negative transition: Submitting a new result on a RECONCILED task returns 409 Conflict."""
    client, _ = env
    task = setup_dispatched_task(client, worker_id="WORKER-NEG-REC", task_id="task-neg-reconciled")
    res_succ = make_success_result(task)
    client.post("/tasks/result", headers=AUTH_HEADERS, json=res_succ)

    # Verify to transition to RECONCILED
    verify_payload = {
        "task_id": task["task_id"],
        "result_id": res_succ["result_id"],
        "verifier_id": "VERIFIER-INDEPENDENT",
        "verdict": "PASS",
        "artifacts": res_succ["artifacts"],
    }
    v_res = client.post("/tasks/verify", headers=VERIFIER_HEADERS, json=verify_payload)
    assert v_res.status_code == 200
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RECONCILED"

    # Submitting another/different result on RECONCILED task is rejected with 409
    later_result = dict(res_succ, result_id="result-later-125")
    res_reconciled = client.post("/tasks/result", headers=AUTH_HEADERS, json=later_result)
    assert res_reconciled.status_code == 409
    assert "Task is not awaiting a result" in res_reconciled.get_json()["error"]


def test_negative_transition_unknown_task_rejected(env):
    """Negative transition: Submitting result on unknown task returns 400 Bad Request."""
    client, _ = env
    unknown_result = {
        "goal_id": "goal-none",
        "task_id": "task-non-existent-125",
        "attempt_id": "task-none:attempt:1",
        "dispatch_id": "disp-none",
        "worker_id": "WORKER-NONE",
        "run_id": "run-none",
        "result_id": "res-none",
        "status": "SUCCESS",
        "artifacts": [{"path": "out_125.txt", "sha256": hashlib.sha256(b"none\n").hexdigest()}],
    }
    res_unknown = client.post("/tasks/result", headers=AUTH_HEADERS, json=unknown_result)
    assert res_unknown.status_code == 400
    assert "Invalid task or worker" in res_unknown.get_json()["error"]
