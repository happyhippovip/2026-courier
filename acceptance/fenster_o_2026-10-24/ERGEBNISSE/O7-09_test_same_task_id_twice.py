"""O7-09 (B5 Replay): the same task id must not run (or show as running) twice.

Guard (holds): the controller dedupes on idempotency_key; the second create with the
same key returns the same task and no second TASK_CREATED (courier_core/controller.py:373-380).
Defect (strict xfail): courier_overlay/event_bus.py:107-110 says delivery is
AT-LEAST-ONCE and consumers MUST fold idempotently. OverlayStateMachine.process_event
(courier_overlay/state_machine.py:19-39) folds strictly in order, and sync()
(:41-46) re-reads the whole bus each time. A duplicate TASK_ASSIGNED/WORKER_STARTED
of an already completed task (a retried emit, or ReplayHarness.reset()+play_all(),
replay_harness.py:161-164, which appends to the same bus) puts task-101 back to
ASSIGNED/WORKING: the overlay shows the same task id executing a second time.
Not a finding: duplicate *records* on the bus are allowed by that contract (consumers
must not count records), so a replay that appends records is not tested here.
"""
import pytest

from courier_core.controller import Controller
from courier_overlay.event_bus import emit
from courier_overlay.replay_harness import LIFECYCLE_SUCCESS, ReplayHarness
from courier_overlay.state_machine import OverlayStateMachine


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-09/B5: overlay re-opens a completed task on an at-least-once duplicate")
def test_duplicate_event_of_completed_task_does_not_reopen_it(tmp_path):
    bus = str(tmp_path / "bus.jsonl")
    harness = ReplayHarness(bus)
    harness.load_sequence(LIFECYCLE_SUCCESS)
    harness.play_all()
    assert {w.agent_id: w.status for w in harness.state_machine.get_snapshot()} == {"worker-alpha": "IDLE"}
    # at-least-once: the earlier TASK_ASSIGNED for task-101 lands a second time
    emit(bus, agent_id="worker-alpha", task_id="task-101", event_type="TASK_ASSIGNED",
         short_summary="Task assigned to worker-alpha")
    fresh = OverlayStateMachine(bus)
    fresh.sync()
    worker = {w.agent_id: w for w in fresh.get_snapshot()}["worker-alpha"]
    assert (worker.status, worker.current_task) == ("IDLE", None), (worker.status, worker.current_task)


def test_guard_controller_runs_one_task_for_one_idempotency_key(tmp_path):
    ctrl = Controller(tmp_path / "home").boot()
    try:
        body = {"adapter": "synthetic", "params": {"write": "o.txt", "content": "x", "estimated_cost_eur": 0.0},
                "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 30, "idempotency_key": "o7-09"}
        first_status, first = ctrl.create_task(dict(body))
        second_status, second = ctrl.create_task(dict(body))
        assert first_status == 201 and second_status == 200
        assert first["task_id"] == second["task_id"]
    finally:
        ctrl.stop()
