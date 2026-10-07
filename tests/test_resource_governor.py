"""Host pressure admission: memory, swap, and fail-closed probe failure.

No test reads the real host. Load and psutil are injected, or the probe
functions are replaced before admission runs.
"""

import ast
import os
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.resource_governor import (
    HostPressureController,
    classify,
    governor,
    read_metrics,
)

ROOT = Path(__file__).resolve().parents[1]
GOVERNOR_PATH = ROOT / "scripts" / "resource_governor.py"


def _boom(*_args, **_kwargs):
    raise AssertionError("test read the real host probe")


@pytest.fixture(autouse=True)
def _no_real_host(monkeypatch):
    """Replace host probes for every test in this module."""
    monkeypatch.setattr(os, "getloadavg", _boom, raising=False)
    blocked = types.ModuleType("psutil")
    blocked.virtual_memory = _boom
    blocked.swap_memory = _boom
    monkeypatch.setitem(sys.modules, "psutil", blocked)


def _install_psutil(monkeypatch, avail_pct, swap_pct, total=10000):
    mod = types.ModuleType("psutil")
    available = total * (avail_pct / 100.0)
    mod.virtual_memory = lambda: SimpleNamespace(available=available, total=total)
    mod.swap_memory = lambda: SimpleNamespace(percent=swap_pct)
    monkeypatch.setitem(sys.modules, "psutil", mod)


def _metrics(load, avail, swap):
    return {
        "load_per_core": load,
        "avail_mem_pct": avail,
        "swap_used_pct": swap,
    }


INCIDENT = _metrics(3.9, 5, 88)


@pytest.mark.parametrize(
    "metrics,level,pressure",
    [
        pytest.param(None, "UNKNOWN", "UNKNOWN", id="metrics-none"),
        pytest.param(_metrics(0.5, None, None), "UNKNOWN", "UNKNOWN", id="memory-both-none"),
        pytest.param(_metrics(3.9, None, None), "UNKNOWN", "UNKNOWN", id="load-cannot-replace-memory"),
        pytest.param(_metrics(None, 5, None), "CRITICAL", "RED", id="avail-only-critical"),
        pytest.param(_metrics(0.5, None, 90), "PRESSURED", "ORANGE", id="swap-only-pressured"),
        pytest.param(_metrics(0.5, 9.9, 0), "CRITICAL", "RED", id="avail-9.9"),
        pytest.param(_metrics(0.5, 10, 0), "PRESSURED", "ORANGE", id="avail-10"),
        pytest.param(_metrics(0.5, 24.9, 0), "PRESSURED", "ORANGE", id="avail-24.9"),
        pytest.param(_metrics(0.5, 25, 0), "NORMAL", "GREEN", id="avail-25"),
        pytest.param(_metrics(0.5, 50, 49), "NORMAL", "GREEN", id="swap-49"),
        pytest.param(_metrics(0.5, 50, 50), "PRESSURED", "ORANGE", id="swap-50"),
        pytest.param(_metrics(0.5, 50, 79), "PRESSURED", "ORANGE", id="swap-79"),
        pytest.param(_metrics(0.5, 50, 80), "PRESSURED", "ORANGE", id="swap-80-healthy-avail"),
        pytest.param(_metrics(0.5, 24.9, 80), "CRITICAL", "RED", id="swap-80-avail-24.9"),
        pytest.param(_metrics(0.5, 25, 80), "PRESSURED", "ORANGE", id="swap-80-avail-25"),
        pytest.param(_metrics(0.5, 24.9, 79), "PRESSURED", "ORANGE", id="swap-79-avail-24.9"),
        pytest.param(_metrics(0.5, 50, 0), "NORMAL", "GREEN", id="load-0.5"),
        pytest.param(_metrics(1.0, 50, 0), "NORMAL", "GREEN", id="load-1.0"),
        pytest.param(_metrics(1.01, 50, 0), "NORMAL", "YELLOW", id="load-1.01"),
        pytest.param(_metrics(1.5, 50, 0), "NORMAL", "YELLOW", id="load-1.5"),
        pytest.param(_metrics(1.51, 50, 0), "PRESSURED", "ORANGE", id="load-1.51"),
        pytest.param(_metrics(2.0, 50, 0), "PRESSURED", "ORANGE", id="load-2.0"),
        pytest.param(_metrics(2.01, 50, 0), "CRITICAL", "RED", id="load-2.01"),
        pytest.param(_metrics(None, 50, 0), "NORMAL", "GREEN", id="load-none-healthy-memory"),
        pytest.param(INCIDENT, "CRITICAL", "RED", id="incident"),
    ],
)
def test_classify_and_legacy_pressure(metrics, level, pressure):
    assert classify(metrics) == level
    controller = HostPressureController()
    with patch("scripts.resource_governor.read_metrics", return_value=metrics):
        assert controller.measure_pressure() == pressure


