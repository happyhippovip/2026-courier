import pytest
import os
import json
import signal
import subprocess
from unittest import mock
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import agent_session_manager

@pytest.fixture
def temp_registry(tmp_path):
    orig = agent_session_manager.REGISTRY_FILE
    agent_session_manager.REGISTRY_FILE = tmp_path / "test_monitors.json"
    yield agent_session_manager.REGISTRY_FILE
    agent_session_manager.REGISTRY_FILE = orig

def test_load_save(temp_registry):
    # Load empty
    assert agent_session_manager._load() == {}
    
    # Save and load
    data = {"test_owner": [{"pid": 123}]}
    agent_session_manager._save(data)
    assert agent_session_manager._load() == data

def test_get_process_info_success():
    with mock.patch("subprocess.check_output", return_value=b"start time info args"):
        assert agent_session_manager.get_process_info(1234) == "start time info args"

def test_get_process_info_fail():
    with mock.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "ps")):
        assert agent_session_manager.get_process_info(1234) is None

def test_register_task(temp_registry):
    with mock.patch("scripts.agent_session_manager.get_process_info", return_value="info"):
        assert agent_session_manager.register_task(111, "owner_a", "watching") is True
        
    data = agent_session_manager._load()
    assert "owner_a" in data
    assert data["owner_a"][0]["pid"] == 111
    assert data["owner_a"][0]["proc_info"] == "info"

def test_register_task_dead_process(temp_registry):
    with mock.patch("scripts.agent_session_manager.get_process_info", return_value=None):
        assert agent_session_manager.register_task(999, "owner_a", "watching") is False
        
    assert agent_session_manager._load() == {}

def test_kill_pid_success():
    with mock.patch("os.kill") as mock_kill:
        # First call to kill 0 raises OSError, meaning process is dead
        mock_kill.side_effect = [None, OSError("No process")]
        assert agent_session_manager.kill_pid(123) is True
        mock_kill.assert_has_calls([mock.call(123, signal.SIGTERM), mock.call(123, 0)])

def test_cleanup_session(temp_registry):
    data = {
        "owner_b": [
            {"pid": 111, "proc_info": "info_match"},
            {"pid": 222, "proc_info": "info_mismatch"}
        ]
    }
    agent_session_manager._save(data)
    
    def mock_get_info(pid):
        if pid == 111: return "info_match"
        if pid == 222: return "new_info_pid_reused"
        
    with mock.patch("scripts.agent_session_manager.get_process_info", side_effect=mock_get_info):
        with mock.patch("scripts.agent_session_manager.kill_pid", return_value=True) as mock_kill:
            killed = agent_session_manager.cleanup_session("owner_b")
            
    assert killed == 1
    mock_kill.assert_called_once_with(111)
    
    # owner_b should be removed from registry
    assert "owner_b" not in agent_session_manager._load()

def test_audit_orphans(temp_registry):
    data = {
        "owner_c": [
            {"pid": 333, "proc_info": "alive_info"},
            {"pid": 444, "proc_info": "dead_info"}
        ],
        "owner_empty": [
            {"pid": 555, "proc_info": "dead_info"}
        ]
    }
    agent_session_manager._save(data)
    
    def mock_get_info(pid):
        if pid == 333: return "alive_info"
        return None
        
    with mock.patch("scripts.agent_session_manager.get_process_info", side_effect=mock_get_info):
        agent_session_manager.audit_orphans()
        
    loaded = agent_session_manager._load()
    assert "owner_empty" not in loaded
    assert len(loaded["owner_c"]) == 1
    assert loaded["owner_c"][0]["pid"] == 333

