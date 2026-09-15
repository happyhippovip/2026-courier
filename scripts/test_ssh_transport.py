import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from remote_artifact_isolation import RemoteLifecycleLedger, RemoteLifecycleError
from remote_ssh_transport import SSHRemoteTransport

@patch("subprocess.run")
def test_start_workload_safe(mock_run, tmp_path):
    ledger_path = tmp_path / "ledger.sqlite3"
    transport = SSHRemoteTransport("test_target", ledger_path)
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "12345\n"
    mock_run.return_value = mock_result
    
    remote_pid = transport.start_workload("task1", 1, "gen1", "/safe/script.sh")
    assert remote_pid == "12345"
    
    # Verify ledger was updated
    import sqlite3
    with sqlite3.connect(ledger_path) as conn:
        row = conn.execute("SELECT remote_execution_id FROM remote_executions WHERE task_id='task1'").fetchone()
        assert row[0] == "12345"

@patch("subprocess.run")
def test_start_workload_unsafe_rejected(mock_run, tmp_path):
    ledger_path = tmp_path / "ledger.sqlite3"
    transport = SSHRemoteTransport("test_target", ledger_path)
    
    with pytest.raises(ValueError, match="Invalid remote script path"):
        transport.start_workload("task1", 1, "gen1", "rm -rf /; something")

@patch("subprocess.run")
def test_probe_workload(mock_run, tmp_path):
    ledger_path = tmp_path / "ledger.sqlite3"
    transport = SSHRemoteTransport("test_target", ledger_path)
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    assert transport.probe_workload("12345") == True
    
    mock_result.returncode = 1
    assert transport.probe_workload("99999") == False
