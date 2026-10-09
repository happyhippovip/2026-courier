import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import courier_github_dispatcher

@pytest.fixture
def mock_env(tmp_path):
    original_dir = courier_github_dispatcher.DISPATCH_DIR
    courier_github_dispatcher.DISPATCH_DIR = tmp_path / "dispatch"
    yield
    courier_github_dispatcher.DISPATCH_DIR = original_dir

def test_persist_packet_valid(mock_env):
    task = {
        "goal_id": "G1",
        "task_id": "T1",
        "attempt_id": "A1",
        "dispatch_id": "dispatch-1234",
        "worker_id": "W1",
        "payload": {}
    }
    path = courier_github_dispatcher.persist_packet(task)
    assert path is not None
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == task

def test_persist_packet_missing_fields(mock_env):
    task = {
        "goal_id": "G1",
        "task_id": "T1",
        "dispatch_id": "dispatch-1234",
        "worker_id": "W1"
        # Missing attempt_id
    }
    path = courier_github_dispatcher.persist_packet(task)
    assert path is None

def test_persist_packet_unsafe_dispatch_id(mock_env):
    task = {
        "goal_id": "G1",
        "task_id": "T1",
        "attempt_id": "A1",
        "dispatch_id": "dispatch-1234/bad",
        "worker_id": "W1",
        "payload": {}
    }
    path = courier_github_dispatcher.persist_packet(task)
    assert path is None

@patch("scripts.courier_github_dispatcher.spawn_adapter")
def test_resume_pending(mock_spawn, mock_env):
    disp_dir = courier_github_dispatcher.DISPATCH_DIR
    disp_dir.mkdir(parents=True)
    
    # 1. Valid pending dispatch
    d1 = disp_dir / "dispatch-1.json"
    d1.write_text('{"dispatch_id": "dispatch-1"}')
    
    # 2. Posted dispatch (should not be resumed)
    d2 = disp_dir / "dispatch-2.json"
    d2.write_text('{"dispatch_id": "dispatch-2"}')
    s2 = disp_dir / "dispatch-2.github-worker-state.json"
    s2.write_text('{"status": "POSTED"}')
    
    # 3. Failed/working dispatch (should be resumed because it's not POSTED)
    d3 = disp_dir / "dispatch-3.json"
    d3.write_text('{"dispatch_id": "dispatch-3"}')
    s3 = disp_dir / "dispatch-3.github-worker-state.json"
    s3.write_text('{"status": "WORKING"}')
    
    resumed = courier_github_dispatcher.resume_pending()
    assert resumed == 2
    assert mock_spawn.call_count == 2
    
    # Check that d1 and d3 were passed to spawn_adapter
    args = [call.args[0] for call in mock_spawn.call_args_list]
    assert d1 in args
    assert d3 in args
    assert d2 not in args

@patch("scripts.courier_github_dispatcher.spawn_adapter")
def test_handle_claimed_task(mock_spawn, mock_env):
    task = {
        "goal_id": "G1",
        "task_id": "T1",
        "attempt_id": "A1",
        "dispatch_id": "dispatch-5678",
        "worker_id": "W1",
        "payload": {}
    }
    
    assert courier_github_dispatcher.handle_claimed_task(task) is True
    mock_spawn.assert_called_once()
    
    path = mock_spawn.call_args[0][0]
    assert path.name == "dispatch-5678.json"
