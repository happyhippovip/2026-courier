import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import start_motor


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_start_motor_bat_dry_run_resolves_functional_python():
    bat_path = REPO_ROOT / "scripts" / "start_motor.bat"
    assert bat_path.exists()

    env = os.environ.copy()
    env["COURIER_MOTOR_DRY_RUN"] = "1"

    proc = subprocess.run(
        ["cmd.exe", "/c", str(bat_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "PYTHON_EXE=" in proc.stdout

    resolved_python = None
    for line in proc.stdout.splitlines():
        if line.startswith("PYTHON_EXE="):
            resolved_python = line.split("=", 1)[1].strip()

    assert resolved_python is not None
    # Verify the resolved python can import the required modules for start_motor
    check_proc = subprocess.run(
        [resolved_python, "-c", "import flask, requests, psutil; print('OK')"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert check_proc.returncode == 0
    assert "OK" in check_proc.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_start_verifier_bat_dry_run_resolves_functional_python():
    bat_path = REPO_ROOT / "scripts" / "start_verifier.bat"
    assert bat_path.exists()

    env = os.environ.copy()
    env["COURIER_VERIFIER_DRY_RUN"] = "1"

    proc = subprocess.run(
        ["cmd.exe", "/c", str(bat_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "PYTHON_EXE=" in proc.stdout

    resolved_python = None
    for line in proc.stdout.splitlines():
        if line.startswith("PYTHON_EXE="):
            resolved_python = line.split("=", 1)[1].strip()

    assert resolved_python is not None
    # Verify the resolved python can import psutil
    check_proc = subprocess.run(
        [resolved_python, "-c", "import psutil; print('OK')"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert check_proc.returncode == 0
    assert "OK" in check_proc.stdout


def test_start_motor_get_python_exe(monkeypatch):
    monkeypatch.setenv("COURIER_PYTHON", r"C:\fake\python.exe")
    assert start_motor.get_python_exe() == r"C:\fake\python.exe"

    monkeypatch.delenv("COURIER_PYTHON", raising=False)
    assert start_motor.get_python_exe() == sys.executable


def test_start_motor_is_port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        assert start_motor.is_port_in_use(port) is True

    # After close, port should not be in use
    assert start_motor.is_port_in_use(port) is False


def test_start_motor_launch_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.chdir(tmp_path)

    with patch("subprocess.Popen") as mock_popen:
        start_motor.launch("test.module", "test.log")
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert kwargs.get("creationflags") == 0x08000008
        assert (tmp_path / "logs" / "test.log").exists()