def test_load_probe_oserror_is_unknown_and_refuses_heavy():
    """os.getloadavg OSError is UNKNOWN, and HEAVY work is not admitted."""
    controller = HostPressureController()
    with patch("os.getloadavg", side_effect=OSError("probe failed"), create=True):
        assert read_metrics() is None
        assert controller.measure_pressure() == "UNKNOWN"
        assert controller.admit_job("HEAVY") is False


def test_load_probe_oserror_refuses_medium_admits_light_without_quiesce():
    controller = HostPressureController()
    with patch("os.getloadavg", side_effect=OSError("probe failed"), create=True):
        assert controller.admit_job("MEDIUM") is False
        assert controller.state == "UNKNOWN"
        assert controller.recovery_end_time == 0
        assert controller.get_poll_interval() == 20
        assert controller.admit_job("LIGHT") is True
        assert controller.state == "UNKNOWN"
        assert controller.recovery_end_time == 0


def test_psutil_missing_and_load_error_refuses_heavy_admits_light(monkeypatch):
    def _load_error():
        raise OSError("load")

    monkeypatch.setattr(os, "getloadavg", _load_error, raising=False)
    monkeypatch.setitem(sys.modules, "psutil", None)
    controller = HostPressureController()
    assert read_metrics() is None
    assert controller.measure_pressure() == "UNKNOWN"
    assert controller.admit_job("HEAVY") is False
    assert controller.admit_job("MEDIUM") is False
    assert controller.state == "UNKNOWN"
    assert controller.get_poll_interval() == HostPressureController.POLL_INTERVAL_BASE * 4
    assert controller.recovery_end_time == 0
    assert controller.admit_job("LIGHT") is True
    assert controller.state == "UNKNOWN"


