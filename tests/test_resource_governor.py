"""Tests for scripts.resource_governor (Item P9 test hardening).

Covers:
- HostPressureController state machine (GREEN, YELLOW, ORANGE, RED, RECOVERY)
- Load measurement and normalized core load calculation
- Job admission rules (HEAVY concurrency limit, FAST_RAMP_DOWN, quiesce trigger)
- Bounded backoff poll intervals per state
- Snapshot generation and global governor singleton
"""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest

from scripts.resource_governor import HostPressureController, governor


def test_governor_constants():
    assert HostPressureController.MAX_HEAVY_JOBS == 1
    assert HostPressureController.POLL_INTERVAL_BASE == 5
    assert HostPressureController.RECOVERY_WINDOW == 300
    assert isinstance(governor, HostPressureController)


def test_measure_pressure_thresholds(monkeypatch):
    ctrl = HostPressureController()
    monkeypatch.setattr(os, "cpu_count", lambda: 4)

    # 1. GREEN: norm_load <= 1.0 (load1 = 4.0, cores = 4 -> 1.0)
    monkeypatch.setattr(os, "getloadavg", lambda: (4.0, 4.0, 4.0), raising=False)
    assert ctrl.measure_pressure() == "GREEN"

    # 2. YELLOW: 1.0 < norm_load <= 1.5 (load1 = 5.0, cores = 4 -> 1.25)
    monkeypatch.setattr(os, "getloadavg", lambda: (5.0, 4.0, 4.0), raising=False)
    assert ctrl.measure_pressure() == "YELLOW"

    # 3. ORANGE: 1.5 < norm_load <= 2.0 (load1 = 7.0, cores = 4 -> 1.75)
    monkeypatch.setattr(os, "getloadavg", lambda: (7.0, 4.0, 4.0), raising=False)
    assert ctrl.measure_pressure() == "ORANGE"

    # 4. RED: norm_load > 2.0 (load1 = 10.0, cores = 4 -> 2.5)
    monkeypatch.setattr(os, "getloadavg", lambda: (10.0, 4.0, 4.0), raising=False)
    assert ctrl.measure_pressure() == "RED"


def test_measure_pressure_handles_exception(monkeypatch):
    ctrl = HostPressureController()
    monkeypatch.setattr(os, "getloadavg", lambda: (_ for _ in ()).throw(OSError("mock error")), raising=False)
    assert ctrl.measure_pressure() == "UNKNOWN"


def test_admit_job_under_recovery_window():
    ctrl = HostPressureController()
    ctrl.recovery_end_time = time.time() + 100.0

    assert ctrl.admit_job("LIGHT") is False
    assert ctrl.state == "RECOVERY"


def test_admit_job_red_triggers_quiesce(monkeypatch):
    ctrl = HostPressureController()
    monkeypatch.setattr(ctrl, "measure_pressure", lambda: "RED")

    now = time.time()
    assert ctrl.admit_job("LIGHT") is False
    assert ctrl.state == "RECOVERY"
    assert ctrl.recovery_end_time >= now + HostPressureController.RECOVERY_WINDOW - 1.0


def test_admit_job_orange_fast_ramp_down(monkeypatch):
    ctrl = HostPressureController()
    monkeypatch.setattr(ctrl, "measure_pressure", lambda: "ORANGE")

    # Rejects HEAVY and MEDIUM
    assert ctrl.admit_job("HEAVY") is False
    assert ctrl.admit_job("MEDIUM") is False

    # Admits LIGHT
    assert ctrl.admit_job("LIGHT") is True
    assert ctrl.state == "ORANGE"


def test_admit_job_heavy_limit(monkeypatch):
    ctrl = HostPressureController()
    monkeypatch.setattr(ctrl, "measure_pressure", lambda: "GREEN")

    # Initial heavy job fits
    ctrl.active_jobs["HEAVY"] = 0
    assert ctrl.admit_job("HEAVY") is True

    # Second heavy job rejected (MAX_HEAVY_JOBS == 1)
    ctrl.active_jobs["HEAVY"] = 1
    assert ctrl.admit_job("HEAVY") is False


def test_get_poll_interval():
    ctrl = HostPressureController()

    ctrl.state = "GREEN"
    assert ctrl.get_poll_interval() == 5

    ctrl.state = "YELLOW"
    assert ctrl.get_poll_interval() == 10

    ctrl.state = "ORANGE"
    assert ctrl.get_poll_interval() == 20

    ctrl.state = "RECOVERY"
    assert ctrl.get_poll_interval() == 30

    ctrl.state = "UNKNOWN"
    assert ctrl.get_poll_interval() == 5


def test_post_run_resource_snapshot():
    ctrl = HostPressureController()
    ctrl.state = "GREEN"

    snap = ctrl.post_run_resource_snapshot()
    assert isinstance(snap, dict)
    assert snap["state"] == "GREEN"
    assert "timestamp" in snap
    assert "load" in snap
