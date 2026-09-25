import pytest
import os
import sys
import subprocess
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import safe_repair

def test_run_health_check_missing(capsys):
    with mock.patch("os.path.exists", return_value=False):
        safe_repair.run_health_check()
    captured = capsys.readouterr()
    assert "Health check script not found" in captured.out

def test_run_health_check_success(capsys):
    with mock.patch("os.path.exists", return_value=True):
        with mock.patch("subprocess.run") as mock_run:
            safe_repair.run_health_check()
            mock_run.assert_called_once()
    captured = capsys.readouterr()
    assert "Health check passed" in captured.out

def test_run_health_check_failure(capsys):
    with mock.patch("os.path.exists", return_value=True):
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
            safe_repair.run_health_check()
    captured = capsys.readouterr()
    assert "Health check failed" in captured.out

def test_safe_repair(capsys):
    with mock.patch("scripts.safe_repair.repair_service") as mock_repair:
        with mock.patch("scripts.safe_repair.run_health_check") as mock_hc:
            with mock.patch("scripts.safe_repair.restart_courier") as mock_restart:
                safe_repair.safe_repair()
                mock_repair.assert_called_once()
                mock_hc.assert_called_once()
                mock_restart.assert_called_once()
    
    captured = capsys.readouterr()
    assert "Initiating Safe Runtime Repair" in captured.out
    assert "Canonical state and credentials preserved" in captured.out

