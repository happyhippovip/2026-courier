import os
import json
import time
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import orphan_task_reaper

# Keep original built-in open
original_open = open

def test_check_task_health_healthy(tmp_path):
    state_file = tmp_path / "central_state.json"
    worker_state_file = tmp_path / "worker_state.json"
    
    state_file.write_text(json.dumps({
        "goals": {
            "g1": {
                "workflow_plan": [
                    {"task_id": "T1", "status": "RUNNING"}
                ]
            }
        }
    }))
    
    worker_state_file.write_text(json.dumps({
        "current_task": {"task_id": "T1"},
        "owned_pids": [1234],
        "last_heartbeat": time.time()
    }))
    
    with mock.patch("scripts.orphan_task_reaper.os.path.exists", return_value=True):
        def mock_open(path, mode='r', **kwargs):
            path_str = str(path)
            if 'central_state.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(state_file), mode, **kwargs)
            elif 'worker_state.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(worker_state_file), mode, **kwargs)
            return original_open(path_str, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            with mock.patch("scripts.orphan_task_reaper.psutil.Process") as mock_process:
                orphan_task_reaper.check_task_health()
                
    # Process should NOT be terminated
    mock_process.assert_not_called()
    
    # State should be untouched
    with original_open(worker_state_file, 'r') as f:
        wstate = json.load(f)
        assert wstate["current_task"] is not None

def test_check_task_health_orphaned_stale_heartbeat(tmp_path):
    state_file = tmp_path / "central_state.json"
    worker_state_file = tmp_path / "worker_state.json"
    
    state_file.write_text(json.dumps({
        "goals": {
            "g1": {
                "workflow_plan": [
                    {"task_id": "T2", "status": "RUNNING"}
                ]
            }
        }
    }))
    
    worker_state_file.write_text(json.dumps({
        "current_task": {"task_id": "T2"},
        "owned_pids": [5678],
        "last_heartbeat": time.time() - 400  # Stale (> 300)
    }))
    
    with mock.patch("scripts.orphan_task_reaper.os.path.exists", return_value=True):
        def mock_open(path, mode='r', **kwargs):
            path_str = str(path)
            if 'central_state.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(state_file), mode, **kwargs)
            elif 'worker_state.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(worker_state_file), mode, **kwargs)
            return original_open(path_str, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            mock_p = mock.Mock()
            mock_p.children.return_value = []
            
            with mock.patch("scripts.orphan_task_reaper.psutil.Process", return_value=mock_p):
                orphan_task_reaper.check_task_health()
                
            mock_p.terminate.assert_called_once()
            
    with original_open(worker_state_file, 'r') as f:
        wstate = json.load(f)
        assert wstate["current_task"] is None
        assert wstate["owned_pids"] == []

