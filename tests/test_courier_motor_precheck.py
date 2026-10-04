import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from scripts.courier_motor_precheck import has_dispatchable_work, main

def test_has_dispatchable_work_worker_busy():
    state = {
        "workers": {
            "GITHUB-DISPATCHER": {
                "current_task": "task_1"
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_not_active():
    state = {
        "goals": {
            "g1": {
                "status": "COMPLETED",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "github"}]
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_no_plan():
    state = {
        "goals": {
            "g1": {
                "status": "ACTIVE"
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_out_of_bounds():
    state = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "COMPLETED", "target_agent": "github"}],
                "current_step_index": 1
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_wrong_agent():
    state = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "linux"}],
                "current_step_index": 0
            }
        }
    }
    assert not has_dispatchable_work(state)

def test_has_dispatchable_work_success():
    state = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "github-actions"}],
                "current_step_index": 0
            }
        }
    }
    assert has_dispatchable_work(state)

def test_has_dispatchable_work_empty():
    assert not has_dispatchable_work({})

def test_main_file_not_exists(capsys):
    with patch("os.path.exists", return_value=False), \
         patch("scripts.courier_motor_precheck.STATE_FILE", "dummy.json"):
        assert main() == 0
        out = capsys.readouterr().out
        assert "[Motor precheck] dummy.json: idle" in out

def test_main_file_exists_with_work(capsys, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "QUEUED", "target_agent": "github"}],
                "current_step_index": 0
            }
        }
    }))
    
    github_out = tmp_path / "github.out"
    
    with patch("scripts.courier_motor_precheck.STATE_FILE", str(state_file)), \
         patch.dict("os.environ", {"GITHUB_OUTPUT": str(github_out)}):
        assert main() == 0
        
    out = capsys.readouterr().out
    assert "pending GitHub work" in out
    
    assert "has_work=true" in github_out.read_text()

def test_main_file_exists_no_work(capsys, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({}))
    
    github_out = tmp_path / "github.out"
    
    with patch("scripts.courier_motor_precheck.STATE_FILE", str(state_file)), \
         patch.dict("os.environ", {"GITHUB_OUTPUT": str(github_out)}):
        assert main() == 0
        
    out = capsys.readouterr().out
    assert "idle" in out
    
    assert "has_work=false" in github_out.read_text()
