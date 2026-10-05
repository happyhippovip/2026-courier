import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.courier_doctor import check_ledger, check_stuck_tasks

def test_check_ledger_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    passed, msg = check_ledger()
    assert not passed
    assert "Missing" in msg

def test_check_ledger_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "central_state.json"
    
    with open(state_file, "w") as f:
        json.dump({"goals": {"a": 1}, "workers": {"w1": 1}}, f)
        
    passed, msg = check_ledger()
    assert passed
    assert "Goals: 1, Known Workers: 1" in msg

def test_check_ledger_corrupt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "central_state.json"
    
    with open(state_file, "w") as f:
        f.write("{corrupt json")
        
    passed, msg = check_ledger()
    assert not passed
    assert "Corrupt JSON" in msg

@patch("time.time", return_value=1000)
def test_check_stuck_tasks_stuck(mock_time, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "central_state.json"
    
    # Task dispatched to a worker last seen at 500 (500 seconds ago, > 300)
    data = {
        "tasks": {"t1": {"status": "DISPATCHED", "worker_id": "w1"}},
        "workers": {"w1": {"last_seen": 500}}
    }
    with open(state_file, "w") as f:
        json.dump(data, f)
        
    passed, msg = check_stuck_tasks()
    assert not passed
    assert "Found 1 stuck tasks" in msg

@patch("time.time", return_value=1000)
def test_check_stuck_tasks_healthy(mock_time, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "central_state.json"
    
    # Task dispatched to a worker last seen at 800 (200 seconds ago, < 300)
    data = {
        "tasks": {"t1": {"status": "DISPATCHED", "worker_id": "w1"}},
        "workers": {"w1": {"last_seen": 800}}
    }
    with open(state_file, "w") as f:
        json.dump(data, f)
        
    passed, msg = check_stuck_tasks()
    assert passed
    assert "active workers" in msg
