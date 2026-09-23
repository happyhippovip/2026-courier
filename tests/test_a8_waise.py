import json
import pytest
from scripts.cannon_motor import CannonMotor, MotorError
from scripts.mac_adapter import MacAdapter
from pathlib import Path

def test_a8_orphaned_result_binding_rejected(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake")
    motor = adapter.motor
    
    motor.m["state"] = "RUNNING"
    motor.m["run_mode"] = "FINITE"
    motor.m["start_limit"] = 1
    motor.m["started_count"] = 0
    motor.m["completed_runs"] = 0
    motor._save()
    
    task_id = "t1" 
    
    results_dir = tmp_path / "results"
    results_dir.mkdir(exist_ok=True)
    
    result_id = f"{task_id}:r1"
    artifact = results_dir / f"{task_id}.result.json"
    payload = {
        "result_id": result_id,
        "task_id": task_id,
        "worker_id": "orphaned_worker",
        "attempt_id": f"{task_id}:a99",
        "dispatch_id": "old_dispatch",
        "outcome": "ok"
    }
    artifact.write_text(json.dumps(payload))
    
    import scripts.cannon_motor
    old_exec = scripts.cannon_motor.deterministic_executor
    def mock_executor(*args, **kwargs):
        return ("ok", result_id)
    scripts.cannon_motor.deterministic_executor = mock_executor
    
    try:
        report = motor.run_step()
    finally:
        scripts.cannon_motor.deterministic_executor = old_exec
        
    assert report["step"] == "error"
    assert "current_result_binding_rejected" in report["error"]
    assert motor.m["state"] == "BLOCKED"
    
def test_a8_cmd_complete_rejects_wrong_attempt_id(tmp_path):
    adapter = MacAdapter(str(tmp_path))
    adapter.seed(1, package="fake")
    motor = adapter.motor
    
    claimed = motor._wq("claim", "--worker", "current_worker")
    task_id = claimed["claimed"]
    
    queue_state = motor._wq("state")
    task = queue_state["tasks"][task_id]
    
    res = motor._wq("complete", task_id, 
        "--result-json", '{"result_id": "r1"}', 
        "--worker-id", "wrong_worker",
        "--attempt-id", task["attempt_id"])
    
    assert res.get("error") == "wrong worker_id"
    
    res = motor._wq("complete", task_id, 
        "--result-json", '{"result_id": "r1"}', 
        "--worker-id", task["worker_id"],
        "--attempt-id", "wrong_attempt")
        
    assert res.get("error") == "wrong attempt_id"
    
    res = motor._wq("complete", task_id, 
        "--result-json", '{"result_id": "r1"}', 
        "--worker-id", task["worker_id"],
        "--attempt-id", task["attempt_id"])
        
    assert "done" in res
