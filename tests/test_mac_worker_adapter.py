import pytest
from pathlib import Path
import json
import time

def test_mac_worker_adapter_success(tmp_path, monkeypatch):
    import scripts.mac_worker_adapter as script
    
    # Mock paths
    monkeypatch.chdir(tmp_path)
    
    task_file = tmp_path / "task-1.json"
    task_file.write_text(json.dumps({"task_id": "task-1", "goal_id": "g-1"}))
    
    # We need to mock time.sleep so we can create the file "concurrently"
    original_sleep = time.sleep
    def mock_sleep(s):
        outbox = Path("scripts/mac_worker/outbox")
        outbox.mkdir(parents=True, exist_ok=True)
        res_file = outbox / "task-1_result.json"
        res_file.write_text(json.dumps({"status": "SUCCESS"}))
        original_sleep(0.01)
        
    monkeypatch.setattr(time, "sleep", mock_sleep)
    
    script.run(str(task_file))
    
    incoming = Path("results/incoming/task-1_result.json")
    assert incoming.exists()
    assert json.loads(incoming.read_text())["status"] == "SUCCESS"

def test_mac_worker_adapter_timeout(tmp_path, monkeypatch):
    import scripts.mac_worker_adapter as script
    
    monkeypatch.chdir(tmp_path)
    
    task_file = tmp_path / "task-1.json"
    task_file.write_text(json.dumps({"task_id": "task-1", "goal_id": "g-1"}))
    
    def mock_time():
        if not hasattr(mock_time, "start"):
            mock_time.start = 1000
            return 1000
        return 1301 # Fast-forward 301 seconds
        
    monkeypatch.setattr(time, "time", mock_time)
    monkeypatch.setattr(time, "sleep", lambda x: None)
    
    (tmp_path / "results/incoming").mkdir(parents=True, exist_ok=True)
    
    script.run(str(task_file))
    
    incoming = Path("results/incoming/task-1_result.json")
    assert incoming.exists()
    assert json.loads(incoming.read_text())["status"] == "FAILED"
    assert json.loads(incoming.read_text())["reason"] == "TIMEOUT"

