import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from scripts.windows_muse_wall.supervisor import MuseWallSupervisor
from scripts.windows_muse_wall.slot_state import StateCorruptionError, default_slot, atomic_write

@pytest.fixture
def supervisor(tmp_path):
    config = {
        "desired_slots": 64,
        "active_limit": 0,
        "provider_launch_enabled": False,
        "staged_levels": [1, 4, 8, 16, 32, 64],
        "minimum_free_memory_mb": 2500,
        "account_roles": {}
    }
    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    
    sup = MuseWallSupervisor(tmp_path, config=config)
    sup.initialize()
    return sup

def test_generate_64_slots(supervisor):
    status = supervisor.status()
    assert status["desired_slots"] == 64
    assert status["defined_slots"] == 64
    assert status["states"]["READY"] == 64
    
    # Check that directories exist
    assert (supervisor.slots_root / "MUSE-64" / "workdir").exists()

def test_slot_workdirs_are_unique(supervisor):
    workdirs = set()
    for i in range(1, supervisor.desired_slots + 1):
        slot = supervisor.load_slot(supervisor.slot_id(i))
        workdirs.add(slot["workdir"])
    assert len(workdirs) == 64

def test_log_paths_are_isolated(supervisor):
    for i in range(1, 65):
        slot_id = supervisor.slot_id(i)
        log_dir = supervisor.slot_dir(slot_id) / "logs"
        assert log_dir.exists()
        assert log_dir.is_dir()

def test_provider_disabled_by_default(supervisor):
    res = supervisor.start_slot("MUSE-01", ["python", "-c", "import time; time.sleep(10)"])
    assert res["started"] is False
    assert res["reason"] == "provider_launch_disabled"

def test_duplicate_slot_start_blocked(supervisor):
    supervisor.config["provider_launch_enabled"] = True
    res1 = supervisor.start_slot("MUSE-01", [sys.executable, "-c", "import time; time.sleep(10)"])
    assert res1["started"] is True
    
    res2 = supervisor.start_slot("MUSE-01", [sys.executable, "-c", "import time; time.sleep(10)"])
    assert res2["started"] is False
    assert res2["reason"] == "already_running"
    
    supervisor.stop_slot("MUSE-01")

def test_live_pid_preserved(supervisor):
    supervisor.config["provider_launch_enabled"] = True
    supervisor.start_slot("MUSE-02", [sys.executable, "-c", "import time; time.sleep(10)"])
    
    slot = supervisor.reconcile_slot("MUSE-02")
    assert slot["process"] is not None
    assert slot["state"] == "IDLE"
    
    supervisor.stop_slot("MUSE-02")

def test_stale_pid_reclaimed(supervisor):
    # Simulate a crashed process
    supervisor.config["provider_launch_enabled"] = True
    res = supervisor.start_slot("MUSE-03", [sys.executable, "-c", "pass"])
    assert res["started"] is True
    pid = res["slot"]["process"]["pid"]
    
    # wait for process to naturally exit
    try:
        psutil.Process(pid).wait(timeout=3)
    except psutil.NoSuchProcess:
        pass
        
    slot = supervisor.reconcile_slot("MUSE-03")
    assert slot["process"] is None
    assert slot["state"] == "CRASHED"

def test_pid_reuse_detected(supervisor):
    # If a PID is reused, the create_time won't match.
    # We simulate this by mutating the state JSON manually.
    supervisor.config["provider_launch_enabled"] = True
    res = supervisor.start_slot("MUSE-04", [sys.executable, "-c", "import time; time.sleep(10)"])
    pid = res["slot"]["process"]["pid"]
    
    slot = supervisor.load_slot("MUSE-04")
    # Shift create_time significantly to pretend it's a reused PID
    slot["process"]["create_time"] -= 10000.0
    supervisor.save_slot(slot)
    
    # Now reconcile
    reconciled = supervisor.reconcile_slot("MUSE-04")
    assert reconciled["process"] is None
    assert reconciled["state"] == "CRASHED"
    
    supervisor.stop_slot("MUSE-04")

def test_single_slot_stop_isolated(supervisor):
    supervisor.config["provider_launch_enabled"] = True
    supervisor.start_slot("MUSE-05", [sys.executable, "-c", "import time; time.sleep(10)"])
    supervisor.start_slot("MUSE-06", [sys.executable, "-c", "import time; time.sleep(10)"])
    
    supervisor.stop_slot("MUSE-05")
    
    slot5 = supervisor.load_slot("MUSE-05")
    slot6 = supervisor.load_slot("MUSE-06")
    
    assert slot5["process"] is None
    assert slot6["process"] is not None
    
    supervisor.stop_slot("MUSE-06")

def test_unrelated_process_survives(supervisor):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    # Not tracked by supervisor
    supervisor.stop_slot("MUSE-07")
    
    # Our unrelated process should still be alive
    assert proc.poll() is None
    proc.terminate()
    proc.wait()

def test_staged_capacity_governor(supervisor):
    assert supervisor.admitted_count(1) == 0  # active limit is 0
    
    supervisor.config["active_limit"] = 16
    assert supervisor.admitted_count(4) == 4
    assert supervisor.admitted_count(16) == 16
    assert supervisor.admitted_count(32) == 16 # Capped by active_limit
    
    with pytest.raises(ValueError):
        supervisor.admitted_count(3) # Not in staged_levels

def test_corrupt_state_fails_closed(supervisor):
    state_path = supervisor.state_path("MUSE-08")
    with open(state_path, "w") as f:
        f.write("invalid json")
        
    with pytest.raises(StateCorruptionError):
        supervisor.load_slot("MUSE-08")
        
    status = supervisor.status()
    # It should count as blocked in status
    assert status["states"].get("BLOCKED", 0) > 0

def test_restart_restores_metadata(supervisor):
    slot = supervisor.load_slot("MUSE-09")
    slot["state"] = "WORKING"
    supervisor.save_slot(slot)
    
    # Reload from fresh supervisor instance
    sup2 = MuseWallSupervisor(supervisor.root, config=supervisor.config)
    sup2.initialize()
    slot2 = sup2.load_slot("MUSE-09")
    assert slot2["state"] == "WORKING"

def test_restart_does_not_auto_launch_provider(supervisor):
    supervisor.config["provider_launch_enabled"] = True
    supervisor.start_slot("MUSE-10", [sys.executable, "-c", "import time; time.sleep(10)"])
    
    sup2 = MuseWallSupervisor(supervisor.root, config=supervisor.config)
    # Even if provider_launch is True, initialize() doesn't auto-start things.
    sup2.initialize()
    
    slot2 = sup2.reconcile_slot("MUSE-10")
    # It should still recognize the running process though
    assert slot2["process"] is not None
    assert slot2["state"] == "IDLE"
    
    sup2.stop_slot("MUSE-10")
