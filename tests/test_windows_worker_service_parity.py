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


def test_windows_daemon_run_task_produces_valid_durable_result_for_server(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    from server import app as server_app
    from scripts.windows_worker import daemon as win_daemon

    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "BATCH_QUEUE_DIR", str(tmp_path / "empty-batches"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    client = server_app.app.test_client()
    headers = {"Authorization": "Bearer test-secret"}

    assert client.post(
        "/workers/register",
        headers=headers,
        json={"worker_id": "WIN-TEST-01", "platform": "windows", "capabilities": ["windows"]},
    ).status_code == 200

    goal_res = client.post(
        "/goals",
        headers=headers,
        json={
            "goal_text": "Windows Daemon DurableResult Contract Proof",
            "workflow_plan": [
                {
                    "task_id": "win-task-1",
                    "target_agent": "windows",
                    "instruction": "Write-Output 'WIN_DAEMON_OK'",
                }
            ],
        },
    )
    assert goal_res.status_code == 200

    claim_res = client.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-TEST-01"})
    assert claim_res.status_code == 200
    claimed_task = claim_res.get_json()["task"]
    assert claimed_task is not None

    result_payload = win_daemon.run_task(claimed_task, {"WORKER_ID": "WIN-TEST-01"})
    assert result_payload["status"] == "SUCCESS"
    assert "WIN_DAEMON_OK" in result_payload["stdout"]
    assert result_payload["runtime_identity"] == claimed_task["server_binding"]

    post_res = client.post("/tasks/result", headers=headers, json=result_payload)
    assert post_res.status_code == 200, post_res.get_json()

