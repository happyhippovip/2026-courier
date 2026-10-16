"""Tests for Idempotent Worker Reconnection (ANTIGRAVITY 031).

Verifies safe, deterministic worker registration and reconnect behavior:
Case A: Worker registers for the first time.
Case B: Same worker reconnects identically; state & assigned task preserved.
Case C: Stale session arrives after newer session; rejected with 409 STALE_SESSION.
Case D: Rapid / concurrent duplicate registrations succeed idempotently without duplicate entries.
Case E: Different worker / platform claims same worker_id; rejected with 409 WRONG_WORKER_IDENTITY.
Case F: Worker reconnects and delivers task result; duplicate delivered handled with ACK_DUPLICATE.
"""

import pytest

import server.app as server_app


def auth_headers():
    return {"Authorization": "Bearer test-secret", "Content-Type": "application/json"}


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "server_state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    return server_app.app.test_client()


def test_case_a_initial_worker_registration(http):
    """Case A: Worker registers for the first time."""
    payload = {
        "worker_id": "WIN-SYNTH-01",
        "platform": "windows",
        "capabilities": ["windows", "powershell"],
        "client_id": "client-uuid-001",
        "session_id": "session-100",
        "session_seq": 1,
    }
    res = http.post("/workers/register", headers=auth_headers(), json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "REGISTERED"
    assert data["reconnected"] is False

    state = server_app.load_state()
    assert "WIN-SYNTH-01" in state["workers"]
    worker = state["workers"]["WIN-SYNTH-01"]
    assert worker["platform"] == "windows"
    assert worker["client_id"] == "client-uuid-001"
    assert worker["session_seq"] == 1
    assert worker["available"] is True


def test_case_b_identical_reconnect_preserves_task_and_identity(http):
    """Case B: Same worker reconnects; identity and active task are preserved."""
    # Register first
    http.post(
        "/workers/register",
        headers=auth_headers(),
        json={"worker_id": "WIN-SYNTH-02", "platform": "windows", "capabilities": ["windows"], "client_id": "cid-02"},
    )
    # Create goal and claim task
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "goal 1", "workflow_plan": [{"task_id": "task-b1", "target_agent": "windows", "artifacts": ["out.txt"]}]},
    )
    claim_res = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WIN-SYNTH-02"})
    assert claim_res.get_json()["task"]["task_id"] == "task-b1"

    # Reconnect (without specifying current_task)
    reconnect_payload = {
        "worker_id": "WIN-SYNTH-02",
        "platform": "windows",
        "capabilities": ["windows"],
        "client_id": "cid-02",
    }
    res = http.post("/workers/register", headers=auth_headers(), json=reconnect_payload)
    assert res.status_code == 200
    assert res.get_json()["reconnected"] is True

    state = server_app.load_state()
    worker = state["workers"]["WIN-SYNTH-02"]
    assert worker["current_task"] == "task-b1"
    assert worker["available"] is False
    # Only one logical worker in registry
    assert len([w for w in state["workers"] if w == "WIN-SYNTH-02"]) == 1


def test_case_c_stale_session_rejected_after_newer_session(http):
    """Case C: Older session registers after newer session; rejected with 409 STALE_SESSION."""
    # Initial registration with session_seq 2
    http.post(
        "/workers/register",
        headers=auth_headers(),
        json={"worker_id": "WIN-SYNTH-03", "platform": "windows", "session_id": "sess-new", "session_seq": 2},
    )

    # Stale registration packet arriving out of order with session_seq 1
    stale_payload = {
        "worker_id": "WIN-SYNTH-03",
        "platform": "windows",
        "session_id": "sess-old",
        "session_seq": 1,
    }
    res = http.post("/workers/register", headers=auth_headers(), json=stale_payload)
    assert res.status_code == 409
    data = res.get_json()
    assert data["code"] == "STALE_SESSION"

    # Verify existing session was not overwritten
    state = server_app.load_state()
    worker = state["workers"]["WIN-SYNTH-03"]
    assert worker["session_id"] == "sess-new"
    assert worker["session_seq"] == 2


