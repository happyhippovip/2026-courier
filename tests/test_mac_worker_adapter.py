import os
import json
import time
from unittest import mock
import pytest
from pathlib import Path

from scripts import mac_worker_adapter

def test_run_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac1", "goal_id": "g1"}, f)
        
    def mock_sleep(seconds):
        outbox_file = Path("scripts/mac_worker/outbox/mac1_result.json")
        outbox_file.parent.mkdir(parents=True, exist_ok=True)
        with open(outbox_file, "w") as f:
            json.dump({"status": "SUCCESS"}, f)
            
    with mock.patch("time.sleep", side_effect=mock_sleep):
        mac_worker_adapter.run(str(task_file))
        
    incoming = Path("results/incoming/mac1_result.json")
    assert incoming.exists()
    
    with open(incoming, "r") as f:
        res = json.load(f)
        assert res["status"] == "SUCCESS"
        
    outbox_file = Path("scripts/mac_worker/outbox/mac1_result.json")
    assert not outbox_file.exists()


def test_run_timeout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("results/incoming").mkdir(parents=True, exist_ok=True)
    
    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac2", "goal_id": "g2"}, f)
        
    start_time = 0
    def mock_time():
        nonlocal start_time
        res = start_time
        start_time += 400
        return res
        
    with mock.patch("time.time", side_effect=mock_time):
        mac_worker_adapter.run(str(task_file))
        
    incoming = Path("results/incoming/mac2_result.json")
    assert incoming.exists()
    
    with open(incoming, "r") as f:
        res = json.load(f)
        assert res["status"] == "FAILED"
        assert res["reason"] == "TIMEOUT"


def test_main(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac3", "goal_id": "g3"}, f)
        
    def mock_sleep(seconds):
        outbox_file = Path("scripts/mac_worker/outbox/mac3_result.json")
        outbox_file.parent.mkdir(parents=True, exist_ok=True)
        with open(outbox_file, "w") as f:
            json.dump({"status": "SUCCESS"}, f)
            
    import sys
    import runpy
    
    with mock.patch("time.sleep", side_effect=mock_sleep):
        sys.argv = ["mac_worker_adapter.py", str(task_file)]
        runpy.run_path(str(Path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "mac_worker_adapter.py"))), run_name="__main__")
        
    incoming = Path("results/incoming/mac3_result.json")
    assert incoming.exists()