def test_psutil_missing_with_readable_load_is_unknown(monkeypatch):
    monkeypatch.setattr(os, "getloadavg", lambda: (0.4, 0.0, 0.0), raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    monkeypatch.setitem(sys.modules, "psutil", None)
    metrics = read_metrics()
    assert metrics["load_per_core"] == 0.1
    assert metrics["avail_mem_pct"] is None
    assert metrics["swap_used_pct"] is None
    controller = HostPressureController()
    assert controller.measure_pressure() == "UNKNOWN"
    assert controller.admit_job("HEAVY") is False
    assert controller.admit_job("LIGHT") is True


def test_psutil_exception_marks_both_memory_readings_unknown(monkeypatch):
    monkeypatch.setattr(os, "getloadavg", lambda: (1.0, 0.0, 0.0), raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    mod = types.ModuleType("psutil")

    def _fail():
        raise RuntimeError("virtual_memory failed")

    mod.virtual_memory = _fail
    mod.swap_memory = lambda: SimpleNamespace(percent=0)
    monkeypatch.setitem(sys.modules, "psutil", mod)
    metrics = read_metrics()
    assert metrics["load_per_core"] == 0.25
    assert metrics["avail_mem_pct"] is None
    assert metrics["swap_used_pct"] is None
    assert classify(metrics) == "UNKNOWN"


def test_zero_memory_total_is_unknown(monkeypatch):
    monkeypatch.setattr(os, "getloadavg", lambda: (0.0, 0.0, 0.0), raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    mod = types.ModuleType("psutil")
    mod.virtual_memory = lambda: SimpleNamespace(available=0, total=0)
    mod.swap_memory = lambda: SimpleNamespace(percent=0)
    monkeypatch.setitem(sys.modules, "psutil", mod)
    metrics = read_metrics()
    assert metrics["load_per_core"] == 0.0
    assert metrics["avail_mem_pct"] is None
    assert metrics["swap_used_pct"] is None
    assert classify(metrics) == "UNKNOWN"


def test_read_metrics_combines_load_and_memory(monkeypatch):
    monkeypatch.setattr(os, "getloadavg", lambda: (2.0, 1.0, 1.0), raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    _install_psutil(monkeypatch, avail_pct=50.0, swap_pct=12.5, total=8)
    assert read_metrics() == {
        "load_per_core": 0.5,
        "avail_mem_pct": 50.0,
        "swap_used_pct": 12.5,
    }


def test_windows_without_getloadavg_healthy_memory_is_green(monkeypatch):
    monkeypatch.delattr(os, "getloadavg", raising=False)
    _install_psutil(monkeypatch, avail_pct=50.0, swap_pct=0.0, total=8)
    metrics = read_metrics()
    assert metrics["load_per_core"] is None
    assert metrics["avail_mem_pct"] == 50.0
    assert metrics["swap_used_pct"] == 0.0
    assert HostPressureController().measure_pressure() == "GREEN"


def test_windows_without_getloadavg_low_memory_is_red(monkeypatch):
    monkeypatch.delattr(os, "getloadavg", raising=False)
    _install_psutil(monkeypatch, avail_pct=8.0, swap_pct=0.0)
    assert classify(read_metrics()) == "CRITICAL"
    assert HostPressureController().measure_pressure() == "RED"


def test_orange_rejection_sets_state_and_interval():
    controller = HostPressureController()
    with patch.object(controller, "measure_pressure", return_value="ORANGE"):
        assert controller.admit_job("HEAVY") is False
        assert controller.state == "ORANGE"
        assert controller.get_poll_interval() == 20
        assert controller.recovery_end_time == 0
        assert controller.admit_job("MEDIUM") is False
        assert controller.state == "ORANGE"
        assert controller.admit_job("LIGHT") is True
        assert controller.state == "ORANGE"


def test_incident_vector_is_critical_red_and_quiesces():
    assert classify(INCIDENT) == "CRITICAL"
    controller = HostPressureController()
    with patch("scripts.resource_governor.read_metrics", return_value=dict(INCIDENT)):
        assert controller.measure_pressure() == "RED"
        assert controller.admit_job("HEAVY") is False
        assert controller.state == "RECOVERY"
        assert controller.recovery_end_time > time.time()


def test_legacy_limits_and_singleton():
    assert HostPressureController.MAX_HEAVY_JOBS == 1
    assert HostPressureController.POLL_INTERVAL_BASE == 5
    assert HostPressureController.RECOVERY_WINDOW == 300
    assert isinstance(governor, HostPressureController)


def test_governor_source_does_not_spawn_or_signal():
    tree = ast.parse(GOVERNOR_PATH.read_text(encoding="utf-8"))
    banned_attrs = {"kill", "killpg", "Popen", "check_output", "system"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "subprocess" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess"
        elif isinstance(node, ast.Attribute):
            assert node.attr not in banned_attrs


def test_post_run_snapshot_uses_injected_load(monkeypatch):
    monkeypatch.setattr(os, "getloadavg", lambda: (1.0, 2.0, 3.0), raising=False)
    controller = HostPressureController()
    controller.state = "YELLOW"
    snap = controller.post_run_resource_snapshot()
    assert snap["load"] == (1.0, 2.0, 3.0)
    assert snap["state"] == "YELLOW"
    assert isinstance(snap["timestamp"], float)


def test_post_run_snapshot_without_getloadavg(monkeypatch):
    monkeypatch.delattr(os, "getloadavg", raising=False)
    snap = HostPressureController().post_run_resource_snapshot()
    assert snap["load"] is None


# --- cases ported from main:tests/test_resource_governor.py ---
# Healthy memory is injected so the legacy load ladder is what varies.


def test_host_pressure_green(monkeypatch):
    _install_psutil(monkeypatch, 50.0, 0.0, total=8)
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(0.5, 0.5, 0.5), create=True):
        with patch("os.cpu_count", return_value=4):
            assert controller.measure_pressure() == "GREEN"


def test_host_pressure_yellow(monkeypatch):
    _install_psutil(monkeypatch, 50.0, 0.0, total=8)
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(5.0, 4.0, 3.0), create=True):
        with patch("os.cpu_count", return_value=4):
            # load 5.0 / 4 = 1.25 -> YELLOW
            assert controller.measure_pressure() == "YELLOW"


def test_host_pressure_orange(monkeypatch):
    _install_psutil(monkeypatch, 50.0, 0.0, total=8)
    controller = HostPressureController()
    with patch("os.getloadavg", return_value=(7.0, 6.0, 5.0), create=True):
        with patch("os.cpu_count", return_value=4):
            # load 7.0 / 4 = 1.75 -> ORANGE
            assert controller.measure_pressure() == "ORANGE"


def test_host_pressure_red(monkeypatch):
    _install_psutil(monkeypatch, 50.0, 0.0, total=8)
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


def test_green_under_cap_admits_heavy():
    controller = HostPressureController()
    with patch.object(controller, "measure_pressure", return_value="GREEN"):
        assert controller.admit_job("HEAVY") is True
        assert controller.state == "GREEN"


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


def test_get_poll_interval():
    controller = HostPressureController()

    controller.state = "GREEN"
    assert controller.get_poll_interval() == 5

    controller.state = "YELLOW"
    assert controller.get_poll_interval() == 10

    controller.state = "ORANGE"
    assert controller.get_poll_interval() == 20

    controller.state = "UNKNOWN"
    assert controller.get_poll_interval() == 20

    controller.state = "RECOVERY"
    # min(30, RECOVERY_WINDOW) -> 30
    assert controller.get_poll_interval() == 30
