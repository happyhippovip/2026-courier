"""Timeout kill for the Windows daemon PowerShell child.

 communicate(timeout=...) never kills the child: on TimeoutExpired the
 daemon must kill+reap the PowerShell process and return FAILED (never
 leave it running unmanaged). PHYSICAL_WINDOWS_REQUIRED for a live
 PowerShell run; the kill contract below is platform-independent.
"""
import importlib.util
import subprocess
from pathlib import Path
from unittest import mock

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"


def load_daemon():
    spec = importlib.util.spec_from_file_location("windows_daemon_timeout_under_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon


def test_run_task_timeout_kills_child_and_fails():
    daemon = load_daemon()
    mock_process = mock.Mock()
    mock_process.pid = 4321
    mock_process.communicate.side_effect = [
        subprocess.TimeoutExpired("powershell", 600),
        ("", ""),
    ]
    task = {"task_id": "w1", "goal_id": "g1", "instruction": "Start-Sleep 9999"}
    config = {"WORKER_ID": "WINDOWS-01"}

    with mock.patch.object(daemon.subprocess, "Popen", return_value=mock_process):
        res = daemon.run_task(task, config)

    mock_process.kill.assert_called_once_with()
    assert mock_process.communicate.call_count == 2
    assert res["status"] == "FAILED"
    assert "TIMEOUT" in res["stderr"]
    assert res["run_id"] == "4321"
