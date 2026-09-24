import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.courierctl import courierctl


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("COURIER_SERVER", "http://127.0.0.1:8080")
    monkeypatch.setenv("COURIER_API_KEY", "test-api-key")


def test_get_config_missing_api_key(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        courierctl.get_config()
    assert exc_info.value.code == 1


def test_get_config_success():
    server, api_key = courierctl.get_config()
    assert server == "http://127.0.0.1:8080"
    assert api_key == "test-api-key"


def test_make_request_connection_failure():
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.make_request("GET", "/health")
        assert exc_info.value.code == 1


def test_cmd_submit_success(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"goal_id": "goal-123", "status": "PENDING"}

    args = MagicMock()
    args.goal = "Build Windows feature"
    args.json = False

    with patch("requests.post", return_value=mock_res):
        courierctl.cmd_submit(args)

    captured = capsys.readouterr()
    assert "Goal submitted successfully. ID: goal-123" in captured.out


def test_cmd_submit_failure_exits_nonzero(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 500
    mock_res.json.return_value = {"error": "Server error"}

    args = MagicMock()
    args.goal = "Build Windows feature"
    args.json = False

    with patch("requests.post", return_value=mock_res):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.cmd_submit(args)
        assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "ERROR: Failed to submit goal (HTTP 500)" in captured.err


def test_cmd_status_success(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"status": "HEALTHY", "active_workers": 2}

    args = MagicMock()
    args.json = False

    with patch("requests.get", return_value=mock_res):
        courierctl.cmd_status(args)

    captured = capsys.readouterr()
    assert "COURIER SYSTEM STATUS" in captured.out
    assert "STATUS: HEALTHY" in captured.out


def test_cmd_status_failure_exits_nonzero(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 503
    mock_res.json.return_value = {"error": "Unavailable"}

    args = MagicMock()
    args.json = False

    with patch("requests.get", return_value=mock_res):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.cmd_status(args)
        assert exc_info.value.code != 0


def test_cmd_health_success(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"healthy": True}

    args = MagicMock()
    args.json = False

    with patch("requests.get", return_value=mock_res):
        courierctl.cmd_health(args)

    captured = capsys.readouterr()
    assert "Server is HEALTHY." in captured.out


def test_cmd_health_failure_exits_nonzero(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 503
    mock_res.json.return_value = {"healthy": False}

    args = MagicMock()
    args.json = False

    with patch("requests.get", return_value=mock_res):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.cmd_health(args)
        assert exc_info.value.code != 0


def test_cmd_goal_success(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "goal": {
            "status": "IN_PROGRESS",
            "goal_text": "Sample goal",
            "workflow_plan": [{"task_id": "t1", "target_agent": "windows", "status": "RUNNING", "worker_id": "w1"}],
        },
        "tasks": [{"task_id": "t1", "worker_id": "w1", "status": "RUNNING", "attempts": 1}],
    }

    args = MagicMock()
    args.id = "goal-abc"
    args.json = False

    with patch("requests.get", return_value=mock_res):
        courierctl.cmd_goal(args)

    captured = capsys.readouterr()
    assert "GOAL goal-abc" in captured.out
    assert "Status: IN_PROGRESS" in captured.out
    assert "Task: t1" in captured.out


def test_cmd_goal_failure_exits_nonzero(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 404
    mock_res.json.return_value = {"error": "Goal not found"}

    args = MagicMock()
    args.id = "goal-missing"
    args.json = False

    with patch("requests.get", return_value=mock_res):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.cmd_goal(args)
        assert exc_info.value.code != 0


def test_cmd_workers_success(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"workers": ["worker-1", "worker-2"]}

    args = MagicMock()
    args.json = True

    with patch("requests.get", return_value=mock_res):
        courierctl.cmd_workers(args)

    captured = capsys.readouterr()
    assert "worker-1" in captured.out


def test_cmd_workers_404_exits_nonzero(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 404
    mock_res.headers = {}

    args = MagicMock()
    args.json = False

    with patch("requests.get", return_value=mock_res):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.cmd_workers(args)
        assert exc_info.value.code != 0


def test_cmd_wall_404_exits_nonzero(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 404
    mock_res.headers = {}

    args = MagicMock()
    args.json = False

    with patch("requests.get", return_value=mock_res):
        with pytest.raises(SystemExit) as exc_info:
            courierctl.cmd_wall(args)
        assert exc_info.value.code != 0


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_courierctl_cmd_windows():
    cmd_path = REPO_ROOT / "tools" / "courierctl" / "courierctl.cmd"
    assert cmd_path.exists()

    proc = subprocess.run(
        ["cmd.exe", "/c", str(cmd_path), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "Courier CLI Operator Client" in proc.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_courierctl_install_ps1(tmp_path):
    ps1_path = REPO_ROOT / "tools" / "courierctl" / "install.ps1"
    assert ps1_path.exists()

    target_dir = tmp_path / "bin"

    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1_path),
            "-InstallDir",
            str(target_dir),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0
    assert (target_dir / "courierctl.cmd").exists()
    assert (target_dir / "courierctl.py").exists()

    # Verify installed courierctl.cmd works
    test_run = subprocess.run(
        ["cmd.exe", "/c", str(target_dir / "courierctl.cmd"), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert test_run.returncode == 0
    assert "Courier CLI Operator Client" in test_run.stdout

