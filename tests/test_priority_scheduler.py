"""Tests for courier_core.priority_scheduler - Priority Preemption & Fair-Share Scheduler."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from courier_core.priority_scheduler import (
    PriorityPreemptionScheduler,
    ScheduledTask,
    TaskPriority,
    TaskState,
)


def _dt(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_seconds)


def test_priority_scheduling_order():
    scheduler = PriorityPreemptionScheduler(max_slots=1)

    t_bg = ScheduledTask("t-bg", priority=TaskPriority.BACKGROUND, enqueued_at=_dt(1))
    t_norm = ScheduledTask("t-norm", priority=TaskPriority.NORMAL, enqueued_at=_dt(2))
    t_high = ScheduledTask("t-high", priority=TaskPriority.HIGH, enqueued_at=_dt(3))
    t_crit = ScheduledTask("t-crit", priority=TaskPriority.CRITICAL, enqueued_at=_dt(4))

    for t in [t_bg, t_norm, t_high, t_crit]:
        scheduler.enqueue(t)

    # First dispatch should be CRITICAL
    dispatched = scheduler.tick(now=_dt(10))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-crit"
    assert scheduler.active_slots_count == 1

    # Complete CRITICAL task
    scheduler.complete_task("t-crit")
    assert scheduler.active_slots_count == 0

    # Next dispatch should be HIGH
    dispatched = scheduler.tick(now=_dt(11))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-high"

    # Complete HIGH task
    scheduler.complete_task("t-high")

    # Next dispatch should be NORMAL
    dispatched = scheduler.tick(now=_dt(12))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-norm"

    # Complete NORMAL task
    scheduler.complete_task("t-norm")

    # Next dispatch should be BACKGROUND
    dispatched = scheduler.tick(now=_dt(13))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-bg"


def test_preemption_of_lower_priority_tasks():
    scheduler = PriorityPreemptionScheduler(max_slots=2)

    # Start 2 tasks: BACKGROUND and NORMAL (both preemptible)
    t1 = ScheduledTask("t1", priority=TaskPriority.BACKGROUND, preemptible=True, checkpoint={"step": 5})
    t2 = ScheduledTask("t2", priority=TaskPriority.NORMAL, preemptible=True, checkpoint={"step": 12})

    scheduler.enqueue(t1)
    scheduler.enqueue(t2)
    scheduler.tick(now=_dt(1))
    assert scheduler.active_slots_count == 2
    assert set(scheduler.running_tasks.keys()) == {"t1", "t2"}

    # Now enqueue a CRITICAL task
    t_crit = ScheduledTask("t-crit", priority=TaskPriority.CRITICAL)
    scheduler.enqueue(t_crit)

    # Tick should trigger preemption of the lowest priority task (t1: BACKGROUND)
    dispatched = scheduler.tick(now=_dt(2))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-crit"

    # Active count must still be <= max_slots (2)
    assert scheduler.active_slots_count == 2
    assert set(scheduler.running_tasks.keys()) == {"t2", "t-crit"}

    # Verify t1 was preempted, checkpoint preserved, and re-queued
    assert t1.task_id not in scheduler.running_tasks
    assert t1.state == TaskState.PREEMPTED
    assert t1.checkpoint == {"step": 5}
    assert t1.preemptions_count == 1
    assert any(q.task_id == "t1" for q in scheduler.ready_queue)


def test_non_preemptible_task_protection():
    scheduler = PriorityPreemptionScheduler(max_slots=1)

    t_locked = ScheduledTask("t-locked", priority=TaskPriority.BACKGROUND, preemptible=False)
    scheduler.enqueue(t_locked)
    scheduler.tick(now=_dt(1))
    assert scheduler.active_slots_count == 1

    # Incoming CRITICAL task cannot preempt non-preemptible task
    t_crit = ScheduledTask("t-crit", priority=TaskPriority.CRITICAL)
    scheduler.enqueue(t_crit)

    dispatched = scheduler.tick(now=_dt(2))
    assert len(dispatched) == 0  # No preemption possible
    assert scheduler.active_slots_count == 1
    assert "t-locked" in scheduler.running_tasks

    # Once non-preemptible task completes, CRITICAL task runs
    scheduler.complete_task("t-locked")
    dispatched = scheduler.tick(now=_dt(3))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-crit"


def test_starvation_prevention_aging():
    # Configure scheduler with aging threshold = 30 seconds
    scheduler = PriorityPreemptionScheduler(max_slots=1, starvation_threshold_seconds=30.0)

    # BACKGROUND task enqueued at t=0
    t_starved = ScheduledTask("t-starved", priority=TaskPriority.BACKGROUND, enqueued_at=_dt(0))
    scheduler.enqueue(t_starved)

    # NORMAL task enqueued at t=50 (starved task has waited 50s > 30s)
    t_normal = ScheduledTask("t-normal", priority=TaskPriority.NORMAL, enqueued_at=_dt(50))
    scheduler.enqueue(t_normal)

    # Effective score calculation at t=50:
    # Starved task should have aged to a higher priority score than fresh normal task
    dispatched = scheduler.tick(now=_dt(50))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-starved"


def test_slot_concurrency_invariant_and_cancellation():
    scheduler = PriorityPreemptionScheduler(max_slots=3)

    tasks = [
        ScheduledTask(f"t-{i}", priority=TaskPriority.NORMAL)
        for i in range(10)
    ]
    for t in tasks:
        scheduler.enqueue(t)

    # First tick dispatches 3 tasks
    d1 = scheduler.tick(now=_dt(0))
    assert len(d1) == 3
    assert scheduler.active_slots_count == 3
    assert len(scheduler.ready_queue) == 7

    # Cancel a task in ready queue
    canceled = scheduler.cancel_task("t-5")
    assert canceled is True
    assert len(scheduler.ready_queue) == 6

    # Cancel a running task
    running_id = d1[0].task_id
    canceled_running = scheduler.cancel_task(running_id)
    assert canceled_running is True
    assert scheduler.active_slots_count == 2

    # Next tick immediately fills the freed slot
    d2 = scheduler.tick(now=_dt(1))
    assert len(d2) == 1
    assert scheduler.active_slots_count == 3


def test_scheduler_cli(capsys, monkeypatch, tmp_path: Path):
    from courier_core.priority_scheduler import main

    cli_state = str(tmp_path / "cli_scheduler_state.json")

    # Enqueue via CLI
    monkeypatch.setattr(
        "sys.argv",
        ["priority_scheduler.py", "--state-file", cli_state, "enqueue", "--task-id", "cli-t1", "--priority", "HIGH", "--preemptible"],
    )
    main()
    out = capsys.readouterr().out
    assert "Enqueued cli-t1" in out

    # Status via CLI
    monkeypatch.setattr(
        "sys.argv",
        ["priority_scheduler.py", "--state-file", cli_state, "status"],
    )
    main()
    out2 = capsys.readouterr().out
    assert "cli-t1" in out2


def test_persistence_state_recovery(tmp_path: Path):
    state_file = tmp_path / "scheduler_state.json"
    s1 = PriorityPreemptionScheduler(max_slots=2, state_file=state_file)

    t1 = ScheduledTask("t-persist-1", priority=TaskPriority.HIGH, checkpoint={"marker": 42})
    s1.enqueue(t1)
    dispatched = s1.tick(now=_dt(1))
    assert len(dispatched) == 1
    assert dispatched[0].task_id == "t-persist-1"

    # Now simulate process restart by instantiating new scheduler with same state file
    s2 = PriorityPreemptionScheduler(max_slots=2, state_file=state_file)
    assert s2.active_slots_count == 1
    assert "t-persist-1" in s2.running_tasks
    recovered_task = s2.running_tasks["t-persist-1"]
    assert recovered_task.checkpoint == {"marker": 42}
    assert recovered_task.priority == TaskPriority.HIGH


def test_duplicate_task_id_deduplication(tmp_path: Path):
    state_file = tmp_path / "dedupe_state.json"
    scheduler = PriorityPreemptionScheduler(max_slots=1, state_file=state_file)

    scheduler.enqueue(ScheduledTask("dup-1", priority=TaskPriority.NORMAL, enqueued_at=_dt(0)))
    scheduler.enqueue(ScheduledTask("dup-1", priority=TaskPriority.HIGH, enqueued_at=_dt(1)))
    scheduler.enqueue(ScheduledTask("dup-1", priority=TaskPriority.BACKGROUND, enqueued_at=_dt(2)))

    assert len(scheduler.ready_queue) == 1
    assert scheduler.ready_queue[0].task_id == "dup-1"
    assert scheduler.ready_queue[0].priority == TaskPriority.HIGH

    scheduler.tick(now=_dt(3))
    assert "dup-1" in scheduler.running_tasks
    assert len(scheduler.ready_queue) == 0

    scheduler.enqueue(ScheduledTask("dup-1", priority=TaskPriority.CRITICAL, enqueued_at=_dt(4)))
    assert len(scheduler.ready_queue) == 0

