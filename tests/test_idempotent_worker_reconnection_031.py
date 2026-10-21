"""Offline test suite for ANTIGRAVITY 031 — IDEMPOTENT WORKER RECONNECTION.

Test Cases:
A. Worker registriert sich erstmals:
   - Erhält REGISTERED-Status, Registrierung wird im State persistiert.
B. Derselbe Worker verbindet sich erneut:
   - Idempotenter Reconnect, keine doppelte Worker-Identität, behält vorhandene Metadaten/Tasks.
C. Alte Session meldet sich nach neuer Session:
   - Registrierung mit früherer session_epoch wird ignoriert (STALE_SESSION_IGNORED), überschreibt neuere Session nicht.
D. Derselbe Worker meldet sich zweimal nahezu gleichzeitig:
   - Parallele / aufeinanderfolgende Aufrufe mit identischer Identität erzeugen keine doppelten Worker-Claims oder Konflikte.
E. Ein anderer Worker beansprucht dieselbe Identität:
   - Bei bestehendem aktivem Worker auf anderer Plattform wird der Claim mit 409 Conflict abgewiesen.
F. Nach einem Reconnect trifft ein altes Result ein:
   - Replay / Mismatch des alten Results auf den neuen State oder eine bereits bearbeitete Aufgabe
     wird strikt abgewiesen bzw. duplikatgeschützt (409 / ACK_DUPLICATE), ohne Geisterausführung.
"""

import copy
import json
import time
import pytest
from server import app as server_app

TEST_SECRET = "test-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}
VERIFIER_HEADERS = {"Authorization": "Bearer verifier-secret", "Content-Type": "application/json"}


@pytest.fixture
def test_env(tmp_path, monkeypatch):
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


def test_case_a_worker_registers_initially(test_env):
    """Case A: Worker registers for the first time successfully."""
    client, state_file = test_env
    res = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
            "session_epoch": 1,
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "REGISTERED"
    assert data["worker_id"] == "WIN-WORKER-01"

    state = server_app.load_state()
    assert "WIN-WORKER-01" in state["workers"]
    worker = state["workers"]["WIN-WORKER-01"]
    assert worker["platform"] == "windows"
    assert worker["available"] is True
    assert worker["current_task"] is None
    assert worker["session_epoch"] == 1


def test_case_b_same_worker_reconnects_idempotently(test_env):
    """Case B: Same worker reconnects; identity is preserved idempotently without duplication."""
    client, state_file = test_env

    # 1. First registration
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
            "session_epoch": 1,
        },
    )

    # 2. Worker reconnects with same ID
    res2 = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
            "session_epoch": 1,
        },
    )
    assert res2.status_code == 200
    assert res2.get_json()["status"] == "REGISTERED"

    state = server_app.load_state()
    # Ensure there is exactly 1 worker record and not duplicate entries
    assert len(state["workers"]) == 1
    assert "WIN-WORKER-01" in state["workers"]


def test_case_c_stale_session_after_new_session(test_env):
    """Case C: Stale session arrives after newer session; stale session is rejected/ignored."""
    client, state_file = test_env

    # 1. Newer session registers (epoch 2)
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
            "session_epoch": 2,
        },
    )

    # 2. Old delayed session tries to register (epoch 1)
    res_stale = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
            "session_epoch": 1,
        },
    )
    assert res_stale.status_code == 200
    data = res_stale.get_json()
    assert data["status"] == "STALE_SESSION_IGNORED"

    # State still preserves newer session epoch 2
    state = server_app.load_state()
    assert state["workers"]["WIN-WORKER-01"]["session_epoch"] == 2


def test_case_d_concurrent_duplicate_registrations(test_env):
    """Case D: Rapid / near-concurrent registrations do not produce conflicting duplicate claims."""
    client, state_file = test_env

    for _ in range(5):
        res = client.post(
            "/workers/register",
            headers=AUTH_HEADERS,
            json={
                "worker_id": "WIN-WORKER-CONCURRENT",
                "platform": "windows",
                "capabilities": ["windows"],
            },
        )
        assert res.status_code == 200
        assert res.get_json()["status"] == "REGISTERED"

    state = server_app.load_state()
    assert len(state["workers"]) == 1
    assert "WIN-WORKER-CONCURRENT" in state["workers"]


def test_case_e_foreign_worker_claims_same_identity(test_env):
    """Case E: A foreign worker from a conflicting platform tries to hijack the identity."""
    client, state_file = test_env

    # 1. Legitimate Windows worker registers
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-IDENTITY-SAFE",
            "platform": "windows",
            "capabilities": ["windows"],
        },
    )

    # 2. Foreign worker with conflicting platform attempts to claim the same ID
    conflict_res = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-IDENTITY-SAFE",
            "platform": "linux",
            "capabilities": ["linux"],
        },
    )
    assert conflict_res.status_code == 409
    assert "Identity conflict" in conflict_res.get_json()["error"]

    # State retains original Windows worker
    state = server_app.load_state()
    assert state["workers"]["WIN-IDENTITY-SAFE"]["platform"] == "windows"


