import os
import sys
import json
import time
import signal
import hashlib
import tempfile
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WIN_WORKER_DIR = REPO_ROOT / "scripts" / "windows_worker"
SERVER_DIR = REPO_ROOT / "server"


def test_runtime_identity_and_reboot_ownership_powershell():
    """Verify Scheduled Task scripts configure OS-owned runtime as SYSTEM with AtStartup trigger and no interactive login."""
    worker_install = (WIN_WORKER_DIR / "install_service.ps1").read_text(encoding="utf-8")
    server_install = (SERVER_DIR / "install_server_service.ps1").read_text(encoding="utf-8")
    bootstrap = (WIN_WORKER_DIR / "bootstrap.ps1").read_text(encoding="utf-8")

    # 1. Worker Service Identity & Trigger
    assert '-UserId "SYSTEM"' in worker_install, "Worker must run as SYSTEM for unattended reboot ownership"
    assert "-LogonType ServiceAccount" in worker_install, "Worker must use ServiceAccount logon (not Interactive)"
    assert "New-ScheduledTaskTrigger -AtStartup" in worker_install, "Worker must trigger at OS startup"
    assert "-MultipleInstances IgnoreNew" in worker_install, "Worker must prevent duplicate task scheduler instances"
    assert "-ExecutionTimeLimit (New-TimeSpan -Days 0)" in worker_install, "Worker execution time limit must be unbounded"

    # 2. Server Service Identity & Trigger
    assert '-UserId "SYSTEM"' in server_install, "Server must run as SYSTEM for unattended reboot ownership"
    assert "-LogonType ServiceAccount" in server_install, "Server must use ServiceAccount logon (not Interactive)"
    assert "New-ScheduledTaskTrigger -AtStartup" in server_install, "Server must trigger at OS startup"
    assert "-MultipleInstances IgnoreNew" in server_install, "Server must prevent duplicate task scheduler instances"

    # 3. Credential Identity compatibility (SYSTEM credential store)
    assert 'keyring.set_password(\'courier_worker\', \'courier_api_key\'' in bootstrap
    assert '-UserId "SYSTEM"' in bootstrap, "bootstrap.ps1 must provision credentials into SYSTEM store"
    assert "-LogonType ServiceAccount" in bootstrap, "bootstrap.ps1 credential task must use ServiceAccount"


def test_broad_process_kill_prohibited():
    """Verify stop.bat, status.bat, and daemon.py do NOT perform broad process killing."""
    stop_bat = (WIN_WORKER_DIR / "stop.bat").read_text(encoding="utf-8")
    status_bat = (WIN_WORKER_DIR / "status.bat").read_text(encoding="utf-8")
    daemon_py = (WIN_WORKER_DIR / "daemon.py").read_text(encoding="utf-8")

    # Assert no broad process kills
    assert "taskkill /F /IM python.exe" not in stop_bat, "Broad taskkill python.exe prohibited in stop.bat"
    assert "taskkill /F /IM powershell.exe" not in stop_bat, "Broad taskkill powershell.exe prohibited in stop.bat"
    assert "taskkill /IM python.exe" not in stop_bat, "Broad taskkill python.exe prohibited in stop.bat"
    assert "taskkill /IM powershell.exe" not in stop_bat, "Broad taskkill powershell.exe prohibited in stop.bat"

    # Assert status does not broad-filter all python
    assert "findstr /I \"python\"" not in status_bat, "Broad python matching prohibited in status.bat"

    # Assert stop uses schtasks End and exact PID
    assert 'schtasks /End /TN "CourierWindowsWorker"' in stop_bat
    assert "taskkill /F /T /PID" in stop_bat

    # Assert daemon.py uses targeted tree kill only
    assert "taskkill /F /IM" not in daemon_py
    assert 'taskkill", "/F", "/T", "/PID"' in daemon_py


def test_no_manual_secrets_or_pythonpath():
    """Customer should not need Git, manual PYTHONPATH, manual API key export."""
    config_file = WIN_WORKER_DIR / "config.json"
    start_bat = (WIN_WORKER_DIR / "start.bat").read_text(encoding="utf-8")

    # Config should not store plaintext secrets
    if config_file.exists():
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
        assert "COURIER_API_KEY" not in cfg, "Secret API key must not be stored in config.json"

    # start.bat should use relative directory and uv run without manual PYTHONPATH
    assert 'cd /d "%~dp0"' in start_bat
    assert "set PYTHONPATH=" not in start_bat


