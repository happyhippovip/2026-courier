"""Gap coverage for the Windows Muse Wall (MISSION_ID=MUSE_C_WALL_TEST_GAPS).

Tests ONLY: no runtime implementation file is modified here. Every test
below pins behavior already specified by existing code/design:

- scripts/windows_muse_wall/supervisor.py (MuseWallSupervisor)
- scripts/windows_muse_wall/slot_state.py (SlotLock, read_json, default_slot)
- scripts/windows_muse_wall/config.json (shipped safe defaults)

Already covered elsewhere (not duplicated here):
- unique slot workdirs, duplicate start rejection, stale PID recovery,
  single-slot stop isolation, unrelated process survival, restart/restore,
  corrupt-status fail-closed, provider-disabled default, staged admission
  levels, safe-slot plumbing, no---yolo/sandbox static guards
  (see test_windows_muse_wall.py, test_muse_wall_launcher_ps1.py,
  test_launch_safe_slot_ps1.py, test_muse_safe_slot.py).
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from scripts.windows_muse_wall.slot_state import (
    SlotLock,
    StateCorruptionError,
    process_matches,
    read_json,
)
from scripts.windows_muse_wall.supervisor import MuseWallSupervisor

BASE_CONFIG = {
    "desired_slots": 64,
    "active_limit": 0,
    "provider_launch_enabled": False,
    "staged_levels": [1, 4, 8, 16, 32, 64],
    "minimum_free_memory_mb": 2500,
}

WALL_DIR = Path(__file__).resolve().parent.parent / "scripts" / "windows_muse_wall"

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def wall(tmp_path, **overrides):
    config = copy.deepcopy(BASE_CONFIG)
    config.update(overrides)
    supervisor = MuseWallSupervisor(tmp_path, config)
    supervisor.initialize()
    return supervisor


def finish_supervised(supervisor, slot_id):
    try:
        supervisor.stop_slot(slot_id)
    except Exception:
        slot = supervisor.load_slot(slot_id)
        process = slot.get("process")
        if process:
            try:
                psutil.Process(process["pid"]).kill()
            except psutil.Error:
                pass


# --- one real slot identity --------------------------------------------------

def test_started_slot_records_live_process_identity(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True, active_limit=1)
    result = supervisor.start_slot("MUSE-01", SLEEPER)
    try:
        assert result["started"] is True
        slot = supervisor.load_slot("MUSE-01")
        record = slot["process"]
        assert record["pid"] > 0
        assert psutil.pid_exists(record["pid"])
        assert process_matches(record) is True
        assert record["owner_token"] == slot["owner_token"]
        assert slot["state"] == "IDLE"
        assert slot["slot_id"] == "MUSE-01"
    finally:
        finish_supervised(supervisor, "MUSE-01")


def test_owner_tokens_unique_across_wall(tmp_path):
    supervisor = wall(tmp_path)
    tokens = [supervisor.load_slot(supervisor.slot_id(i))["owner_token"] for i in range(1, 65)]
    assert len(set(tokens)) == 64
    assert all(supervisor.load_slot(supervisor.slot_id(i))["state"] == "READY" for i in range(1, 65))


# --- unique state/lock/log paths ---------------------------------------------

def test_unique_state_lock_log_paths_across_wall(tmp_path):
    supervisor = wall(tmp_path)
    state_paths = set()
    lock_paths = set()
    log_dirs = set()
    for i in range(1, 65):
        slot_id = supervisor.slot_id(i)
        state_paths.add(supervisor.state_path(slot_id))
        lock_paths.add(supervisor.slot_dir(slot_id) / "slot.lock")
        log_dir = supervisor.slot_dir(slot_id) / "logs"
        log_dirs.add(log_dir)
        assert log_dir.is_dir()
        assert supervisor.state_path(slot_id).is_file()
    assert len(state_paths) == 64
    assert len(lock_paths) == 64
    assert len(log_dirs) == 64
    assert not (state_paths & lock_paths)


# --- PID reuse rejection (stop path) ------------------------------------------

def test_stop_slot_refuses_pid_reuse_and_spares_live_process(tmp_path):
    supervisor = wall(tmp_path)
    unrelated = subprocess.Popen(SLEEPER)
    try:
        slot = supervisor.load_slot("MUSE-01")
        slot["state"] = "WORKING"
        # Same live PID but a create_time that cannot match: the PID has
        # been "reused" since the record was written.
        slot["process"] = {
            "pid": unrelated.pid,
            "create_time": psutil.Process(unrelated.pid).create_time() + 99,
            "owner_token": slot["owner_token"],
        }
        supervisor.save_slot(slot)
        result = supervisor.stop_slot("MUSE-01")
        assert result["stopped"] is False
        assert result["reason"] == "no_matching_owned_process"
        assert unrelated.poll() is None
        reread = supervisor.load_slot("MUSE-01")
        assert reread["process"] is None
        assert reread["state"] == "CRASHED"
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
            unrelated.wait(timeout=5)


# --- exact stop isolation across sibling slots ---------------------------------

def test_stop_one_slot_leaves_sibling_slot_running(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True, active_limit=2)
    assert supervisor.start_slot("MUSE-01", SLEEPER)["started"] is True
    assert supervisor.start_slot("MUSE-02", SLEEPER)["started"] is True
    try:
        assert supervisor.stop_slot("MUSE-01")["stopped"] is True
        sibling = supervisor.load_slot("MUSE-02")
        assert process_matches(sibling["process"]) is True
        assert psutil.Process(sibling["process"]["pid"]).is_running()
        assert supervisor.load_slot("MUSE-01")["process"] is None
    finally:
        finish_supervised(supervisor, "MUSE-01")
        finish_supervised(supervisor, "MUSE-02")


# --- reconcile preserves terminal states ---------------------------------------

@pytest.mark.parametrize("terminal", ["DONE", "BLOCKED"])
def test_reconcile_preserves_terminal_states_on_dead_process(tmp_path, terminal):
    supervisor = wall(tmp_path)
    slot = supervisor.load_slot("MUSE-01")
    slot["state"] = terminal
    slot["process"] = {"pid": 999999, "create_time": 0.0, "owner_token": slot["owner_token"]}
    supervisor.save_slot(slot)
    recovered = supervisor.reconcile_slot("MUSE-01")
    assert recovered["process"] is None
    assert recovered["state"] == terminal


# --- corrupt state fail-closed (direct load path) -------------------------------

def test_load_slot_rejects_identity_mismatch(tmp_path):
    from scripts.windows_muse_wall.slot_state import atomic_write, default_slot

    supervisor = wall(tmp_path)
    foreign = default_slot("MUSE-02", supervisor.slot_dir("MUSE-01") / "workdir")
    atomic_write(supervisor.state_path("MUSE-01"), foreign)
    with pytest.raises(StateCorruptionError):
        supervisor.load_slot("MUSE-01")


def test_read_json_rejects_garbage_state(tmp_path):
    supervisor = wall(tmp_path)
    supervisor.state_path("MUSE-01").write_text("not-json", encoding="utf-8")
    with pytest.raises(StateCorruptionError):
        read_json(supervisor.state_path("MUSE-01"))
    with pytest.raises(StateCorruptionError):
        supervisor.load_slot("MUSE-01")


# --- staged capacity guard -------------------------------------------------------

@pytest.mark.parametrize("level", [0, 2, 3, 7, 33, 65])
def test_admit_rejects_unstaged_levels(tmp_path, level):
    supervisor = wall(tmp_path, active_limit=64)
    with pytest.raises(ValueError):
        supervisor.admitted_count(level)


# --- provider start requires an explicit command ----------------------------------

def test_start_slot_without_command_is_denied(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True, active_limit=1)
    result = supervisor.start_slot("MUSE-01", None)
    assert result["started"] is False
    assert result["reason"] == "no_launch_command"
    assert supervisor.load_slot("MUSE-01")["process"] is None


# --- per-slot lock exclusivity -----------------------------------------------------

def test_slot_lock_is_exclusive_and_cleans_up(tmp_path):
    lock_path = tmp_path / "MUSE-01" / "slot.lock"
    with SlotLock(lock_path):
        assert lock_path.is_file()
        with pytest.raises(RuntimeError):
            with SlotLock(lock_path):
                pass
        # Failed acquisition must not remove the live lock.
        assert lock_path.is_file()
    assert not lock_path.exists()


def test_slot_lock_never_deletes_preexisting_lock(tmp_path):
    lock_path = tmp_path / "MUSE-01" / "slot.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("holder", encoding="utf-8")
    with pytest.raises(RuntimeError):
        with SlotLock(lock_path):
            pass
    assert lock_path.read_text(encoding="utf-8") == "holder"


# --- shipped config pins safe defaults ----------------------------------------------

def test_shipped_config_disables_provider_and_pins_stages():
    config = json.loads((WALL_DIR / "config.json").read_text(encoding="utf-8"))
    assert config["provider_launch_enabled"] is False
    assert config["staged_levels"] == [1, 4, 8, 16, 32, 64]
    assert config["desired_slots"] == 64
    assert config["active_limit"] in [0] + config["staged_levels"]
