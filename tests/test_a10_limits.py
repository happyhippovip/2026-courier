import pytest
from scripts.cannon_motor import CannonMotor
from scripts.mac_adapter import MacAdapter
from pathlib import Path
import json

def test_a10_start_limit_enforced_across_crashes(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    # We seed 3 tasks
    adapter.seed(1, package="fake")
    adapter.seed(2, package="fake")
    adapter.seed(3, package="fake")
    
    motor = adapter.motor
    motor.start(mode="FINITE", limit=2, local_fake=True)
    
    # Run the first task successfully
    report1 = motor.run_step()
    
    # Now simulate a crash while picking up the second task
    # Then user manually forces state back to IDLE to retry
    motor.m["state"] = "IDLE"
    motor.m["current_task"] = None
    motor._save()
    
    # A new process starts and user tries to restart
    motor2 = CannonMotor(str(tmp_path))
    
    # User tries to bypass the limit by restarting with limit=2
    # Expectation: it resumes the old run, doesn't reset started_count to 0
    motor2.start(mode="FINITE", limit=2, local_fake=True)
    
    # Run the second task
    report2 = motor2.run_step()
    
    # Try to run the third task - should hit limit!
    report3 = motor2.run_step()
    
    assert report3["step"] == "limit_reached"
    assert motor2.m["state"] == "COMPLETED"
    assert motor2.m["started_count"] == 2
