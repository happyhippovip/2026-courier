import os
import time
import pytest
from scripts.resource_governor import HostPressureController, governor

def test_governor_singleton():
    assert isinstance(governor, HostPressureController)
    assert governor.MAX_HEAVY_JOBS == 1
    assert governor.POLL_INTERVAL_BASE == 5
    assert governor.RECOVERY_WINDOW == 300

def test_measure_pressure_mock(monkeypatch):
    h = HostPressureController()
    monkeypatch.setattr(os, "getloadavg", lambda: (10.0, 5.0, 1.0))
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    # norm_load = 10 / 4 = 2.5 > 2.0 -> RED
    assert h.measure_pressure() == "RED"

    monkeypatch.setattr(os, "getloadavg", lambda: (7.0, 5.0, 1.0))
    # norm_load = 7 / 4 = 1.75 -> ORANGE
    assert h.measure_pressure() == "ORANGE"

    monkeypatch.setattr(os, "getloadavg", lambda: (4.5, 4.0, 1.0))
    # norm_load = 4.5 / 4 = 1.125 -> YELLOW
    assert h.measure_pressure() == "YELLOW"

    monkeypatch.setattr(os, "getloadavg", lambda: (2.0, 2.0, 1.0))
    # norm_load = 2.0 / 4 = 0.5 -> GREEN
    assert h.measure_pressure() == "GREEN"

def test_admit_job_under_pressure(monkeypatch):
    h = HostPressureController()
    monkeypatch.setattr(h, "measure_pressure", lambda: "ORANGE")
    assert h.admit_job("HEAVY") is False
    assert h.admit_job("MEDIUM") is False
    assert h.admit_job("LIGHT") is True
    assert h.state == "ORANGE"

def test_admit_job_red_triggers_quiesce(monkeypatch):
    h = HostPressureController()
    monkeypatch.setattr(h, "measure_pressure", lambda: "RED")
    assert h.admit_job("LIGHT") is False
    assert h.state == "RECOVERY"
    assert h.recovery_end_time > time.time()
    # While in recovery window, cannot admit any job
    assert h.admit_job("LIGHT") is False

def test_poll_interval_bounded_backoff():
    h = HostPressureController()
    h.state = "GREEN"
    assert h.get_poll_interval() == 5
    h.state = "YELLOW"
    assert h.get_poll_interval() == 10
    h.state = "ORANGE"
    assert h.get_poll_interval() == 20
    h.state = "RECOVERY"
    assert h.get_poll_interval() == 30

def test_post_run_resource_snapshot():
    h = HostPressureController()
    snap = h.post_run_resource_snapshot()
    assert "load" in snap
    assert "state" in snap
    assert "timestamp" in snap
