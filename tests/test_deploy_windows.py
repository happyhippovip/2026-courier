import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_deploy_courier_health_bat():
    bat_path = REPO_ROOT / "deploy" / "courier-health.bat"
    assert bat_path.exists()

    # Run with dummy unreachable server to verify it executes curl and terminates properly
    env = os.environ.copy()
    env["COURIER_SERVER"] = "http://127.0.0.1:59999"

    proc = subprocess.run(
        ["cmd.exe", "/c", str(bat_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    # curl should execute (exit code might be curl error 7 since port is closed)
    # The batch script itself executes without syntax error
    assert proc.returncode in [0, 7]


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_deploy_courier_status_bat(tmp_path):
    bat_path = REPO_ROOT / "deploy" / "courier-status.bat"
    assert bat_path.exists()

    env = os.environ.copy()
    env["COURIER_SERVER"] = "http://127.0.0.1:59999"
    env["COURIER_API_KEY"] = "test-token"

    proc = subprocess.run(
        ["cmd.exe", "/c", str(bat_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode in [0, 7]
