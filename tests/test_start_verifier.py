#!/usr/bin/env python3
"""Tests for scripts/start_verifier.py."""

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
import scripts.start_verifier as start_verifier


def test_is_verifier_running_true():
    mock_proc = MagicMock()
    mock_proc.info = {"cmdline": ["python", "-u", "-m", "scripts.courier_verifier"]}
    with patch("psutil.process_iter", return_value=[mock_proc]):
        assert start_verifier.is_verifier_running() is True


def test_is_verifier_running_false():
    mock_proc = MagicMock()
    mock_proc.info = {"cmdline": ["python", "other_script.py"]}
    with patch("psutil.process_iter", return_value=[mock_proc]):
        assert start_verifier.is_verifier_running() is False


def test_launch_verifier_refuses_when_running(tmp_path: Path):
    with patch("scripts.start_verifier.is_verifier_running", return_value=True):
        with patch("subprocess.Popen") as mock_popen:
            res = start_verifier.launch_verifier(repo_dir=tmp_path, force=False)
            assert res is False
            mock_popen.assert_not_called()


def test_launch_verifier_launches_when_not_running(tmp_path: Path):
    with patch("scripts.start_verifier.is_verifier_running", return_value=False):
        with patch("subprocess.Popen") as mock_popen:
            res = start_verifier.launch_verifier(repo_dir=tmp_path, force=False)
            assert res is True
            mock_popen.assert_called_once()
            assert (tmp_path / "scripts" / "verifier.log").exists()


def test_launch_verifier_force_launches(tmp_path: Path):
    with patch("scripts.start_verifier.is_verifier_running", return_value=True):
        with patch("subprocess.Popen") as mock_popen:
            res = start_verifier.launch_verifier(repo_dir=tmp_path, force=True)
            assert res is True
            mock_popen.assert_called_once()


def test_main_check_only(capsys):
    with patch("scripts.start_verifier.is_verifier_running", return_value=True):
        ret = start_verifier.main(["--check-only"])
        assert ret == 0
        captured = capsys.readouterr().out
        assert "VERIFIER_RUNNING: True" in captured

    with patch("scripts.start_verifier.is_verifier_running", return_value=False):
        ret = start_verifier.main(["--check-only"])
        assert ret == 1
        captured = capsys.readouterr().out
        assert "VERIFIER_RUNNING: False" in captured
