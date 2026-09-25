import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest import mock
import pytest

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import mac_worker_adapter

def test_mac_worker_adapter_success(tmp_path):
    # Mocking paths to use tmp_path
    base_dir = tmp_path / "scripts" / "mac_worker"
    inbox = base_dir / "inbox"
    outbox = base_dir / "outbox"
    results_inc = tmp_path / "results" / "incoming"
    
    inbox.mkdir(parents=True)
    outbox.mkdir(parents=True)
    results_inc.mkdir(parents=True)
    
    task_file = tmp_path / "test_task.json"
    task_data = {"task_id": "test-123", "goal_id": "goal-1"}
    with open(task_file, "w") as f:
        json.dump(task_data, f)
        
    def mock_sleep(secs):
        # Simulate worker completing the task
        outbox_file = outbox / "test-123_result.json"
        with open(outbox_file, "w") as f:
            json.dump({"status": "PASS", "task_id": "test-123"}, f)
            
    with mock.patch("time.sleep", side_effect=mock_sleep):
        with mock.patch("scripts.mac_worker_adapter.Path", side_effect=lambda p: tmp_path / p if isinstance(p, str) else p):
            with mock.patch("os.makedirs"):
                with mock.patch("shutil.copy", side_effect=shutil.copy):
                    with mock.patch("os.replace", side_effect=os.replace):
                        with mock.patch("os.remove", side_effect=os.remove):
                            mac_worker_adapter.run(str(task_file))
                            
    # Verify result moved
    final_res = tmp_path / "results" / "incoming" / "test-123_result.json"
    assert final_res.exists()
    with open(final_res, "r") as f:
        data = json.load(f)
        assert data["status"] == "PASS"

def test_mac_worker_adapter_timeout(tmp_path):
    # Mocking paths to use tmp_path
    base_dir = tmp_path / "scripts" / "mac_worker"
    inbox = base_dir / "inbox"
    outbox = base_dir / "outbox"
    results_inc = tmp_path / "results" / "incoming"
    
    inbox.mkdir(parents=True)
    outbox.mkdir(parents=True)
    results_inc.mkdir(parents=True)
    
    task_file = tmp_path / "test_task_timeout.json"
    task_data = {"task_id": "test-timeout", "goal_id": "goal-1"}
    with open(task_file, "w") as f:
        json.dump(task_data, f)
        
    with mock.patch("time.sleep"):
        with mock.patch("time.time", side_effect=[0, 301]): # Force timeout
            with mock.patch("scripts.mac_worker_adapter.Path", side_effect=lambda p: tmp_path / p if isinstance(p, str) else p):
                with mock.patch("os.makedirs"):
                    mac_worker_adapter.run(str(task_file))
                    
    # Verify timeout result generated
    final_res = tmp_path / "results" / "incoming" / "test-timeout_result.json"
    assert final_res.exists()
    with open(final_res, "r") as f:
        data = json.load(f)
        assert data["status"] == "FAILED"
        assert data["reason"] == "TIMEOUT"

