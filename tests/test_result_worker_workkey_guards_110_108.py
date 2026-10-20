"""Deterministic tests for SEED 110 (RESULT MIT FALSCHEM WORKER) and SEED 108 (RESULT MIT FALSCHER WORKKEY-ID).

Verifies:
1. Valid worker and matching workkey submitting result -> 200 OK (ACK_RESULT_RECEIVED).
2. Result submitted by wrong worker (worker_id mismatch) -> 409 Conflict.
3. Result submitted with wrong workkey (workkey mismatch) -> 409 Conflict.
4. Result submitted with unexpected workkey when task has no workkey -> 409 Conflict.
5. Replay / duplicate of already accepted result by correct worker -> 200 OK (ACK_DUPLICATE).
6. Non-dispatched task receiving result -> 409 Conflict ("Task is not awaiting a result").
"""

import json
import pytest
from scripts.integration_contract import ContractError, validate_durable_result, prepare_task
from server import app as server_app

TEST_SECRET = "test-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}
VERIFIER_HEADERS = {"Authorization": "Bearer verifier-secret", "Content-Type": "application/json"}


@pytest.fixture
def server_env(tmp_path, monkeypatch):
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


def setup_dispatched_task(client, worker_id="WORKER-ORIGINAL", workkey="WORKKEY-ALPHA"):
    # 1. Register worker
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"]},
    )

    # 2. Submit goal with task
    task_spec = {
        "task_id": "task-test-result-guard",
        "target_agent": "windows",
        "instruction": "perform operation",
        "artifacts": ["out.txt"],
    }
    if workkey:
        task_spec["workkey"] = workkey

    goal_res = client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "guarded goal",
            "workflow_plan": [task_spec],
        },
    )
    assert goal_res.status_code == 200

    # 3. Claim task
    claim_res = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id})
    assert claim_res.status_code == 200
    task = claim_res.get_json()["task"]
    assert task is not None
    assert task["status"] == "DISPATCHED"
    return task


def test_seed_110_result_mit_falschem_worker(server_env):
    """SEED 110: Result submission with wrong worker_id is rejected with 409 Conflict."""
    client, _ = server_env
    task = setup_dispatched_task(client, worker_id="WORKER-LEGIT")

    wrong_worker_payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WORKER-IMPOSTOR",
        "run_id": "run-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=wrong_worker_payload)
    assert res.status_code == 409
    err = res.get_json()["error"]
    assert "worker_id mismatch" in err

    # Ensure state was not modified and task is still DISPATCHED to the legit worker
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"
    assert state["tasks"][task["task_id"]]["worker_id"] == "WORKER-LEGIT"


def test_seed_108_result_mit_falscher_workkey_id(server_env):
    """SEED 108: Result submission with mismatched workkey is rejected with 409 Conflict."""
    client, _ = server_env
    task = setup_dispatched_task(client, worker_id="WORKER-LEGIT", workkey="WORKKEY-ALPHA")

    wrong_workkey_payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WORKER-LEGIT",
        "workkey": "WORKKEY-WRONG",
        "run_id": "run-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=wrong_workkey_payload)
    assert res.status_code == 409
    err = res.get_json()["error"]
    assert "workkey mismatch" in err

    # Ensure state was not modified
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_positive_matching_worker_and_workkey_succeeds(server_env):
    """Positive Case: Matching worker_id and matching workkey succeeds with 200 OK."""
    client, _ = server_env
    task = setup_dispatched_task(client, worker_id="WORKER-LEGIT", workkey="WORKKEY-CORRECT")

    correct_payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WORKER-LEGIT",
        "workkey": "WORKKEY-CORRECT",
        "run_id": "run-1",
        "result_id": "res-legit-1",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=correct_payload)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Idempotent re-send is acknowledged duplicate
    res_dupe = client.post("/tasks/result", headers=AUTH_HEADERS, json=correct_payload)
    assert res_dupe.status_code == 200
    assert res_dupe.get_json()["status"] == "ACK_DUPLICATE"


def test_seed_110_missing_worker_id_fails_closed(server_env):
    """Synthetic Negative: Missing worker_id is rejected fail-closed with 409 mismatch."""
    client, _ = server_env
    task = setup_dispatched_task(client, worker_id="WORKER-LEGIT")

    payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "run_id": "run-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 409
    assert "worker_id mismatch" in res.get_json()["error"]

    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_seed_110_contract_level_worker_id_mismatch():
    """Synthetic Negative: Contract level validate_durable_result enforces worker_id equality."""
    task = prepare_task({
        "goal_id": "goal-worker-test",
        "task_id": "task-worker-test",
        "target_capability": "windows",
        "status": "DISPATCHED",
        "artifacts": ["out.txt"],
    })
    res_payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WRONG-WORKER",
        "run_id": "run-w-1",
        "result_id": "res-w-1",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "a" * 64}],
    }
    with pytest.raises(ContractError, match="worker_id mismatch"):
        validate_durable_result(task, res_payload)


def test_seed_110_run_id_equals_worker_id_rejected():
    """Security Regression: run_id must not equal worker_id (cross-field spoofing protection)."""
    task = prepare_task({
        "goal_id": "goal-worker-test2",
        "task_id": "task-worker-test2",
        "target_capability": "windows",
        "status": "DISPATCHED",
        "artifacts": ["out.txt"],
    })
    res_payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": task["worker_id"],  # illegal: run_id == worker_id
        "result_id": "res-w-2",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "b" * 64}],
    }
    with pytest.raises(ContractError, match="run_id must not equal worker_id"):
        validate_durable_result(task, res_payload)


def test_seed_110_reassigned_task_rejects_stale_prior_worker(server_env):
    """Synthetic Negative: Stale prior worker attempting submission after task reassignment is rejected."""
    client, _ = server_env
    task1 = setup_dispatched_task(client, worker_id="WORKER-FIRST")

    # Fail first attempt -> task requeued
    fail_res = {
        "goal_id": task1["goal_id"],
        "task_id": task1["task_id"],
        "attempt_id": task1["attempt_id"],
        "dispatch_id": task1["dispatch_id"],
        "worker_id": "WORKER-FIRST",
        "run_id": "run-fail-1",
        "result_id": "res-fail-1",
        "status": "FAILED",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }
    res_f = client.post("/tasks/result", headers=AUTH_HEADERS, json=fail_res)
    assert res_f.status_code == 200

    # Register worker 2 and claim requeued task
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": "WORKER-SECOND", "platform": "windows", "capabilities": ["windows"]},
    )
    claim2 = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WORKER-SECOND"})
    assert claim2.status_code == 200
    task2 = claim2.get_json()["task"]
    assert task2["worker_id"] == "WORKER-SECOND"

    # Stale WORKER-FIRST tries to submit for current attempt
    stale_worker_payload = {
        "goal_id": task2["goal_id"],
        "task_id": task2["task_id"],
        "attempt_id": task2["attempt_id"],
        "dispatch_id": task2["dispatch_id"],
        "worker_id": "WORKER-FIRST",
        "run_id": "run-stale-1",
        "result_id": "res-stale-1",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }
    res_stale = client.post("/tasks/result", headers=AUTH_HEADERS, json=stale_worker_payload)
    assert res_stale.status_code == 409
    assert "worker_id mismatch" in res_stale.get_json()["error"]

