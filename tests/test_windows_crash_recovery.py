import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import windows_crash_recovery

def test_recover_worker_no_state(tmp_path, capsys):
    state_file = tmp_path / "worker_state.json"
    
    with mock.patch("scripts.windows_crash_recovery.os.path.exists", return_value=False):
        windows_crash_recovery.recover_worker(str(state_file))
        
    captured = capsys.readouterr()
    assert "No worker state found" in captured.out

def test_recover_worker_idle(tmp_path, capsys):
    state_file = tmp_path / "worker_state.json"
    state_file.write_text(json.dumps({"current_task": None}))
    
    with mock.patch("scripts.windows_crash_recovery.os.path.exists", return_value=True):
        windows_crash_recovery.recover_worker(str(state_file))
        
    captured = capsys.readouterr()
    assert "Worker crashed while idle" in captured.out

def test_recover_worker_phases(tmp_path, capsys):
    phases = ['PRE_EFFECT', 'ARTIFACT_CREATED', 'POST_EXTERNAL_EFFECT', 'POST_RESULT', 'UNKNOWN']
    
    for phase in phases:
        state_file = tmp_path / f"worker_state_{phase}.json"
        state_file.write_text(json.dumps({
            "current_task": {
                "task_id": "T1",
                "execution_ref": "exec_1",
                "phase": phase
            },
            "owned_pids": [123]
        }))
        
        with mock.patch("scripts.windows_crash_recovery.os.path.exists", return_value=True):
            windows_crash_recovery.recover_worker(str(state_file))
            
        captured = capsys.readouterr()
        
        if phase == 'PRE_EFFECT':
            assert "Safe to blindly re-execute" in captured.out
        elif phase == 'ARTIFACT_CREATED':
            assert "Artifacts persist" in captured.out
        elif phase == 'POST_EXTERNAL_EFFECT':
            assert "AMBIGUOUS_EFFECT_FAIL_CLOSED" in captured.out
        elif phase == 'POST_RESULT':
            assert "Server has result" in captured.out
        else:
            assert "Unknown phase" in captured.out
            
        assert "Cleaning up orphaned processes from crash: [123]" in captured.out
        
        # State should be cleared
        wstate = json.loads(state_file.read_text())
        assert wstate["current_task"] is None
        assert wstate["owned_pids"] == []

