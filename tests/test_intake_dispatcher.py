import pytest
import json
import os
import sys
from pathlib import Path

def test_dispatch_intake_success(tmp_path, monkeypatch):
    import scripts.intake_dispatcher as dispatcher
    
    state_file = tmp_path / "central_state.json"
    monkeypatch.setenv("COURIER_STATE_FILE", str(state_file))
    
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test-owner",
        "target_repo": "test-repo",
        "target_sha": "abc1234",
        "customer_reference": "cust-01"
    }))
    
    # Mock subprocess.run
    class MockProcess:
        def __init__(self, stdout=""):
            self.stdout = stdout
            
    def mock_run(cmd, *args, **kwargs):
        if "gh run list" in " ".join(cmd):
            return MockProcess(stdout="123456\n")
        return MockProcess()
        
    monkeypatch.setattr(dispatcher.subprocess, "run", mock_run)
    
    # Mock time.sleep to avoid waiting
    import time
    monkeypatch.setattr(time, "sleep", lambda x: None)
    
    dispatcher.dispatch_intake(str(intake_file))
    
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert "tasks" in state
    
    # Find the task
    tasks = state["tasks"]
    assert len(tasks) == 1
    task_id = list(tasks.keys())[0]
    
    task = tasks[task_id]
    assert task["customer_reference"] == "cust-01"
    assert task["worker_id"] == "github-actions-revenue-v1"
    assert task["execution_ref"] == "123456"

