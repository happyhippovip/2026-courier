import os
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.resource_governor import HostPressureController

def test_host_pressure_green():
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(0.5, 0.5, 0.5), create=True):
        with patch("os.cpu_count", return_value=4):
            assert controller.measure_pressure() == "GREEN"

def test_host_pressure_yellow():
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(5.0, 4.0, 3.0), create=True):
        with patch("os.cpu_count", return_value=4):
            # load 5.0 / 4 = 1.25 -> YELLOW
            assert controller.measure_pressure() == "YELLOW"

def test_host_pressure_orange():
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(7.0, 6.0, 5.0), create=True):
        with patch("os.cpu_count", return_value=4):
            # load 7.0 / 4 = 1.75 -> ORANGE
            assert controller.measure_pressure() == "ORANGE"

def test_host_pressure_red():
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(10.0, 9.0, 8.0), create=True):
        with patch("os.cpu_count", return_value=4):
            # load 10.0 / 4 = 2.5 -> RED
            assert controller.measure_pressure() == "RED"

def test_admit_job_heavy_limit():
    controller = HostPressureController()
    controller.active_jobs["HEAVY"] = 1
    with patch.object(controller, "measure_pressure", return_value="GREEN"):
        assert not controller.admit_job("HEAVY")
        assert controller.admit_job("LIGHT")

def test_trigger_quiesce():
    controller = HostPressureController()
    controller.trigger_quiesce()
    assert controller.state == "RECOVERY"
    assert controller.recovery_end_time > time.time()
    
    # Check that jobs are rejected during recovery
    assert not controller.admit_job("LIGHT")

def test_admit_job_red():
    controller = HostPressureController()
    with patch.object(controller, "measure_pressure", return_value="RED"):
        assert not controller.admit_job("LIGHT")
        assert controller.state == "RECOVERY"

def test_admit_job_orange():
    controller = HostPressureController()
    with patch.object(controller, "measure_pressure", return_value="ORANGE"):
        assert not controller.admit_job("HEAVY")
        assert not controller.admit_job("MEDIUM")
        assert controller.admit_job("LIGHT")
        assert controller.state == "ORANGE"

def test_unknown_pressure_does_not_admit(monkeypatch):
    controller = HostPressureController()
    with patch.object(controller, "measure_pressure", return_value="UNKNOWN"):
        assert controller.admit_job("HEAVY") is False
        assert controller.admit_job("MEDIUM") is False
        assert controller.admit_job("LIGHT") is False
    assert controller.state == "UNKNOWN"
    assert controller.get_poll_interval() == 20

    monkeypatch.setenv("COURIER_MOCK_HOST_PRESSURE", "BLUE")
    fresh = HostPressureController()
    assert fresh.measure_pressure() == "BLUE"
    assert fresh.admit_job("LIGHT") is False
    assert fresh.state == "UNKNOWN"


def test_unreadable_load_is_unknown(monkeypatch):
    controller = HostPressureController()
    monkeypatch.delenv("COURIER_MOCK_HOST_PRESSURE", raising=False)

    def boom():
        raise OSError("loadavg unreadable")

    with patch("os.getloadavg", boom, create=True):
        assert controller.measure_pressure() == "UNKNOWN"
        assert controller.admit_job("HEAVY") is False

    # Windows has no getloadavg. Absence of the API must still admit the
    # live agy path. Only a failed read refuses admission.
    monkeypatch.delattr(os, "getloadavg", raising=False)
    assert controller.measure_pressure() == "GREEN"
    assert controller.admit_job("HEAVY") is True


def test_get_poll_interval():
    controller = HostPressureController()
    
    controller.state = "GREEN"
    assert controller.get_poll_interval() == 5
    
    controller.state = "YELLOW"
    assert controller.get_poll_interval() == 10
    
    controller.state = "ORANGE"
    assert controller.get_poll_interval() == 20
    
    controller.state = "RECOVERY"
    # min(30, RECOVERY_WINDOW) -> 30
    assert controller.get_poll_interval() == 30
