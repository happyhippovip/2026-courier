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

        for line in completed.stdout.splitlines():
            if line.startswith("PYTHON_EXE="):
                resolved_python = line.split("=", 1)[1].strip()
                check_proc = subprocess.run(
                    [resolved_python, "-c", "import psutil; import scripts.windows_worker.daemon"],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                )
                assert check_proc.returncode == 0, f"Resolved python {resolved_python} failed to import daemon/psutil: {check_proc.stderr}"



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


def test_windows_daemon_provider_wait_transitions_task_to_waiting_provider(tmp_path, monkeypatch):
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
        json={"worker_id": "WIN-TEST-02", "platform": "windows", "capabilities": ["windows"]},
    ).status_code == 200

    goal_res = client.post(
        "/goals",
        headers=headers,
        json={
            "goal_text": "Windows Daemon Provider Wait Proof",
            "workflow_plan": [
                {
                    "task_id": "win-wait-1",
                    "target_agent": "windows",
                    "instruction": "Write-Output '429 quota exceeded'",
                }
            ],
        },
    )
    assert goal_res.status_code == 200
    claimed = client.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-TEST-02"}).get_json()["task"]
    assert claimed is not None

    res_payload = win_daemon.run_task(claimed, {"WORKER_ID": "WIN-TEST-02"})
    assert res_payload["status"] == "PROVIDER_WAIT"

    wait_res = client.post(
        f"/tasks/{claimed['task_id']}/provider_wait",
        headers=headers,
        json={
            "worker_id": res_payload["worker_id"],
            "reason": res_payload["reason"],
            "wait_type": "WAITING_PROVIDER",
            "task_id": claimed["task_id"],
        },
    )
    assert wait_res.status_code == 200
    assert server_app.load_state()["tasks"]["win-wait-1"]["status"] == "WAITING_PROVIDER"


def test_windows_daemon_antigravity_mode_uses_skip_permissions_flag(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    from scripts.windows_worker import daemon as win_daemon

    captured_cmds = []

    class DummyProc:
        pid = 42424
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return ('```json\n{"status": "SUCCESS", "stdout_summary": "ok"}\n```', "")

    monkeypatch.setattr(win_daemon.shutil, "which", lambda name: "C:\\bin\\agy.exe" if name == "agy" else None)
    monkeypatch.setattr(
        win_daemon.subprocess,
        "Popen",
        lambda cmd, **kwargs: (captured_cmds.append(cmd) or DummyProc()),
    )

    task = {
        "goal_id": "g-agy",
        "task_id": "t-agy",
        "attempt_id": "t-agy:attempt:1",
        "dispatch_id": "d-agy",
        "execution_ref": "e-agy",
        "worker_id": "WIN-AGY",
        "mode": "ANTIGRAVITY",
        "instruction": "Verify Windows agy invocation",
        "server_binding": "local-runtime-v1",
    }
    res = win_daemon.run_task(task, {"WORKER_ID": "WIN-AGY"})
    assert res["status"] == "SUCCESS"
    assert len(captured_cmds) == 1
    assert "--dangerously-skip-permissions" in captured_cmds[0]
    assert captured_cmds[0][0] == "C:\\bin\\agy.exe"


def test_windows_worker_atomic_marker_write_and_recovery(tmp_path, monkeypatch):
    """Verify atomic marker writes, durable identity attachment on recovery, and corrupt marker quarantine."""
    from scripts.windows_worker import daemon as win_daemon

    marker_file = tmp_path / "result_marker.json"
    posted = []
    monkeypatch.setattr(win_daemon, "http_post_result", lambda payload: posted.append(dict(payload)))

    # 1. Valid result marker without canonical result_id gets canonical result_id + runtime_identity and is unlinked
    win_daemon._atomic_write_json(
        marker_file,
        {
            "goal_id": "g-rec",
            "task_id": "t-rec",
            "attempt_id": "t-rec:attempt:1",
            "dispatch_id": "d-rec",
            "execution_ref": "e-rec",
            "worker_id": "WIN-REC",
            "run_id": "win-native",
            "status": "SUCCESS",
            "artifacts": [],
            "server_binding": "local-runtime-v1",
        },
    )
    assert marker_file.exists()
    assert win_daemon.recover_result_marker(marker_file, "WIN-REC") is True
    assert not marker_file.exists()
    assert len(posted) == 1
    assert posted[0]["runtime_identity"] == "local-runtime-v1"
    assert posted[0]["result_id"].startswith("result-")

    # 2. Corrupt/truncated result marker is quarantined/unlinked without crashing loop
    marker_file.write_text("{corrupt-truncated-json", encoding="utf-8")
    assert win_daemon.recover_result_marker(marker_file, "WIN-REC") is False
    assert not marker_file.exists()


def test_windows_uninstall_and_demo_and_tempdir_safety():
    """Verify uninstall.ps1 preserves source code, demo/run_demo.py supports Windows process groups, and temp dirs are portable."""
    from demo import run_demo
    from scripts import muse_bench_server

    repo_root = Path(__file__).resolve().parents[1]
    uninstall_ps1 = (repo_root / "scripts" / "windows_worker" / "uninstall.ps1").read_text(encoding="utf-8")
    assert "Remove-Item -Path $PSScriptRoot -Recurse" not in uninstall_ps1
    assert '@("state", "logs", "worker_daemon.lock")' in uninstall_ps1

    # Verify demo._popen_group and _kill_process_tree work on Windows without os.setsid / os.killpg errors
    proc = run_demo._popen_group([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert proc.poll() is None
        run_demo._kill_process_tree(proc)
        proc.wait(timeout=5)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()

    # Verify muse_bench_server default WORK_DIR is portable (not raw POSIX /tmp on Windows)
    assert str(muse_bench_server.WORK_DIR).endswith("muse_workhorse")
    if sys.platform == "win32":
        assert not str(muse_bench_server.WORK_DIR).startswith("/tmp/")

    # Verify pre_courier_muse.muse_runner imports cleanly without fcntl and acquires/blocks locks on Windows
    from pre_courier_muse import muse_runner
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        lp = str(Path(td) / "muse_runner.lock")
        fd1 = muse_runner.is_another_instance_running(lp)
        assert fd1 is not None
        try:
            fd2 = muse_runner.is_another_instance_running(lp)
            assert fd2 is None
        finally:
            os.close(fd1)

    # Verify app.cannon.processes.process_identity populates creation_filetime and WindowsJob binds Job Object
    from app.cannon import processes as cannon_proc
    child, job, ident = cannon_proc.launch_gated(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=str(repo_root),
        env=dict(os.environ),
    )
    try:
        assert ident["pid"] == child.pid
        assert ident["creation_filetime"] is not None
        if os.name == "nt":
            assert job.job_handle is not None
    finally:
        job.close()
        child.wait(timeout=5)






