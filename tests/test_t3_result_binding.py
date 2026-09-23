import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch

from scripts.cannon_motor import CannonMotor, MotorError
from scripts.work_queue import main as wq_main

def test_result_binding(tmp_path):
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
    
    motor = CannonMotor(state_dir, behaviors={"t1": "ok"})
    motor.start(mode="FINITE", limit=1, local_fake=False)
    motor.run_step()
    
    artifact = state_dir / "results" / "t1.result.json"
    assert artifact.exists(), "Result artifact was not written!"
    
    data = json.loads(artifact.read_text())
    assert data["task_id"] == "t1", "Artifact task_id mismatch!"
    
    # Reload raw queue
    raw = json.loads(qfile.read_text())
    assert raw["tasks"]["t1"]["status"] == "DONE"
    
    # Add second task
    raw["tasks"]["t2"] = {
        "task_id": "t2",
        "status": "READY",
        "executor_kind": "LOCAL_FAKE"
    }
    qfile.write_text(json.dumps(raw))
    
    def malicious_executor(results_dir, task_id, behavior="ok", check_stop=None):
        res_id = "t2:r1"
        malicious_artifact = Path(results_dir) / f"{task_id}.result.json"
        payload = {"result_id": res_id, "task_id": "t1", "outcome": "ok"} # mismatch!
        malicious_artifact.write_text(json.dumps(payload))
        return ("ok", res_id)
        
    motor.m["start_limit"] = 2
    motor.m["state"] = "RUNNING"
    motor._save()
    
    with patch("scripts.cannon_motor.deterministic_executor", side_effect=malicious_executor):
        motor.run_step()
        
    raw2 = json.loads(qfile.read_text())
    
    assert raw2["tasks"]["t2"]["status"] != "DONE", "Motor accepted a result with mismatched task_id!"
    assert motor.m["state"] in ("ERROR", "BLOCKED"), "Motor did not halt on mismatched result!"

