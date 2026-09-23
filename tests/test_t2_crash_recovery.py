import pytest
import time
import json
import multiprocessing
from pathlib import Path
from unittest.mock import patch

from scripts.cannon_motor import CannonMotor

def run_hanging_motor(state_dir):
    motor = CannonMotor(state_dir, behaviors={"t1": "ok"})
    motor.start(mode="FINITE", limit=2, local_fake=False)
    motor.m["run_id"] = "run-1"
    motor._save()
    
    def hanging_executor(results_dir, task_id, behavior="ok", check_stop=None):
        time.sleep(100) # hang
        return ("ok", f"{task_id}:r1")
        
    with patch("scripts.cannon_motor.deterministic_executor", side_effect=hanging_executor):
        motor.run_step()

def test_motor_crash_recovery(tmp_path):
    state_dir = tmp_path / "motor_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    qfile = state_dir / "queue.json"
    qfile.write_text(json.dumps({
        "tasks": {
            "t1": {
                "task_id": "t1", 
                "status": "READY", 
                "executor_kind": "LOCAL_FAKE"
            }
        },
        "leases": {}
    }))
    
    p = multiprocessing.Process(target=run_hanging_motor, args=(state_dir,))
    p.start()
    time.sleep(1.0)
    
    p.terminate()
    p.join(timeout=5)
    
    motor2 = CannonMotor(state_dir)
    motor2.m["start_limit"] = 2  # Increase limit so it tries to run another step
    res = motor2.run_step()
    print("RES2:", res)
    
    with open(state_dir / "queue.json") as f:
        snap = json.load(f)
    print("QUEUE AFTER MOTOR2:", snap)

