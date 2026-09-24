import copy
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from scripts.windows_muse_wall.supervisor import MuseWallSupervisor
from scripts.windows_muse_wall.slot_state import atomic_write


BASE_CONFIG = {
    "desired_slots": 64,
    "active_limit": 0,
    "provider_launch_enabled": False,
    "staged_levels": [1, 4, 8, 16, 32, 64],
    "minimum_free_memory_mb": 2500,
}


def wall(tmp_path, **overrides):
    config = copy.deepcopy(BASE_CONFIG)
    config.update(overrides)
    supervisor = MuseWallSupervisor(tmp_path, config)
    supervisor.initialize()
    return supervisor


def sleeper():
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


def finish(process):
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


def test_same_slot_cannot_start_twice(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True, active_limit=1)
    first = supervisor.start_slot("MUSE-01", [sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        second = supervisor.start_slot("MUSE-01", [sys.executable, "-c", "import time; time.sleep(60)"])
        assert first["started"] is True
        assert second["reason"] == "already_running"
    finally:
        supervisor.stop_slot("MUSE-01")


def test_stale_pid_creation_time_is_reclaimed_without_killing_live_process(tmp_path):
    supervisor = wall(tmp_path)
    unrelated = sleeper()
    try:
        slot = supervisor.load_slot("MUSE-01")
        slot["state"] = "WORKING"
        slot["process"] = {"pid": unrelated.pid, "create_time": psutil.Process(unrelated.pid).create_time() + 99, "owner_token": slot["owner_token"]}
        supervisor.save_slot(slot)
        recovered = supervisor.reconcile_slot("MUSE-01")
        assert recovered["state"] == "CRASHED"
        assert recovered["process"] is None
        assert unrelated.poll() is None
    finally:
        finish(unrelated)


def test_stop_slot_only_stops_exact_owned_process(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True)
    unrelated = sleeper()
    try:
        started = supervisor.start_slot("MUSE-01", [sys.executable, "-c", "import time; time.sleep(60)"])
        assert started["started"] is True
        assert supervisor.stop_slot("MUSE-01")["stopped"] is True
        assert unrelated.poll() is None
    finally:
        finish(unrelated)


def test_initialization_generates_64_isolated_slot_configs(tmp_path):
    supervisor = wall(tmp_path)
    status = supervisor.status()
    assert status["defined_slots"] == 64
    assert len({supervisor.load_slot(supervisor.slot_id(i))["workdir"] for i in range(1, 65)}) == 64


@pytest.mark.parametrize("level", [1, 4, 8, 16, 32, 64])
def test_admission_governor_respects_approved_levels(tmp_path, level):
    supervisor = wall(tmp_path, active_limit=64)
    assert supervisor.admitted_count(level) == level
    supervisor.config["active_limit"] = 0
    assert supervisor.admitted_count(level) == 0


def test_default_provider_launch_is_disabled(tmp_path):
    supervisor = wall(tmp_path)
    result = supervisor.start_slot("MUSE-01", [sys.executable, "-c", "raise SystemExit(99)"])
    assert result["started"] is False
    assert result["reason"] == "provider_launch_disabled"
    assert supervisor.load_slot("MUSE-01")["state"] == "READY"


def test_restart_restores_metadata_without_provider_autolaunch(tmp_path):
    first = wall(tmp_path)
    slot = first.load_slot("MUSE-01")
    slot["state"] = "WAITING"
    first.save_slot(slot)
    restarted = MuseWallSupervisor(tmp_path, copy.deepcopy(BASE_CONFIG))
    restarted.initialize()
    assert restarted.load_slot("MUSE-01")["state"] == "WAITING"
    assert restarted.status()["states"]["READY"] == 63
    assert restarted.status()["provider_launch_enabled"] is False


def test_corrupt_state_fails_closed(tmp_path):
    supervisor = wall(tmp_path)
    supervisor.state_path("MUSE-01").write_text("not-json", encoding="utf-8")
    assert supervisor.status()["states"]["BLOCKED"] == 1


def test_no_admin_elevation_is_required(tmp_path):
    supervisor = wall(tmp_path)
    assert supervisor.config.get("requires_admin", False) is False
    assert supervisor.status()["defined_slots"] == 64