def test_duplicate_worker_lock_prevention():
    """Test single instance locking mechanism in daemon.py."""
    sys.path.insert(0, str(WIN_WORKER_DIR))
    import daemon

    test_worker_id = f"test-win-worker-{os.getpid()}"
    lock1 = daemon.acquire_lock(test_worker_id)
    assert lock1 is not None, "First instance must acquire lock"
    assert lock1.exists(), "Lock file must exist"

    # Attempt second acquire with same worker_id -> must fail
    lock2 = daemon.acquire_lock(test_worker_id)
    assert lock2 is None, "Second instance must be rejected to prevent duplicate workers"

    # Cleanup first lock
    if lock1.exists():
        lock1.unlink()
    pid_file = WIN_WORKER_DIR / "daemon.pid"
    if pid_file.exists():
        pid_file.unlink()

    # After cleanup, lock can be acquired again
    lock3 = daemon.acquire_lock(test_worker_id)
    assert lock3 is not None, "Must be able to acquire lock after cleanup"
    if lock3.exists():
        lock3.unlink()
    if pid_file.exists():
        pid_file.unlink()


def test_exact_child_tree_cleanup_on_timeout():
    """Verify that child process tree is cleanly terminated without leaking descendants."""
    sys.path.insert(0, str(WIN_WORKER_DIR))
    import daemon

    # Spawn a parent process that spawns a child that sleeps
    parent_script = """
import subprocess, sys, time
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
time.sleep(60)
"""
    proc = subprocess.Popen([sys.executable, "-c", parent_script])
    parent_pid = proc.pid

    # Let children spin up
    time.sleep(0.5)

    # Terminate exact process tree
    daemon.kill_process_tree(parent_pid)
    try:
        proc.communicate(timeout=3)
    except Exception:
        pass

    assert not daemon.is_pid_running(parent_pid), "Parent PID must be terminated"


def test_canonical_state_remote_decision(monkeypatch):
    """Verify that local worker treats Courier server as canonical authority upon 400/409 rejection."""
    sys.path.insert(0, str(WIN_WORKER_DIR))
    import daemon
    import urllib.error

    class MockHTTPError(urllib.error.HTTPError):
        def __init__(self, code):
            super().__init__("http://127.0.0.1:8080/tasks/result", code, f"HTTP Error {code}", {}, None)
        def read(self):
            return b'{"error": "Task already completed or reassigned"}'

    # When server responds with 409 Conflict (canonical authority decision)
    def mock_urlopen_409(req, data=None, timeout=10):
        raise MockHTTPError(409)

    monkeypatch.setattr(daemon.urllib.request, "urlopen", mock_urlopen_409)

    res = daemon.http_post_result({"task_id": "task-test-409", "status": "SUCCESS"})
    assert res is False, "Worker must accept permanent 409 rejection and not loop infinitely"


def test_timeout_exact_cleanup_leaves_persistent_service_running():
    """Verify that killing a timed out worker child leaves persistent services (like CourierServer) completely untouched."""
    sys.path.insert(0, str(WIN_WORKER_DIR))
    import daemon

    # 1. Start a mock persistent service (e.g. CourierServer)
    srv = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    srv_pid = srv.pid

    # 2. Start a worker task child
    task_child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    child_pid = task_child.pid

    time.sleep(0.3)
    assert daemon.is_pid_running(srv_pid), "Server must be running"
    assert daemon.is_pid_running(child_pid), "Child must be running"

    # 3. Simulate timeout of worker child and exact tree cleanup
    daemon.kill_process_tree(child_pid)
    try:
        task_child.communicate(timeout=2)
    except Exception:
        pass

    # 4. Assert child is dead, BUT persistent server is still alive
    assert not daemon.is_pid_running(child_pid), "Worker child must be dead"
    assert daemon.is_pid_running(srv_pid), "Persistent Courier service must survive untouched"

    # Cleanup persistent mock server
    daemon.kill_process_tree(srv_pid)
    try:
        srv.communicate(timeout=2)
    except Exception:
        pass


def test_bounded_execution_artifacts_sha256(tmp_path, monkeypatch):
    """Verify bounded execution produces correct artifacts and sha256 digests."""
    sys.path.insert(0, str(WIN_WORKER_DIR))
    import daemon

    test_file = tmp_path / "courier_canary_test.txt"
    test_content = b"CANARY_OK_VERIFIED"
    test_file.write_bytes(test_content)
    expected_sha = hashlib.sha256(test_content).hexdigest()

    monkeypatch.chdir(tmp_path)

    task = {
        "task_id": "task-win-001",
        "instruction": "Write-Output 'Done'",
        "artifacts": ["courier_canary_test.txt"]
    }
    config = {"WORKER_ID": "TEST-WIN-01"}

    # Mock powershell command to succeed
    def mock_popen(*args, **kwargs):
        class MockProc:
            pid = 12345
            returncode = 0
            def communicate(self, timeout=None):
                return ("Done\n", "")
        return MockProc()

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    res = daemon.run_task(task, config)
    assert res["status"] == "SUCCESS"
    assert len(res["artifacts"]) == 1
    assert res["artifacts"][0]["path"] == "courier_canary_test.txt"
    assert res["artifacts"][0]["sha256"] == expected_sha

