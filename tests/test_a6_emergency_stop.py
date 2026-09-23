import time
import pytest
import os
from pathlib import Path
from scripts.cannon_motor import CannonMotor
from scripts.mac_adapter import MacAdapter

def test_emergency_stop_response_time(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake")
    
    motor = adapter.motor
    motor.m["cooldown_seconds"] = 10.0
    motor.m["run_id"] = "test-run"
    motor.m["state"] = "RUNNING"
    motor.m["current_task"] = None
    motor.m["run_mode"] = "FINITE"
    motor.m["local_fake"] = True
    motor._save()
    
    import threading
    def request_stop_soon():
        time.sleep(1.0)
        (tmp_path / "STOP").write_text("")
        
    threading.Thread(target=request_stop_soon).start()
    
    start = time.time()
    ret = motor.run_step()
    duration = time.time() - start
    
    print("RET:", ret)
    print("M:", motor.m)
    
    assert duration < 2.5, f"Took {duration}s, should be < 2.5s!"
    assert motor.state in ("IDLE", "COMPLETED", "PAUSED")
    assert motor.m.get("stop_requested") == True

def test_stop_command_response_time(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake2")
    
    motor = adapter.motor
    motor.m["cooldown_seconds"] = 10.0
    motor.m["run_id"] = "test-run-2"
    motor.m["state"] = "RUNNING"
    motor.m["current_task"] = None
    motor.m["run_mode"] = "FINITE"
    motor.m["local_fake"] = True
    motor._save()
    
    import threading
    def request_stop_soon():
        time.sleep(1.0)
        motor2 = CannonMotor(tmp_path)
        motor2.request_stop()
        
    threading.Thread(target=request_stop_soon).start()
    
    start = time.time()
    motor.run_step()
    duration = time.time() - start
    
    assert duration < 2.5, f"Took {duration}s, should be < 2.5s!"
    assert motor.m.get("stop_requested") == True
