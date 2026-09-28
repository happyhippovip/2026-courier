import pytest
from pathlib import Path
import json

def test_execute_bridge_task_dedupe(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as script
    
    # Mock PROCESSED_DIR
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    monkeypatch.setattr(script, "PROCESSED_DIR", processed_dir)
    
    # Create result file
    res_file = processed_dir / "t-1-result.json"
    res_file.write_text("{}")
    
    # Create job file
    job_file = tmp_path / "t-1-worker-job.json"
    job_file.write_text(json.dumps({"task_id": "t-1"}))
    
    class MockHooks:
        pass
        
    res = script.execute_bridge_task(job_file, MockHooks(), force=False)
    assert res == res_file
    
def test_execute_bridge_task_success(tmp_path, monkeypatch):
    import scripts.run_antigravity_bridge as script
    
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    monkeypatch.setattr(script, "PROCESSED_DIR", processed_dir)
    
    job_file = tmp_path / "t-2-worker-job.json"
    job_file.write_text(json.dumps({
        "task_id": "t-2", 
        "instruction": "Do something",
        "allowed_scope": ["tests/test_run_antigravity_bridge.py"]
    }))
    
    class MockStateTracker:
        def update_state(self, *args, **kwargs):
            pass
            
    hooks = script.AntigravityHookRunner(MockStateTracker())
    
    res_file = script.execute_bridge_task(job_file, hooks, force=True)
    
    assert res_file.exists()
    res_data = json.loads(res_file.read_text())
    assert res_data["task_id"] == "t-2"
    assert res_data["payload"]["verdict"] == "PASS"
    assert res_data["payload"]["action_executed"] == "EXECUTE_INSTRUCTION"

