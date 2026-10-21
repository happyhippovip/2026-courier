"""CP-06 / CQ-06 Intake Idempotency, Request-ID, Answer Loss Resilience & Conflict Rejection.

Acceptance:
- Antwortverlust plus Wiederholung erzeugt hoechstens ein logisches Goal.
- Widerspruechlicher Payload zum selben Schluessel wird nicht ueberschrieben (409 conflict).
- Server Cold-Restart erhaelt die Idempotenzgrenze dauerhaft.
- Client-Submit mit automatischem Retry garantiert Single-Logical-Goal Receipt.
"""

import hashlib
import json
import pytest
from pathlib import Path
from unittest import mock

from server import app as server_app
from courier_core.intake_client import (
    GoalReceipt,
    IdempotencyConflictError,
    IntakeClientError,
    IntakeRejectedError,
    submit_goal_with_retry,
)


@pytest.fixture
def http(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def auth():
    return {"Authorization": "Bearer test-secret"}


def _plan(instruction: str = "bounded run"):
    return [
        {
            "task_id": "task-cp06-1",
            "target_agent": "linux",
            "instruction": instruction,
            "artifacts": ["out.txt"],
        }
    ]


def test_first_submission_creates_active_goal(http):
    payload = {
        "goal_text": "Intake audit test",
        "idempotency_key": "idem-cp06-001",
        "workflow_plan": _plan(),
    }
    resp = http.post("/goals", headers=auth(), json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ACTIVE"
    assert data["duplicate"] is False
    assert data["goal_id"].startswith("goal-")

    state = server_app.load_state()
    assert data["goal_id"] in state["goals"]
    assert "idem-cp06-001" in state["goal_idempotency"]
    assert state["goal_idempotency"]["idem-cp06-001"]["goal_id"] == data["goal_id"]


def test_retry_after_lost_response_returns_same_goal_without_duplication(http):
    payload = {
        "goal_text": "Intake network drop simulation",
        "idempotency_key": "idem-drop-002",
        "workflow_plan": _plan("run once"),
    }
    # Initial submission
    resp1 = http.post("/goals", headers=auth(), json=payload)
    assert resp1.status_code == 200
    goal_id_1 = resp1.get_json()["goal_id"]

    # Client believes response was lost and retries with identical idempotency key
    resp2 = http.post("/goals", headers=auth(), json=payload)
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2["goal_id"] == goal_id_1
    assert data2["duplicate"] is True

    # Critical invariant: Only one goal created, and exactly one task queued
    state = server_app.load_state()
    assert len(state["goals"]) == 1
    assert len(state["tasks"]) == 1


def test_conflicting_payload_with_same_idempotency_key_is_rejected_409(http):
    original_payload = {
        "goal_text": "Original payload content",
        "idempotency_key": "idem-conflict-003",
        "workflow_plan": _plan("original task"),
    }
    resp1 = http.post("/goals", headers=auth(), json=original_payload)
    assert resp1.status_code == 200
    goal_id_orig = resp1.get_json()["goal_id"]

    # Contradictory payload with different goal_text
    conflicting_payload = {
        "goal_text": "Contradictory forged content!",
        "idempotency_key": "idem-conflict-003",
        "workflow_plan": _plan("forged task"),
    }
    resp2 = http.post("/goals", headers=auth(), json=conflicting_payload)
    assert resp2.status_code == 409
    err = resp2.get_json()
    assert err["error"] == "idempotency_conflict"

    # Invariant: Original goal was not overwritten or corrupted
    state = server_app.load_state()
    assert state["goals"][goal_id_orig]["goal_text"] == "Original payload content"
    assert len(state["goals"]) == 1


def test_idempotency_key_header_support(http):
    payload = {
        "goal_text": "Header based idempotency",
        "workflow_plan": _plan(),
    }
    headers = dict(auth())
    headers["Idempotency-Key"] = "idem-header-004"

    resp1 = http.post("/goals", headers=headers, json=payload)
    assert resp1.status_code == 200
    goal_id = resp1.get_json()["goal_id"]

    # Replay with header
    resp2 = http.post("/goals", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.get_json()["goal_id"] == goal_id
    assert resp2.get_json()["duplicate"] is True


def test_invalid_idempotency_key_shape_fails_closed(http):
    # Whitespace only
    resp = http.post("/goals", headers=auth(), json={"goal_text": "t", "idempotency_key": "   "})
    assert resp.status_code == 400

    # Overlong (> 128 chars)
    resp2 = http.post("/goals", headers=auth(), json={"goal_text": "t", "idempotency_key": "a" * 129})
    assert resp2.status_code == 400


def test_cold_restart_preserves_idempotency_registry(tmp_path, monkeypatch):
    state_file = tmp_path / "persistent_state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")

    http1 = server_app.app.test_client()
    payload = {
        "goal_text": "Survives crash test",
        "idempotency_key": "idem-cold-restart-005",
        "workflow_plan": _plan(),
    }
    resp1 = http1.post("/goals", headers=auth(), json=payload)
    assert resp1.status_code == 200
    goal_id_initial = resp1.get_json()["goal_id"]

    # Cold restart simulation: new test client instance loading from disk
    http2 = server_app.app.test_client()
    resp_replay = http2.post("/goals", headers=auth(), json=payload)
    assert resp_replay.status_code == 200
    assert resp_replay.get_json()["goal_id"] == goal_id_initial
    assert resp_replay.get_json()["duplicate"] is True

    # Conflicting payload after cold restart still gets 409 conflict
    conflict_payload = dict(payload, goal_text="Different after restart")
    resp_conflict = http2.post("/goals", headers=auth(), json=conflict_payload)
    assert resp_conflict.status_code == 409


def test_client_submit_helper_transparent_retry_on_lost_connection(http):
    payload = {
        "goal_text": "Client submit helper test",
        "workflow_plan": _plan(),
    }
    receipt = submit_goal_with_retry(
        http.post,
        payload,
        idempotency_key="idem-client-submit-006",
        headers=auth(),
    )
    assert isinstance(receipt, GoalReceipt)
    assert receipt.status == "ACTIVE"
    assert receipt.duplicate is False
    assert receipt.attempts == 1

    # Retry helper call with same key
    receipt2 = submit_goal_with_retry(
        http.post,
        payload,
        idempotency_key="idem-client-submit-006",
        headers=auth(),
    )
    assert receipt2.goal_id == receipt.goal_id
    assert receipt2.duplicate is True


def test_client_submit_helper_raises_on_conflict(http):
    payload = {
        "goal_text": "Base payload",
        "workflow_plan": _plan(),
    }
    submit_goal_with_retry(http.post, payload, idempotency_key="idem-raise-conflict", headers=auth())

    with pytest.raises(IdempotencyConflictError):
        submit_goal_with_retry(
            http.post,
            dict(payload, goal_text="Conflict text"),
            idempotency_key="idem-raise-conflict",
            headers=auth(),
        )


def test_client_submit_helper_simulated_network_flakiness():
    calls = []

    def flaky_post(endpoint, headers=None, json=None):
        calls.append(json)
        if len(calls) < 3:
            raise ConnectionResetError("Simulated socket drop")
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.get_json.return_value = {"goal_id": "goal-recovered", "status": "ACTIVE", "duplicate": True}
        return mock_resp

    receipt = submit_goal_with_retry(
        flaky_post,
        {"goal_text": "Flaky recovery"},
        idempotency_key="flaky-key",
        max_attempts=4,
        backoff_s=0.01,
    )
    assert receipt.goal_id == "goal-recovered"
    assert receipt.attempts == 3
    assert len(calls) == 3
    # All retries used the exact same idempotency_key
    assert all(c["idempotency_key"] == "flaky-key" for c in calls)
