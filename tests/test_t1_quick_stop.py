import pytest
import threading
import time
import json
import shutil
from pathlib import Path

from scripts.cannon_motor import CannonMotor, deterministic_executor

def test_quick_stop(tmp_path):
    state_dir = tmp_path / "motor_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    motor = CannonMotor(state_dir, behaviors={"local-fake-run-1-1": "slow:10"})
    
    res = motor.start(mode="FINITE", limit=1, local_fake=True)
    assert res.get("started"), f"Motor failed to start: {res}"
    
    motor.m["run_id"] = "run-1"
    motor._save()
    
    results = []
    def run_motor():
        results.append(motor.run_step())
        
    t = threading.Thread(target=run_motor)
    t.start()
    
    time.sleep(1.0)
    
    start_time = time.time()
    motor.request_stop()
    
    t.join(timeout=10.0)
    duration = time.time() - start_time
    
    assert not t.is_alive(), "Motor did not stop quickly enough!"
    assert duration < 5.0, f"Motor took {duration}s to stop, expected < 5s"
    
    snap = motor.queue_snapshot()
    # It shouldn't be DONE if it was aborted
    assert snap["tasks"]["local-fake-run-1-1"]["status"] in ("READY", "CLAIMED")
    
    assert results[0]["step"] == "aborted"

