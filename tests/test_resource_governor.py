import os
import time
import pytest
from scripts.resource_governor import HostPressureController

def test_measure_pressure_loadavg_posix(monkeypatch):
    controller = HostPressureController()
    monkeypatch.setattr(os, "cpu_count", lambda: 4)

    # > 2.0 -> RED (norm_load = 10.0 / 4 = 2.5)
    monkeypatch.setattr(os, "getloadavg", lambda: (10.0, 5.0, 5.0), raising=False)
    assert controller.measure_pressure() == "RED"

    # > 1.5 -> ORANGE (norm_load = 7.0 / 4 = 1.75)
    monkeypatch.setattr(os, "getloadavg", lambda: (7.0, 5.0, 5.0), raising=False)
    assert controller.measure_pressure() == "ORANGE"

    # > 1.0 -> YELLOW (norm_load = 5.0 / 4 = 1.25)
    monkeypatch.setattr(os, "getloadavg", lambda: (5.0, 5.0, 5.0), raising=False)
    assert controller.measure_pressure() == "YELLOW"

    # <= 1.0 -> GREEN (norm_load = 2.0 / 4 = 0.5)
    monkeypatch.setattr(os, "getloadavg", lambda: (2.0, 2.0, 2.0), raising=False)
    assert controller.measure_pressure() == "GREEN"

def test_measure_pressure_windows_psutil_fallback(monkeypatch):
    controller = HostPressureController()
    # Remove getloadavg to simulate Windows environment
    if hasattr(os, "getloadavg"):
        monkeypatch.delattr(os, "getloadavg")

    import psutil

    # 1. Critical CPU -> RED
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 95.0)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: type("Mem", (), {"percent": 40.0})())
    assert controller.measure_pressure() == "RED"

    # 2. Critical Memory -> RED
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 20.0)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: type("Mem", (), {"percent": 92.0})())
    assert controller.measure_pressure() == "RED"

    # 3. High CPU -> ORANGE
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 78.0)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: type("Mem", (), {"percent": 50.0})())
    assert controller.measure_pressure() == "ORANGE"

    # 4. Moderate Memory -> YELLOW
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 30.0)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: type("Mem", (), {"percent": 72.0})())
    assert controller.measure_pressure() == "YELLOW"

    # 5. Calm -> GREEN
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 20.0)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: type("Mem", (), {"percent": 40.0})())
    assert controller.measure_pressure() == "GREEN"

def test_admit_job_fsm_and_recovery():
    controller = HostPressureController()
    controller.measure_pressure = lambda: "GREEN"

    # GREEN admits HEAVY, MEDIUM, LIGHT
    assert controller.admit_job("HEAVY") is True
    assert controller.admit_job("medium") is True
    assert controller.admit_job("light") is True

    # ORANGE blocks HEAVY and MEDIUM, allows LIGHT
    controller.measure_pressure = lambda: "ORANGE"
    assert controller.admit_job("HEAVY") is False
    assert controller.admit_job("MEDIUM") is False
    assert controller.admit_job("LIGHT") is True

    # RED triggers quiesce and enters RECOVERY
    controller.measure_pressure = lambda: "RED"
    assert controller.admit_job("LIGHT") is False
    assert controller.state == "RECOVERY"
    assert controller.recovery_end_time > time.time()

    # While in recovery window, all jobs rejected
    assert controller.admit_job("LIGHT") is False

    # Once window expires, recovery clears
    controller.recovery_end_time = time.time() - 1
    controller.measure_pressure = lambda: "GREEN"
    assert controller.admit_job("LIGHT") is True
    assert controller.state == "GREEN"

def test_start_and_finish_job_accounting():
    controller = HostPressureController()
    controller.measure_pressure = lambda: "GREEN"

    # Start first heavy job succeeds
    assert controller.start_job("heavy") is True
    assert controller.active_jobs["HEAVY"] == 1

    # Second heavy job rejected (MAX_HEAVY_JOBS = 1)
    assert controller.start_job("HEAVY") is False
    assert controller.active_jobs["HEAVY"] == 1

    # Finish job releases capacity
    controller.finish_job("heavy")
    assert controller.active_jobs["HEAVY"] == 0

    # Can now admit heavy again
    assert controller.start_job("HEAVY") is True
    assert controller.active_jobs["HEAVY"] == 1

def test_bounded_backoff_poll_intervals():
    controller = HostPressureController()
    controller.state = "GREEN"
    assert controller.get_poll_interval() == 5

    controller.state = "YELLOW"
    assert controller.get_poll_interval() == 10

    controller.state = "ORANGE"
    assert controller.get_poll_interval() == 20

    controller.state = "RECOVERY"
    assert controller.get_poll_interval() == 30

def test_post_run_resource_snapshot():
    controller = HostPressureController()
    controller.state = "GREEN"
    snap = controller.post_run_resource_snapshot()
    assert snap["state"] == "GREEN"
    assert "timestamp" in snap
    assert snap["timestamp"] > 0