def test_case_f_old_result_arrives_after_reconnect(test_env):
    """Case F: After a reconnect, a stale or superseded attempt's result cannot bind or overwrite."""
    client, state_file = test_env

    # 1. Register worker
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
        },
    )

    # 2. Create goal and task
    goal_res = client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "bounded task",
            "workflow_plan": [
                {
                    "task_id": "task-test-f",
                    "target_agent": "windows",
                    "instruction": "execute task",
                    "artifacts": ["out.txt"],
                }
            ],
        },
    )
    assert goal_res.status_code == 200

    # 3. Worker claims task
    claim_res = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WIN-WORKER-01"})
    task = claim_res.get_json()["task"]
    assert task is not None
    assert task["task_id"] == "task-test-f"
    first_attempt_id = task["attempt_id"]
    first_dispatch_id = task["dispatch_id"]

    # 4. Worker reconnects, signaling task loss (e.g. crash/restart without state)
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={
            "worker_id": "WIN-WORKER-01",
            "platform": "windows",
            "capabilities": ["windows"],
            "current_task": None,
        },
    )

    # Server quarantined task to HUMAN_REQUIRED
    state = server_app.load_state()
    assert state["tasks"]["task-test-f"]["status"] == "HUMAN_REQUIRED"

    # 5. An old delayed result arrives from the previous execution
    old_result_payload = {
        "goal_id": task["goal_id"],
        "task_id": "task-test-f",
        "attempt_id": first_attempt_id,
        "dispatch_id": first_dispatch_id,
        "worker_id": "WIN-WORKER-01",
        "run_id": "run-old",
        "result_id": "result-old-1",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }

    res_post = client.post("/tasks/result", headers=AUTH_HEADERS, json=old_result_payload)
    # The server must refuse the result for a non-DISPATCHED (quarantined) task
    assert res_post.status_code == 409
    assert "Task is not awaiting a result" in res_post.get_json()["error"]

    # Resume the task and re-claim it with a fresh attempt
    client.post("/tasks/task-test-f/resume", headers=AUTH_HEADERS, json={"action": "retry"})
    claim_res2 = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WIN-WORKER-01"})
    task2 = claim_res2.get_json()["task"]
    assert task2["attempt_id"] != first_attempt_id
    assert task2["dispatch_id"] != first_dispatch_id

    # Sending old result again with stale attempt_id must still be rejected (409)
    res_post2 = client.post("/tasks/result", headers=AUTH_HEADERS, json=old_result_payload)
    assert res_post2.status_code == 409
    assert "attempt or dispatch mismatch" in res_post2.get_json()["error"]


def test_case_g_invalid_session_epoch_fails_closed(test_env):
    """Case G: Non-integer, boolean, or negative session_epoch values fail closed with HTTP 400."""
    client, _ = test_env

    for bad_epoch in ["invalid", True, False, -1, -100, 1.5, [1], {"epoch": 1}]:
        res = client.post(
            "/workers/register",
            headers=AUTH_HEADERS,
            json={
                "worker_id": "WIN-WORKER-01",
                "platform": "windows",
                "capabilities": ["windows"],
                "session_epoch": bad_epoch,
            },
        )
        assert res.status_code == 400
        assert "invalid session_epoch" in res.get_json()["error"]


def test_case_h_malformed_worker_id_fails_closed(test_env):
    """Case H: Worker IDs with path traversals or illegal characters fail closed with HTTP 400."""
    client, _ = test_env

    for bad_id in [
        "../../malicious",
        "worker/slash",
        "worker\\backslash",
        "worker\x00null",
        "worker with space",
        "worker#hash",
        "worker;semicolon",
    ]:
        res = client.post(
            "/workers/register",
            headers=AUTH_HEADERS,
            json={
                "worker_id": bad_id,
                "platform": "windows",
                "capabilities": ["windows"],
            },
        )
        assert res.status_code == 400
        assert "invalid worker_id" in res.get_json()["error"]


def test_case_i_prepare_task_rejects_malformed_ids():
    """Case I: prepare_task enforces safe charset and rejects path traversals in task_id and goal_id."""
    from scripts.integration_contract import prepare_task, ContractError
    import pytest

    for bad_id in ["../../bad", "task/slash", "task\\backslash", "task with space", "task;evil"]:
        with pytest.raises(ContractError, match="forbidden characters or path traversal"):
            prepare_task({"task_id": bad_id, "goal_id": "g1", "target_agent": "windows"})

        with pytest.raises(ContractError, match="forbidden characters or path traversal"):
            prepare_task({"task_id": "t1", "goal_id": bad_id, "target_agent": "windows"})
