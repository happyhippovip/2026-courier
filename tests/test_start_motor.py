#!/usr/bin/env python3
"""Tests for scripts/start_motor.py."""

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
import scripts.start_motor as start_motor


def test_is_port_in_use():
    with patch("socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        mock_sock.connect_ex.return_value = 0
        assert start_motor.is_port_in_use(8080) is True

        mock_sock.connect_ex.return_value = 10061
        assert start_motor.is_port_in_use(8080) is False


def test_get_python_exe(monkeypatch):
    monkeypatch.setenv("COURIER_PYTHON", "C:\\custom\\python.exe")
    assert start_motor.get_python_exe() == "C:\\custom\\python.exe"

    monkeypatch.delenv("COURIER_PYTHON", raising=False)
    assert Path(start_motor.get_python_exe()).name.startswith("python")


def test_launch(tmp_path: Path):
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        proc = start_motor.launch("test.module", "test.log", repo_dir=tmp_path)
        assert proc is not None
        mock_popen.assert_called_once()
        assert (tmp_path / "logs" / "test.log").exists()


def test_start_motor_refuses_when_port_in_use(tmp_path: Path):
    with patch("scripts.start_motor.is_port_in_use", side_effect=lambda p: p == 8080):
        with patch("scripts.start_motor.launch") as mock_launch:
            res = start_motor.start_motor(repo_dir=tmp_path, force=False)
            assert res is False
            mock_launch.assert_not_called()


def test_start_motor_force_launches(tmp_path: Path):
    with patch("scripts.start_motor.is_port_in_use", return_value=True):
        with patch("scripts.start_motor.launch") as mock_launch:
            res = start_motor.start_motor(repo_dir=tmp_path, force=True)
            assert res is True
            assert mock_launch.call_count == 3


def test_start_motor_launches_when_free(tmp_path: Path):
    with patch("scripts.start_motor.is_port_in_use", return_value=False):
        with patch("scripts.start_motor.launch") as mock_launch:
            res = start_motor.start_motor(repo_dir=tmp_path, force=False)
            assert res is True
            assert mock_launch.call_count == 3


def test_main_check_ports(capsys):
    with patch("scripts.start_motor.is_port_in_use", side_effect=lambda p: p == 8080):
        ret = start_motor.main(["--check-ports"])
        assert ret == 0
        captured = capsys.readouterr().out
        assert "PORT_8080_IN_USE: True" in captured
        assert "PORT_8081_IN_USE: False" in captured
