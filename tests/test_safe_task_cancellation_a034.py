"""Tests for Safe Task Cancellation and Human Gates (ANTIGRAVITY 034).

Verifies fail-closed task cancellation and human gates:
Case A: Task cancelled before dispatch (QUEUED -> CANCELLED, no worker claim).
Case B: Task cancelled during unknown external execution (non-idempotent effect unknown -> BLOCKED / HUMAN_REQUIRED).
Case C: Task is BLOCKED / HUMAN_REQUIRED (cancellation requires named actor, rejects unauthenticated cancel).
Case D: Worker result arrives late after cancellation requested (rejected with 409 cancel_requested, not accepted).
Case E: Restart reconstructs cancelled and blocked tasks deterministically without re-execution.
Case F: Independent READY tasks continue execution unhindered by cancelled/blocked tasks.
"""

from pathlib import Path
import pytest

from courier_core.controller import ApiError
from courier_core.events import EventType
from courier_core.state_machine import TaskStatus
from tests.controller.ctrl_helpers import (
    FakeClock,
    make_controller,
    result_body,
    task_body,
    types,
)


def api_error(fn, *args):
    with pytest.raises(ApiError) as exc:
        fn(*args)
    return exc.value


def pass_time(ctl, clock, seconds, step=0.25):
    elapsed = 0.0
    while elapsed < seconds:
        delta = min(step, seconds - elapsed)
        clock.advance(delta)
        elapsed += delta
        ctl.tick()


def test_case_a_cancel_before_dispatch(tmp_path: Path):
    """Case A: Task cancelled before dispatch."""
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body())
        task_id = body["task_id"]

        # Cancel while still QUEUED
        res = ctl.cancel(task_id)
        assert res["status"] == "CANCELLED"
        assert res["cancel_requested"] is True

        # Claim must return None (no queued tasks available)
        assert ctl.claim({"worker_id": "w1"}) is None

        # Task journal reflects immediate cancellation
        assert types(ctl, task_id) == ["TASK_CREATED", "TASK_CANCEL_REQUESTED", "TASK_CANCELLED"]
        task = ctl.journal.task(task_id)
        assert task.status is TaskStatus.CANCELLED
    finally:
        ctl.stop()


def test_case_b_cancel_during_unknown_external_execution(tmp_path: Path):
    """Case B: Task cancelled during external execution with unknown effects.
    
    For non-idempotent tasks, if execution was started and cancelled while worker vanishes,
    the controller transitions to BLOCKED to prevent blind replay or assumption of safety.
    """
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock)
    try:
        _, body = ctl.create_task(task_body(effect_class="non_idempotent", lease_ttl_s=3))
        task_id = body["task_id"]
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})

        # Cancel requested while running
        res = ctl.cancel(task_id)
        assert res["status"] == "RUNNING"
        assert res["cancel_requested"] is True

        # Worker vanishes (lease expires without reaped confirmation)
        pass_time(ctl, clock, 4)

        # Fails closed to BLOCKED / human review because non-idempotent effect may have occurred
        task = ctl.journal.task(task_id)
        assert task.status is TaskStatus.BLOCKED
        assert "TASK_BLOCKED" in types(ctl, task_id)
    finally:
        ctl.stop()


def test_case_c_blocked_human_gate_requires_named_actor(tmp_path: Path):
    """Case C: Task is BLOCKED / HUMAN_REQUIRED.
    
    Cancellation requires a human decision naming the actor. Unattributed cancel is rejected.
    """
    clock = FakeClock()
    ctl = make_controller(tmp_path / "home", clock=clock)
    try:
        _, body = ctl.create_task(task_body(effect_class="non_idempotent", lease_ttl_s=3))
        task_id = body["task_id"]
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        ctl.cancel(task_id)
        pass_time(ctl, clock, 4)
        assert ctl.journal.task(task_id).status is TaskStatus.BLOCKED

        # Unattributed cancel is rejected with actor_required (409)
        err = api_error(ctl.cancel, task_id)
        assert err.status == 409
        assert err.code == "actor_required"

        # Named actor cancellation succeeds
        res = ctl.cancel(task_id, {"actor": "operator:alice", "reason": "user requested cancellation"})
        assert res["status"] == "CANCELLED"
        task = ctl.journal.task(task_id)
        assert task.status is TaskStatus.CANCELLED
        assert task.decided_by == "operator:alice"
        assert task.resolution == "cancelled_effect_unknown"
    finally:
        ctl.stop()


