from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts.windows_worker import health_check

REPO_ROOT = Path(__file__).resolve().parent.parent
WIN_WORKER_DIR = REPO_ROOT / "scripts" / "windows_worker"


def test_windows_worker_start_bat_exists_and_resolves_python():
    start_bat = WIN_WORKER_DIR / "start.bat"
    assert start_bat.exists(), "scripts/windows_worker/start.bat must exist for install_service.ps1 and bootstrap.ps1"
    if os.name == "nt":
        env = os.environ.copy()
        env["COURIER_WORKER_DRY_RUN"] = "1"
        completed = subprocess.run(
            ["cmd.exe", "/c", str(start_bat)],
            cwd=str(WIN_WORKER_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        assert "PYTHON_EXE=" in completed.stdout
        assert "DAEMON=" in completed.stdout


def test_windows_worker_health_check_runs_cleanly(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-key")
    report = health_check.run()
    assert "windows" in report["capabilities"]
    assert "powershell" in report["capabilities"]
    assert report["credentials"] == "FOUND (env)"
    assert isinstance(report["pending_task_checkpoint"], bool)
    assert isinstance(report["pending_result_checkpoint"], bool)
