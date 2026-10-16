"""Deterministic test suite for Seed 109: Result mit falschem Attempt.

Category: 📥 Outbox, Resultfluss & Fortsetzung
Phase 7: Persistenz und Restart-Nachweis

Verifies:
1. Positive Contract Path:
   - Valid result with exact attempt_id and matching numeric attempt is accepted (200 OK).
2. Negative Contract Paths:
   - Result with mismatched attempt_id is rejected fail-closed (409 Conflict).
   - Result with mismatched numeric attempt is rejected fail-closed (409 Conflict).
   - Result with invalid attempt format (non-integer, boolean, <= 0) is rejected (400 Bad Request / ContractError).
3. Stale Attempt Replay Rejection:
   - When a task advances to attempt 2, delayed result from attempt 1 is rejected (409 Conflict).
4. Persistence & Restart Contract (Phase 7):
   - Task attempt identity survives cold state reload intact.
   - Wrong attempt submitted after reload is rejected fail-closed with zero state corruption.
   - Valid attempt submitted after reload is accepted.
   - Idempotent duplicate result resubmission over restart returns ACK_DUPLICATE (200 OK).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from scripts.integration_contract import (
    ContractError,
    prepare_task,
    validate_durable_result,
    verify_result,
)
from server import app as server_app

TEST_SECRET = "test-secret-109"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}


@pytest.fixture
def courier_env(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    init_state = {
        "goals": {},
        "tasks": {},
        "workers": {},
        "seq": 0,
    }
    state_file.write_text(json.dumps(init_state), encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", TEST_SECRET)
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret-109")
    with server_app.app.test_client() as client:
        yield client, state_file, tmp_path


def _make_dispatched_task(client, task_id="task-att-109", worker_id="WIN-CUSTODIAN-109"):
    # 1. Register worker
    reg = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": worker_id, "capabilities": ["windows"], "platform": "windows"},
    )
    assert reg.status_code == 200

    # 2. Post goal
    goal = client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "Test attempt consistency contract",
            "workflow_plan": [
                {
                    "task_id": task_id,
                    "target_agent": "windows",
                    "workkey": "courier/evidence/attempt-109",
                    "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
                    "owner": "Windows Evidence Custodian",
                    "artifacts": ["artifact.txt"],
                }
            ],
        },
    )
    assert goal.status_code == 200

    # 3. Claim task
    claim = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id})
    assert claim.status_code == 200
    task = claim.get_json()["task"]
    assert task is not None
    assert task["task_id"] == task_id
    assert task["attempts"] == 1
    assert task["attempt_id"] == f"{task_id}:attempt:1"
    return task


def _build_result(task, attempt_id=None, attempt=None):
    res = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": attempt_id if attempt_id is not None else task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-test-109",
        "result_id": "result-attempt-109",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "artifact.txt", "sha256": hashlib.sha256(b"content").hexdigest()}
        ],
    }
    if attempt is not None:
        res["attempt"] = attempt
    return res


# ---------------------------------------------------------------------------
# 1. Positiver Pfad: Matching Attempt
# ---------------------------------------------------------------------------

def test_result_with_matching_attempt_and_attempt_id_accepted(courier_env):
    client, _, _ = courier_env
    task = _make_dispatched_task(client)

    result = _build_result(task, attempt=1)
    resp = client.post("/tasks/result", headers=AUTH_HEADERS, json=result)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "ACK_RESULT_RECEIVED"


# ---------------------------------------------------------------------------
# 2. Negativer Pfad: Falscher Attempt / Attempt-ID Mismatch
# ---------------------------------------------------------------------------

def test_result_with_wrong_attempt_id_rejected(courier_env):
    client, _, _ = courier_env
    task = _make_dispatched_task(client)

    bad_result = _build_result(task, attempt_id=f"{task['task_id']}:attempt:99")
    resp = client.post("/tasks/result", headers=AUTH_HEADERS, json=bad_result)
    assert resp.status_code == 409
    assert "attempt or dispatch mismatch, possible replay" in resp.get_json()["error"]


def test_result_with_wrong_numeric_attempt_rejected(courier_env):
    client, _, _ = courier_env
    task = _make_dispatched_task(client)

    bad_result = _build_result(task, attempt=2)  # Task is at attempt 1
    resp = client.post("/tasks/result", headers=AUTH_HEADERS, json=bad_result)
    assert resp.status_code == 409
    assert "attempt mismatch" in resp.get_json()["error"]


@pytest.mark.parametrize("invalid_attempt", [True, False, 0, -1, "one", [1]])
def test_result_with_invalid_attempt_type_rejected(courier_env, invalid_attempt):
    client, _, _ = courier_env
    task = _make_dispatched_task(client)

    bad_result = _build_result(task, attempt=invalid_attempt)
    resp = client.post("/tasks/result", headers=AUTH_HEADERS, json=bad_result)
    assert resp.status_code == 400
    assert "invalid attempt format" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# 3. Contract-Level Tests: scripts.integration_contract
# ---------------------------------------------------------------------------

def test_contract_validate_durable_result_checks_attempt():
    task = prepare_task({
        "goal_id": "goal-contract",
        "task_id": "task-contract",
        "target_capability": "windows",
        "status": "DISPATCHED",
        "attempts": 1,
        "artifacts": ["art.txt"],
    })
    valid_res = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-ok-1",
        "result_id": "result-ok-1",
        "status": "SUCCESS",
        "attempt": 1,
        "artifacts": [{"path": "art.txt", "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"}],
    }
    # Pass
    validated = validate_durable_result(task, valid_res)
    assert validated["attempt"] == 1

    # Wrong numeric attempt -> ContractError
    wrong_att = dict(valid_res, attempt=2)
    with pytest.raises(ContractError, match="attempt mismatch"):
        validate_durable_result(task, wrong_att)

    # Wrong attempt_id -> ContractError
    wrong_id = dict(valid_res, attempt_id="task-contract:attempt:99")
    with pytest.raises(ContractError, match="attempt_id mismatch"):
        validate_durable_result(task, wrong_id)

    # Bad format (bool) -> ContractError
    bad_type = dict(valid_res, attempt=True)
    with pytest.raises(ContractError, match="attempt must be an integer >= 1"):
        validate_durable_result(task, bad_type)


# ---------------------------------------------------------------------------
# 4. Phase 7: Persistenz und Restart-Nachweis
# ---------------------------------------------------------------------------

def test_persistence_and_restart_reconstruction_with_attempt(courier_env):
    """Cold restart preserves attempts and attempt_id; wrong attempt after restart fails closed."""
    client, state_file, _ = courier_env
    task = _make_dispatched_task(client, task_id="task-restart-109")

    # Verify task state in persistent file before reload
    raw_saved = json.loads(state_file.read_text(encoding="utf-8"))
    saved_task = raw_saved["tasks"]["task-restart-109"]
    assert saved_task["attempts"] == 1
    assert saved_task["attempt_id"] == "task-restart-109:attempt:1"
    assert saved_task["status"] == "DISPATCHED"

    # Simulate server restart / cold reload
    reloaded_state = server_app.load_state()
    reloaded_task = reloaded_state["tasks"]["task-restart-109"]
    assert reloaded_task["attempts"] == 1
    assert reloaded_task["attempt_id"] == "task-restart-109:attempt:1"
    assert reloaded_task["worker_id"] == task["worker_id"]
    assert reloaded_task["dispatch_id"] == task["dispatch_id"]

    # 1. Negative after restart: wrong attempt rejected with 409
    wrong_res = _build_result(task, attempt=3)
    resp_wrong = client.post("/tasks/result", headers=AUTH_HEADERS, json=wrong_res)
    assert resp_wrong.status_code == 409
    assert "attempt mismatch" in resp_wrong.get_json()["error"]

    # Verify task state on disk was NOT modified by the rejected attempt
    post_reject_state = server_app.load_state()
    assert post_reject_state["tasks"]["task-restart-109"]["status"] == "DISPATCHED"

    # 2. Positive after restart: matching attempt accepted with 200
    valid_res = _build_result(task, attempt=1)
    resp_valid = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_res)
    assert resp_valid.status_code == 200
    assert resp_valid.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Verify status transition was committed to persistent storage
    post_accept_state = server_app.load_state()
    accepted_task = post_accept_state["tasks"]["task-restart-109"]
    assert accepted_task["status"] == "RESULT_RECEIVED"

    # 3. Idempotent resend over restart returns ACK_DUPLICATE
    resp_dupe = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_res)
    assert resp_dupe.status_code == 200
    assert resp_dupe.get_json()["status"] == "ACK_DUPLICATE"


def test_stale_attempt_from_prior_generation_rejected_after_requeue(courier_env):
    """When attempt 1 fails and task is reclaimed/requeued to attempt 2, stale attempt 1 is rejected."""
    client, _, _ = courier_env
    task1 = _make_dispatched_task(client, task_id="task-stale-gen-109")
    assert task1["attempts"] == 1
    assert task1["attempt_id"] == "task-stale-gen-109:attempt:1"

    # Worker 1 reports failure for attempt 1 -> server puts task back to QUEUED for retry
    fail_res = _build_result(task1, attempt=1)
    fail_res["status"] = "FAILED"
    fail_res["result_id"] = "res-attempt1-fail"
    resp_fail = client.post("/tasks/result", headers=AUTH_HEADERS, json=fail_res)
    assert resp_fail.status_code == 200

    # Task is now re-queued; worker claims again -> advances to attempt 2
    claim2 = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WIN-CUSTODIAN-109"})
    assert claim2.status_code == 200
    task2 = claim2.get_json()["task"]
    assert task2["attempts"] == 2
    assert task2["attempt_id"] == "task-stale-gen-109:attempt:2"

    # Stale attempt 1 result arrives -> must be rejected with 409 Conflict
    stale_attempt1_res = _build_result(task1, attempt=1)
    resp_stale = client.post("/tasks/result", headers=AUTH_HEADERS, json=stale_attempt1_res)
    assert resp_stale.status_code == 409

    # Valid attempt 2 result arrives -> accepted with 200
    valid_attempt2_res = _build_result(task2, attempt=2)
    valid_attempt2_res["result_id"] = "res-attempt2-success"
    resp_valid2 = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_attempt2_res)
    assert resp_valid2.status_code == 200
    assert resp_valid2.get_json()["status"] == "ACK_RESULT_RECEIVED"

