import pytest
import json
from pathlib import Path
from scripts.cannon_motor import CannonMotor, MotorError
from scripts.mac_adapter import MacAdapter

def test_a8_artifact_missing_rejected(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake")
    motor = adapter.motor
    
    motor.start(mode="FINITE", limit=1, local_fake=True)
    
    import scripts.cannon_motor
    old_exec = scripts.cannon_motor.deterministic_executor
    def mock_missing(results_dir, task_id, behavior):
        return ("ok", f"{task_id}:r1")
    scripts.cannon_motor.deterministic_executor = mock_missing
    
    try:
        report = motor.run_step()
    finally:
        scripts.cannon_motor.deterministic_executor = old_exec
        
    assert report["step"] == "error"
    assert "ARTIFACT_MISSING" in report["error"]
    assert motor.m["state"] == "BLOCKED"

def test_a8_artifact_mismatch_rejected(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake") # task_id: t1
    motor = adapter.motor
    
    motor.m["state"] = "IDLE"
    motor.start(mode="FINITE", limit=1, local_fake=True)
    
    import scripts.cannon_motor
    old_exec = scripts.cannon_motor.deterministic_executor
    def mock_mismatch(results_dir, task_id, behavior):
        results_dir.mkdir(exist_ok=True, parents=True)
        artifact = results_dir / f"{task_id}.result.json"
        payload = {
            "result_id": "WRONG_ID",
            "task_id": task_id,
            "outcome": "ok"
        }
        artifact.write_text(json.dumps(payload))
        return ("ok", f"{task_id}:r1")
        
    scripts.cannon_motor.deterministic_executor = mock_mismatch
    
    try:
        report = motor.run_step()
    finally:
        scripts.cannon_motor.deterministic_executor = old_exec
        
    assert report["step"] == "error"
    assert "ARTIFACT_MISMATCH" in report["error"]
    assert motor.m["state"] == "BLOCKED"

