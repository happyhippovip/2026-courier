from __future__ import annotations

import io
import json
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.launch_visual_studio as lvs


def test_port_is_listening():
    # Start a temporary listener
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert lvs.port_is_listening(port) is True
    finally:
        srv.close()

    assert lvs.port_is_listening(port) is False


def test_launch_server_already_running():
    with patch.object(lvs, "port_is_listening", return_value=True):
        res = lvs.launch_server(8088, quiet=True)
        assert res["status"] == "ALREADY_RUNNING"
        assert res["exit_code"] == 0
        assert res["port"] == 8088


def test_launch_server_successful_start(tmp_path: Path):
    mock_proc = MagicMock()
    mock_proc.pid = 4321
    mock_proc.poll.return_value = None

    port_states = [False, False, True]

    def mock_listening(_port: int) -> bool:
        if port_states:
            return port_states.pop(0)
        return True

    with patch.object(lvs, "port_is_listening", side_effect=mock_listening):
        with patch("subprocess.Popen", return_value=mock_proc):
            res = lvs.launch_server(8088, repo_dir=tmp_path, timeout=2.0, quiet=True)
            assert res["status"] == "STARTED"
            assert res["pid"] == 4321
            assert res["exit_code"] == 0


def test_launch_server_process_fails(tmp_path: Path):
    mock_proc = MagicMock()
    mock_proc.pid = 4322
    mock_proc.poll.return_value = 1
    mock_proc.returncode = 1

    with patch.object(lvs, "port_is_listening", return_value=False):
        with patch("subprocess.Popen", return_value=mock_proc):
            res = lvs.launch_server(8088, repo_dir=tmp_path, timeout=2.0, quiet=True)
            assert res["status"] == "START_FAILED"
            assert res["exit_code"] == 1


def test_launch_server_timeout(tmp_path: Path):
    mock_proc = MagicMock()
    mock_proc.pid = 4323
    mock_proc.poll.return_value = None

    with patch.object(lvs, "port_is_listening", return_value=False):
        with patch("subprocess.Popen", return_value=mock_proc):
            res = lvs.launch_server(8088, repo_dir=tmp_path, timeout=0.2, quiet=True)
            assert res["status"] == "TIMEOUT"
            assert res["exit_code"] == 1


def test_main_cli_status(capsys):
    with patch.object(lvs, "port_is_listening", return_value=True):
        code = lvs.main(["--status", "--port", "8088", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["listening"] is True
        assert data["port"] == 8088


def test_main_cli_invalid_port():
    with pytest.raises(SystemExit):
        lvs.main(["--port", "999999"])
