"""Tests for Adaptive Concurrency Scaler and Permit Controller."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.concurrency_scaler import (
    ConcurrencyScaler,
    ScalerTelemetry,
    acquire_permit,
    release_permit,
    adjust_capacity,
    main,
)


def test_initial_permits_acquisition_and_limits():
    scaler = ConcurrencyScaler(min_slots=1, max_slots=4, initial_slots=2)
    assert scaler.current_slots == 2

    # Acquire within slot limit
    assert scaler.acquire_permit("task_1") is True
    assert scaler.acquire_permit("task_2") is True

    # Exceed slot limit -> queued, returns False
    assert scaler.acquire_permit("task_3") is False
    assert len(scaler.active_permits) == 2
    assert scaler.queued_tasks == ["task_3"]


def test_release_permit_promotes_queued_task():
    scaler = ConcurrencyScaler(initial_slots=1)
    assert scaler.acquire_permit("task_1") is True
    assert scaler.acquire_permit("task_2") is False
    assert scaler.queued_tasks == ["task_2"]

    # Release task_1 -> task_2 automatically promoted
    promoted = scaler.release_permit("task_1")
    assert promoted == "task_2"
    assert "task_2" in scaler.active_permits
    assert len(scaler.queued_tasks) == 0


def test_scale_up_under_normal_resource_conditions():
    scaler = ConcurrencyScaler(min_slots=1, max_slots=5, initial_slots=2)

    # Normal resource state with high headroom (> 0.5) -> scale up by 1
    new_slots = scaler.adjust_capacity(resource_state="NORMAL", headroom_pct=0.8)
    assert new_slots == 3
    assert scaler.current_slots == 3

    # Scale up again
    new_slots = scaler.adjust_capacity(resource_state="NORMAL", headroom_pct=0.9)
    assert new_slots == 4


def test_freeze_capacity_during_cooldown():
    scaler = ConcurrencyScaler(initial_slots=3)

    # Cooldown freezes capacity regardless of headroom
    new_slots = scaler.adjust_capacity(resource_state="COOLDOWN", headroom_pct=0.9)
    assert new_slots == 3
    assert scaler.current_slots == 3


def test_scale_down_under_resource_pressure():
    scaler = ConcurrencyScaler(min_slots=1, max_slots=8, initial_slots=6)

    # Resource pressure reduces capacity (halves down to min_slots)
    new_slots = scaler.adjust_capacity(resource_state="PRESSURED")
    assert new_slots == 3

    # Repeated pressure clamps to min_slots
    new_slots2 = scaler.adjust_capacity(resource_state="PRESSURED")
    assert new_slots2 == 1
    assert scaler.current_slots == 1


def test_telemetry_reporting():
    scaler = ConcurrencyScaler(min_slots=1, max_slots=4, initial_slots=2)
    scaler.acquire_permit("task_1")
    scaler.acquire_permit("task_2")
    scaler.acquire_permit("task_3")  # queued

    telem = scaler.get_telemetry()
    assert telem.current_slots == 2
    assert telem.active_count == 2
    assert telem.queued_count == 1
    assert telem.min_slots == 1
    assert telem.max_slots == 4


def test_cli_invocation():
    code = main([
        "--initial-slots", "3",
        "--action", "telemetry",
    ])
    assert code == 0
