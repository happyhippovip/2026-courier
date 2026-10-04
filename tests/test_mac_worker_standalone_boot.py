"""Daemon must boot when launched standalone (launchd / run_physical spawn).

Regression: the Resource Governor commit added a top-level
`from resource_governor import governor` to scripts/mac_worker/daemon.py
without ensuring scripts/ is on sys.path. Launched as
`python scripts/mac_worker/daemon.py` (cwd=repo root, launchd, or the
physical runner), the import failed with ModuleNotFoundError, the worker
died instantly, and claimed tasks stayed QUEUED forever.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "scripts" / "mac_worker" / "daemon.py"


def _clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["COURIER_WORKER_HOME"] = str(home)
    env["COURIER_API_KEY"] = "dummy-test-key-not-real"
    env["COURIER_SERVER"] = "http://127.0.0.1:1"
    return env


def test_daemon_boots_standalone_without_import_error(tmp_path):
    """Spawned daemon survives startup; no ModuleNotFoundError in stderr."""
    home = tmp_path / "worker_home"
    home.mkdir()
    proc = subprocess.Popen(
        [sys.executable, str(DAEMON)],
        cwd=str(tmp_path),
        env=_clean_env(home),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(6)
        assert proc.poll() is None, "daemon exited during standalone boot"
    finally:
        proc.terminate()
        try:
            _, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate(timeout=10)
    assert "ModuleNotFoundError" not in stderr
    assert "Traceback" not in stderr