def test_case_d_duplicate_near_simultaneous_registration_idempotent(http):
    """Case D: Same worker registers twice in rapid succession; succeeds idempotently."""
    payload = {
        "worker_id": "WIN-SYNTH-04",
        "platform": "windows",
        "capabilities": ["windows"],
        "session_id": "sess-04",
        "session_seq": 1,
    }
    first = http.post("/workers/register", headers=auth_headers(), json=payload)
    second = http.post("/workers/register", headers=auth_headers(), json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["reconnected"] is True

    state = server_app.load_state()
    # Exactly one entry in state["workers"]
    assert list(state["workers"].keys()).count("WIN-SYNTH-04") == 1


def test_case_e_wrong_worker_identity_rejected(http):
    """Case E: A different worker / platform claims existing worker_id; rejected with 409."""
    # Worker registered on Windows
    http.post(
        "/workers/register",
        headers=auth_headers(),
        json={"worker_id": "WIN-SYNTH-05", "platform": "windows", "client_id": "pc-win-01"},
    )

    # Different client claiming same worker_id from macOS
    wrong_platform = {
        "worker_id": "WIN-SYNTH-05",
        "platform": "macos",
        "client_id": "mac-laptop-99",
    }
    res1 = http.post("/workers/register", headers=auth_headers(), json=wrong_platform)
    assert res1.status_code == 409
    assert res1.get_json()["code"] == "WRONG_WORKER_IDENTITY"

    # Same platform but different client_id
    wrong_client = {
        "worker_id": "WIN-SYNTH-05",
        "platform": "windows",
        "client_id": "impostor-client",
    }
    res2 = http.post("/workers/register", headers=auth_headers(), json=wrong_client)
    assert res2.status_code == 409
    assert res2.get_json()["code"] == "WRONG_WORKER_IDENTITY"


def test_case_f_old_result_delivery_after_reconnect(http):
    """Case F: Worker reconnects and delivers result; re-delivery receives ACK_DUPLICATE."""
    http.post(
        "/workers/register",
        headers=auth_headers(),
        json={"worker_id": "WIN-SYNTH-06", "platform": "windows", "capabilities": ["windows"]},
    )
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "goal 6", "workflow_plan": [{"task_id": "task-f1", "target_agent": "windows", "artifacts": ["res.txt"]}]},
    )
    claim = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WIN-SYNTH-06"}).get_json()["task"]

    # Worker executes task locally, reconnects after disconnect
    http.post(
        "/workers/register",
        headers=auth_headers(),
        json={"worker_id": "WIN-SYNTH-06", "platform": "windows", "capabilities": ["windows"]},
    )

    # Post result
    result_payload = {
        "goal_id": claim["goal_id"],
        "task_id": claim["task_id"],
        "attempt_id": claim["attempt_id"],
        "dispatch_id": claim["dispatch_id"],
        "worker_id": "WIN-SYNTH-06",
        "run_id": "run-f1",
        "result_id": "res-f1",
        "status": "SUCCESS",
        "artifacts": [{"path": "res.txt", "sha256": "f" * 64}],
    }
    res = http.post("/tasks/result", headers=auth_headers(), json=result_payload)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Redelivery of same result (network glitch on ack) returns ACK_DUPLICATE
    res_dup = http.post("/tasks/result", headers=auth_headers(), json=result_payload)
    assert res_dup.status_code == 200
    assert res_dup.get_json()["status"] == "ACK_DUPLICATE"


def test_case_g_interrupted_reconnect_recovers_cleanly(http):
    """Case G: Interrupted Reconnect — worker disconnects mid-flight and reconnects with updated session seq."""
    reg_init = {
        "worker_id": "WIN-SYNTH-07",
        "platform": "windows",
        "capabilities": ["windows"],
        "client_id": "client-uuid-007",
        "session_id": "sess-init",
        "session_seq": 1,
    }
    res_init = http.post("/workers/register", headers=auth_headers(), json=reg_init)
    assert res_init.status_code == 200

    # Claim task
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "goal 7", "workflow_plan": [{"task_id": "task-g1", "target_agent": "windows", "artifacts": ["g.txt"]}]},
    )
    claim_res = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WIN-SYNTH-07"})
    assert claim_res.status_code == 200
    claim_task = claim_res.get_json()["task"]
    assert claim_task["task_id"] == "task-g1"

    # Worker connection was interrupted, reconnects with incremented session_seq
    reconnect_after_interrupt = {
        "worker_id": "WIN-SYNTH-07",
        "platform": "windows",
        "capabilities": ["windows"],
        "client_id": "client-uuid-007",
        "session_id": "sess-resumed",
        "session_seq": 2,
    }
    res_rec = http.post("/workers/register", headers=auth_headers(), json=reconnect_after_interrupt)
    assert res_rec.status_code == 200
    assert res_rec.get_json()["reconnected"] is True

    # State verification: task is preserved, worker identity is preserved, no duplicate
    state = server_app.load_state()
    assert list(state["workers"].keys()).count("WIN-SYNTH-07") == 1
    worker = state["workers"]["WIN-SYNTH-07"]
    assert worker["current_task"] == "task-g1"
    assert worker["session_id"] == "sess-resumed"
    assert worker["session_seq"] == 2

    # Worker can send heartbeat and submit result
    hb_res = http.post("/workers/heartbeat", headers=auth_headers(), json={"worker_id": "WIN-SYNTH-07"})
    assert hb_res.status_code == 200

    result_payload = {
        "goal_id": claim_task["goal_id"],
        "task_id": claim_task["task_id"],
        "attempt_id": claim_task["attempt_id"],
        "dispatch_id": claim_task["dispatch_id"],
        "worker_id": "WIN-SYNTH-07",
        "run_id": "run-g1",
        "result_id": "res-g1",
        "status": "SUCCESS",
        "artifacts": [{"path": "g.txt", "sha256": "0" * 64}],
    }
    res_result = http.post("/tasks/result", headers=auth_headers(), json=result_payload)
    assert res_result.status_code == 200
    assert res_result.get_json()["status"] == "ACK_RESULT_RECEIVED"