def test_case_d_late_worker_result_after_cancel_rejected(tmp_path: Path):
    """Case D: Worker result arrives late after cancellation was requested.
    
    Controller rejects late result with 409 cancel_requested and does not promote to COMPLETED.
    """
    ctl = make_controller(tmp_path / "home")
    try:
        _, body = ctl.create_task(task_body())
        task_id = body["task_id"]
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})

        # User cancels task
        ctl.cancel(task_id)

        # Heartbeat informs worker to cancel
        hb = ctl.heartbeat({"worker_id": "w1", "dispatch_ids": [lease["dispatch_id"]]})
        assert hb["cancel"] == [lease["dispatch_id"]]

        # Late result delivery attempt
        err = api_error(ctl.result, result_body(lease["dispatch_id"]))
        assert err.status == 409
        assert err.code == "cancel_requested"

        # Task does NOT become COMPLETE
        task = ctl.journal.task(task_id)
        assert task.status is not TaskStatus.COMPLETE
    finally:
        ctl.stop()


def test_case_e_restart_reconstructs_stopped_tasks_without_side_effects(tmp_path: Path):
    """Case E: Controller restart reconstructs cancelled and blocked tasks accurately."""
    home = tmp_path / "home"
    clock = FakeClock()
    ctl = make_controller(home, clock=clock)

    # 1. Create task-1 and cancel it before dispatch
    _, b1 = ctl.create_task(task_body())
    ctl.cancel(b1["task_id"])

    # 2. Create task-2, start, cancel, and let lease expire into BLOCKED
    _, b2 = ctl.create_task(task_body(effect_class="non_idempotent", lease_ttl_s=3))
    l2 = ctl.claim({"worker_id": "w1"})
    ctl.start({"dispatch_id": l2["dispatch_id"]})
    ctl.cancel(b2["task_id"])
    pass_time(ctl, clock, 4)

    ctl.stop()

    # Reopen controller from durable journal
    reopened = make_controller(home)
    try:
        t1 = reopened.journal.task(b1["task_id"])
        t2 = reopened.journal.task(b2["task_id"])

        assert t1.status is TaskStatus.CANCELLED
        assert t2.status is TaskStatus.BLOCKED

        # Claiming from reopened controller yields NO tasks (neither is eligible for dispatch)
        assert reopened.claim({"worker_id": "w1"}) is None
    finally:
        reopened.stop()


def test_case_f_independent_ready_task_continues_unhindered(tmp_path: Path):
    """Case F: Independent READY task continues execution normally despite other cancelled tasks."""
    ctl = make_controller(tmp_path / "home")
    try:
        # Task 1: Cancelled
        _, b1 = ctl.create_task(task_body())
        ctl.cancel(b1["task_id"])

        # Task 2: Independent task
        _, b2 = ctl.create_task(task_body())

        # Claim must yield Task 2 (not Task 1)
        lease2 = ctl.claim({"worker_id": "w1"})
        assert lease2 is not None
        assert lease2["task_id"] == b2["task_id"]

        # Task 2 executes to completion
        ctl.start({"dispatch_id": lease2["dispatch_id"]})
        ctl.result(result_body(lease2["dispatch_id"], outcome="success"))
        ctl.drain()

        task2 = ctl.journal.task(b2["task_id"])
        assert task2.status is TaskStatus.COMPLETE

        # Task 1 remains CANCELLED
        task1 = ctl.journal.task(b1["task_id"])
        assert task1.status is TaskStatus.CANCELLED
    finally:
        ctl.stop()
