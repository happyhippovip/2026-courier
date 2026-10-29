"""Tests for Grandma State Mapping (Dual-Surface Truth).

Verifies ops/ai/USER_REQUIREMENT_01_GRANDMA_STATE_MAPPING.md:
- FERTIG: goal status DONE or all steps reconciled
- BRAUCHT_DICH: blocked, terminal failure, verification failure, stale worker
- ARBEITET: active computing with fresh worker heartbeat
- WARTET_AUF_KAPAZITAET: queued waiting for matching worker
- API endpoint integration: /goals/<goal_id> and /goals/<goal_id>/grandma
"""
import time
import pytest

from courier_core.grandma_state import (
    STATE_ARBEITET,
    STATE_BRAUCHT_DICH,
    STATE_FERTIG,
    STATE_WARTET_AUF_KAPAZITAET,
    derive_user_state,
)


def test_fertig_when_goal_status_is_done():
    goal = {
        "goal_id": "g-1",
        "status": "DONE",
        "workflow_plan": [
            {"task_id": "t1", "status": "RECONCILED"},
            {"task_id": "t2", "status": "RECONCILED"},
        ],
        "current_step_index": 2,
    }
    res = derive_user_state(goal)
    assert res["user_state"] == STATE_FERTIG
    assert res["action_required"] is False
    assert res["action_type"] is None
    assert "erfolgreich abgeschlossen" in res["user_message"]
    assert res["step_progress"] == {"current": 2, "total": 2}


def test_fertig_when_all_steps_are_reconciled():
    goal = {
        "goal_id": "g-2",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "t1", "status": "RECONCILED"},
            {"task_id": "t2", "status": "RECONCILED"},
        ],
        "current_step_index": 1,
    }
    res = derive_user_state(goal)
    assert res["user_state"] == STATE_FERTIG
    assert res["action_required"] is False


def test_success_status_is_not_fertig():
    goal = {
        "goal_id": "g-success",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "t1", "status": "RECONCILED"},
            {"task_id": "t2", "status": "SUCCESS"},
        ],
        "current_step_index": 1,
    }
    res = derive_user_state(goal)
    assert res["user_state"] != STATE_FERTIG
    assert "verifiziert" not in res["user_message"]


def test_fresh_worker_on_another_task_is_not_this_step():
    now = 1000.0
    goal = {
        "goal_id": "g-other",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "task-alpha", "status": "DISPATCHED", "target_agent": "mac"}
        ],
        "current_step_index": 0,
    }
    state = {
        "workers": {
            "mac-1": {
                "worker_id": "mac-1",
                "current_task": "task-other",
                "last_seen": now - 30,
                "status": "BUSY",
            }
        }
    }
    res = derive_user_state(goal, state, now=now)
    assert res["user_state"] == STATE_BRAUCHT_DICH
    assert "Heartbeat abgelaufen" in res["user_message"]


def test_braucht_dich_when_goal_is_blocked():
    goal = {
        "goal_id": "g-3",
        "status": "BLOCKED",
        "blocked_reason": "API Key quota exceeded",
        "workflow_plan": [
            {"task_id": "t1", "status": "DISPATCHED"},
        ],
        "current_step_index": 0,
    }
    res = derive_user_state(goal)
    assert res["user_state"] == STATE_BRAUCHT_DICH
    assert res["action_required"] is True
    assert res["action_type"] == "RESUME_OR_RETRY"
    assert "quota exceeded" in res["user_message"]


def test_braucht_dich_when_step_fails_verification_or_terminal():
    goal = {
        "goal_id": "g-4",
        "status": "ACTIVE",
        "workflow_plan": [
            {
                "task_id": "t1",
                "status": "FAILED_VERIFICATION",
                "error": "AssertionError: SHA mismatch in artifact",
            }
        ],
        "current_step_index": 0,
    }
    res = derive_user_state(goal)
    assert res["user_state"] == STATE_BRAUCHT_DICH
    assert res["action_required"] is True
    assert res["action_type"] == "RESUME_OR_RETRY"
    assert "SHA mismatch" in res["user_message"]
    # Check that traceback prefix was stripped
    assert not res["user_message"].startswith("AssertionError:")


def test_arbeitet_when_step_is_dispatched_and_worker_is_fresh():
    now = 1000.0
    goal = {
        "goal_id": "g-5",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "task-alpha", "status": "DISPATCHED", "target_agent": "mac"}
        ],
        "current_step_index": 0,
    }
    state = {
        "workers": {
            "mac-1": {
                "worker_id": "mac-1",
                "current_task": "task-alpha",
                "last_seen": now - 30,  # 30 seconds ago (< 300s)
                "status": "BUSY",
            }
        }
    }
    res = derive_user_state(goal, state, now=now)
    assert res["user_state"] == STATE_ARBEITET
    assert res["action_required"] is False
    assert res["action_type"] is None
    assert "Schritt 1 von 1" in res["user_message"]


def test_braucht_dich_when_dispatched_worker_heartbeat_is_stale():
    now = 1000.0
    goal = {
        "goal_id": "g-6",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "task-beta", "status": "DISPATCHED", "target_agent": "windows"}
        ],
        "current_step_index": 0,
    }
    state = {
        "workers": {
            "win-1": {
                "worker_id": "win-1",
                "current_task": "task-beta",
                "last_seen": now - 350,  # Stale: > 300s
                "status": "BUSY",
            }
        }
    }
    res = derive_user_state(goal, state, now=now)
    assert res["user_state"] == STATE_BRAUCHT_DICH
    assert res["action_required"] is True
    assert "Heartbeat abgelaufen" in res["user_message"]


def test_wartet_auf_kapazitaet_when_step_is_queued():
    goal = {
        "goal_id": "g-7",
        "status": "ACTIVE",
        "workflow_plan": [
            {"task_id": "task-gamma", "status": "QUEUED", "target_agent": "github"}
        ],
        "current_step_index": 0,
    }
    state = {"workers": {}}
    res = derive_user_state(goal, state)
    assert res["user_state"] == STATE_WARTET_AUF_KAPAZITAET
    assert res["action_required"] is False
    assert "Plattform github" in res["user_message"]


def test_no_workflow_plan_initialized_safely():
    goal = {
        "goal_id": "g-empty",
        "status": "ACTIVE",
        "workflow_plan": [],
        "current_step_index": 0,
    }
    res = derive_user_state(goal)
    assert res["user_state"] == STATE_WARTET_AUF_KAPAZITAET
    assert res["action_required"] is False
    assert "initialisiert" in res["user_message"]


def test_api_get_goal_returns_user_summary(tmp_path, monkeypatch):
    from server import app as server_app

    state_file = tmp_path / "state.json"
    state_file.write_text(
        '{"goals": {"g-test": {"goal_id": "g-test", "status": "DONE", "workflow_plan": []}}, "tasks": {}, "workers": {}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-key-123")

    client = server_app.app.test_client()
    headers = {"Authorization": "Bearer test-key-123"}

    # Test main endpoint
    resp = client.get("/goals/g-test", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "goal" in data
    assert "user_summary" in data
    assert data["user_summary"]["user_state"] == STATE_FERTIG

    # Test dedicated grandma endpoint
    resp_g = client.get("/goals/g-test/grandma", headers=headers)
    assert resp_g.status_code == 200
    data_g = resp_g.get_json()
    assert data_g["user_state"] == STATE_FERTIG
    assert data_g["action_required"] is False
