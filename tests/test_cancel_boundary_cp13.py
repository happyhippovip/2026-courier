"""
tests/test_cancel_boundary_cp13.py — Contract tests for CP-13 / CQ-13
Cancel-Requested, Confirmed Stop, Stale Result & Effect Boundary

Invariants:
1. Cancel is neither proof of success nor an immediate safe stop.
2. In-flight tasks wait for confirmed stop; worker receives cancel signal on heartbeat.
3. Confirmed stop transitions task to CANCELLED and frees worker safely.
4. Late result submission does not rewrite history; recorded immutably as EffectReceipt.
5. If worker vanishes without confirming stop:
   - Non-idempotent task is quarantined/BLOCKED (unknown effect); no blind retry.
   - Idempotent task is cleanly cancelled.
6. Cancelling a BLOCKED task strictly requires a human actor.
"""

import json
import uuid
import pytest
from courier_core.cancel_handler import (
    CancelHandler,
    CancelHandlerError,
    CancellationStatus,
    EffectReceipt,
)
from server import app as server_app


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def auth():
    return {"Authorization": "Bearer test-secret"}


def test_cancel_requested_does_not_immediately_mark_cancelled_while_worker_running(http):
    """Invariant 1 & 2: Cancel is not immediate stop; in-flight task stays DISPATCHED with cancel_requested."""
    # 1. Register worker
    res = http.post("/workers/register", headers=auth(), json={
        "worker_id": "MAC-01",
        "platform": "mac",
        "capabilities": ["macos"]
    })
    assert res.status_code == 200

    # 2. Post goal with 1 step
    res = http.post("/goals", headers=auth(), json={
        "goal_text": "Run long task",
        "workflow_plan": [{
            "task_id": "task-cancel-1",
            "target_agent": "mac",
            "artifacts": ["out1.txt"],
            "effect_class": "non_idempotent"
        }]
    })
    assert res.status_code == 200

    # 3. Worker claims task
    res = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"})
    assert res.status_code == 200
    task_claim = res.get_json()["task"]
    task_id = task_claim["task_id"]
    dispatch_id = task_claim["dispatch_id"]

    # 4. Request cancellation
    res = http.post(f"/tasks/{task_id}/cancel", headers=auth(), json={
        "actor": "operator:dennis",
        "reason": "user requested abort"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["cancel_requested"] is True
    # Crucial: Not immediately CANCELLED because the worker process is still executing!
    assert data["status"] == "DISPATCHED"

    # 5. Worker heartbeats -> receives cancel directive
    res = http.post("/workers/heartbeat", headers=auth(), json={"worker_id": "MAC-01"})
    assert res.status_code == 200
    hb_data = res.get_json()
    assert dispatch_id in hb_data.get("cancel", [])


def test_confirmed_stop_transitions_to_cancelled(http):
    """Invariant 3: Confirmed stop transitions task to CANCELLED and restores worker availability."""
    # Register & claim
    http.post("/workers/register", headers=auth(), json={
        "worker_id": "MAC-02",
        "platform": "mac",
        "capabilities": ["macos"]
    })
    http.post("/goals", headers=auth(), json={
        "goal_text": "Task to abort",
        "workflow_plan": [{
            "task_id": "task-cancel-2",
            "target_agent": "mac",
            "artifacts": ["out2.txt"]
        }]
    })
    claim = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-02"}).get_json()["task"]
    task_id = claim["task_id"]
    dispatch_id = claim["dispatch_id"]

    # Request cancel
    http.post(f"/tasks/{task_id}/cancel", headers=auth(), json={"actor": "operator:dennis"})

    # Worker reaps process tree and reports stopped_dispatches on heartbeat
    res = http.post("/workers/heartbeat", headers=auth(), json={
        "worker_id": "MAC-02",
        "stopped_dispatches": [dispatch_id]
    })
    assert res.status_code == 200

    # Task is now CANCELLED with confirmed stop
    res = http.get("/api/state")
    state = res.get_json()
    task = next(t for t in state["task_board"] if t["task_id"] == task_id)
    assert task["status"] == "CANCELLED"


def test_late_result_under_cancel_is_recorded_as_effect_receipt_without_history_rewriting(http):
    """Invariant 4 & 5: Late result does NOT rewrite history; preserved immutably as EffectReceipt."""
    http.post("/workers/register", headers=auth(), json={
        "worker_id": "MAC-03",
        "platform": "mac",
        "capabilities": ["macos"]
    })
    res_goal = http.post("/goals", headers=auth(), json={
        "goal_text": "Late result test",
        "workflow_plan": [{
            "task_id": "task-cancel-3",
            "target_agent": "mac",
            "artifacts": ["out3.txt"]
        }]
    }).get_json()
    goal_id = res_goal["goal_id"]

    claim = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-03"}).get_json()["task"]
    task_id = claim["task_id"]
    dispatch_id = claim["dispatch_id"]
    attempt_id = claim["attempt_id"]

    # Request cancel
    http.post(f"/tasks/{task_id}/cancel", headers=auth(), json={"actor": "operator:dennis"})

    # Worker finishes anyway and posts late result
    res = http.post("/tasks/result", headers=auth(), json={
        "goal_id": goal_id,
        "task_id": task_id,
        "worker_id": "MAC-03",
        "dispatch_id": dispatch_id,
        "attempt_id": attempt_id,
        "run_id": f"run-{uuid.uuid4().hex[:8]}",
        "result_id": f"result-{uuid.uuid4().hex[:8]}",
        "source_sha": "a" * 64,
        "status": "SUCCESS",
        "artifacts": [
            {
                "path": "out3.txt",
                "sha256": "b" * 64,
                "size_bytes": 10,
            }
        ],
    })
    assert res.status_code == 409
    body = res.get_json()
    assert body["code"] == "cancel_requested"
    assert "receipt_digest" in body

    # History is NOT rewritten: task status was not flipped to RESULT_RECEIVED
    res = http.get("/api/state")
    state = res.get_json()
    task = next(t for t in state["task_board"] if t["task_id"] == task_id)
    assert task["status"] != "RESULT_RECEIVED"


def test_vanished_worker_under_cancel_non_idempotent_blocks_automatic_retry():
    """Invariant 5: If worker vanishes on non-idempotent task under cancel, transitions to BLOCKED."""
    task = {
        "task_id": "task-non-idem-1",
        "status": "DISPATCHED",
        "worker_id": "W-DEAD-1",
        "dispatch_id": "dsp-111",
        "cancel_requested": True,
        "idempotent": False,
        "effect_class": "non_idempotent",
        "cancellation_history": [{
            "task_id": "task-non-idem-1",
            "status": "CANCEL_REQUESTED"
        }]
    }

    updated = CancelHandler.handle_vanished_worker(task)
    assert updated["status"] == "BLOCKED"
    assert updated["recovery_reason"] == "cancelled_worker_vanished_effect_ambiguous"
    assert updated["reexecution_allowed"] is False


def test_vanished_worker_under_cancel_idempotent_clears_safely():
    """Invariant 5: If worker vanishes on idempotent task under cancel, clears cleanly to CANCELLED."""
    task = {
        "task_id": "task-idem-1",
        "status": "DISPATCHED",
        "worker_id": "W-DEAD-2",
        "dispatch_id": "dsp-222",
        "cancel_requested": True,
        "idempotent": True,
        "cancellation_history": [{
            "task_id": "task-idem-1",
            "status": "CANCEL_REQUESTED"
        }]
    }

    updated = CancelHandler.handle_vanished_worker(task)
    assert updated["status"] == "CANCELLED"
    assert updated["resolution"] == "idempotent_cleared"
    assert updated["reexecution_allowed"] is False


def test_cancelling_blocked_task_requires_human_actor():
    """Invariant 6: Cancelling a BLOCKED task strictly requires an explicit human actor."""
    blocked_task = {
        "task_id": "task-blocked-1",
        "status": "BLOCKED",
        "recovery_reason": "STALE_WORKER_EFFECT_AMBIGUOUS"
    }

    # Without actor -> fails closed
    with pytest.raises(CancelHandlerError) as exc_info:
        CancelHandler.request_cancellation(blocked_task, actor=None)
    assert exc_info.value.code == "actor_required"

    # With named actor -> successfully cancels with resolution cancelled_effect_unknown
    updated = CancelHandler.request_cancellation(blocked_task, actor="desk:ana")
    assert updated["status"] == "CANCELLED"
    assert updated["resolution"] == "cancelled_effect_unknown"
    assert updated["decided_by"] == "desk:ana"
