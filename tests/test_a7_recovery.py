import time
import pytest
import os
import signal
import subprocess
import sys
import json
from pathlib import Path
from scripts.cannon_motor import CannonMotor
from scripts.mac_adapter import MacAdapter
from scripts import work_queue

def run_motor_until_crash(state_dir):
    # This runs in a subprocess
    motor = CannonMotor(state_dir)
    motor.behaviors["t1"] = "real_bad"
    try:
        motor.run_step()
    except Exception as e:
        print("EXCEPTION IN CHILD:", e)

def test_recovery_safe_task(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake")
    
    motor = adapter.motor
    motor.start(mode="FINITE", local_fake=True)
    
    # Run in subprocess so the kill only affects the child
    p = subprocess.Popen([sys.executable, "-c", 
        f"from tests.test_a7_recovery import run_motor_until_crash; run_motor_until_crash('{tmp_path}')"
    ])
    p.wait(timeout=5)
    
    # The child should have been killed by SIGKILL in real_bad
    assert p.returncode != 0
    
    motor._load()
    assert motor.m.get("current_task") == "t1"
    
    snap = motor.queue_snapshot()
    assert snap["tasks"]["t1"]["status"] == "CLAIMED"
    
    # Recover
    time.sleep(0.01)
    res = motor.recover()
    assert res["recovered"] == True
    assert res["action"] == "reclaimed_safe"
    
    motor._load()
    assert motor.m.get("current_task") is None
    
    snap2 = motor.queue_snapshot()
    assert snap2["tasks"]["t1"]["status"] == "READY"
    
def test_recovery_ambiguous_task(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake2")
    
    motor = adapter.motor
    motor.start(mode="FINITE", local_fake=True)
    
    # Fake the task to be REAL_MUSE and CLAIMED manually 
    motor._wq("claim", "--worker", "test_worker")
    
    # Update queue to REAL_MUSE directly
    qf = tmp_path / "queue.json"
    data = json.loads(qf.read_text())
    data["tasks"]["t1"]["executor_kind"] = "REAL_MUSE"
    data["tasks"]["t1"]["status"] = "CLAIMED"
    qf.write_text(json.dumps(data))
    
    motor.m["current_task"] = "t1"
    motor.m["state"] = "RUNNING"
    motor._save()
    
    # Recover
    time.sleep(0.01)
    res = motor.recover()
    assert res["recovered"] == True
    assert res["action"] == "failed_closed"
    
    snap = motor.queue_snapshot()
    assert snap["tasks"]["t1"]["status"] == "BLOCKED"
    assert snap["tasks"]["t1"]["block_reason"] == "CRASH_DURING_EXTERNAL_EFFECT"

