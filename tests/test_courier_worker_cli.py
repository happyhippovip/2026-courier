import os
"""Tests for courier_worker CLI entrypoint and argument parsing robustness."""
import subprocess
import sys
from pathlib import Path
import pytest
from courier_worker.service import main as service_main


def test_cli_invocation_via_subprocess(monkeypatch):
    """Beweis: python -m courier_worker.cli akzeptiert Standardargumente ohne sys.argv[0] Kollision."""
    monkeypatch.delenv("COURIER_TOKEN", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    cmd = [
        sys.executable,
        "-m",
        "courier_worker.cli",
        "--controller",
        "http://127.0.0.1:9999",
        "--worker-id",
        "cli-test-worker",
    ]
    root = str(Path(__file__).resolve().parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = root
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=root, env=env)
    # Darf nicht an 'unrecognized arguments: ...cli.py' scheitern!
    assert "unrecognized arguments" not in res.stderr
    # Scheitert erst am ControllerConnect/Unreachable (Code 4)
    assert res.returncode == 4 or "no controller token" in res.stderr or "ControllerUnreachable" in res.stderr


def test_service_main_accepts_raw_sys_argv(monkeypatch):
    """service.main muss sowohl sys.argv (inkl. [0]) als auch sys.argv[1:] verarbeiten."""
    test_args = ["courier_worker.host", "--controller", "http://127.0.0.1:9999", "--worker-id", "test-w"]
    # Ohne Guard würde argparse versuchen, test_args[0] als positional argument zu parsen
    rc = service_main(test_args)
    assert rc == 4  # ControllerUnreachable, nicht exit(2) wegen argparse error
