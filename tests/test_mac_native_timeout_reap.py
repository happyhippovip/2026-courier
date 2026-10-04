"""run_native timeout + interruption reap (M2 mac reliability lane).

Proves: a hung native child is group-killed on timeout (FAILED/TIMEOUT, no
surviving process) instead of blocking the daemon forever; a daemon
interruption (WorkerShutdown, a BaseException) during execution still reaps
the child and propagates; fast echo/git_status behavior is unchanged.
"""
import importlib.util
import subprocess
import time
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_native_reap", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def stray_sleep(seconds):
    """PIDs of system-wide `sleep <seconds>` processes (distinctive duration)."""
    try:
        out = subprocess.check_output(["pgrep", "-f", f"^sleep {seconds}$"], text=True)
    except subprocess.CalledProcessError:
        return set()
    return {int(p) for p in out.split()}


def test_native_timeout_kills_group_and_reaps(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    assert stray_sleep(63) == set()  # distinctive duration: no foreign process
    task = {"task_id": "task-native-1", "action": "echo",
            "instruction": "echo go; sleep 63"}
    started = time.monotonic()
    result = daemon.run_native(task, {"NATIVE_TIMEOUT_SECONDS": 2})
    elapsed = time.monotonic() - started
    assert result["status"] == "FAILED"
    assert result["reason"] == "TIMEOUT"
    assert result["execution_mode"] == "NATIVE"
    assert "TIMEOUT" in result["stderr"]
    assert elapsed < 30  # timeout + grace, not the 63s sleep
    assert stray_sleep(63) == set()  # group incl. shell grandchild dead


def test_native_fast_paths_unaffected(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    echo = daemon.run_native({"task_id": "t-e", "action": "echo", "instruction": "echo hi"},
                             {"WORKER_ID": "MAC-01"})
    assert echo["status"] == "SUCCESS"
    assert echo["stdout"] == "hi\n"
    assert echo["exit_code"] == 0
    assert echo["execution_mode"] == "NATIVE"
    assert "reason" not in echo
    git = daemon.run_native({"task_id": "t-g", "action": "git_status", "instruction": ""},
                            {"WORKER_ID": "MAC-01"})
    assert git["execution_mode"] == "NATIVE"
    assert git["exit_code"] == 0
    assert git["status"] == "SUCCESS"


def test_native_interruption_reaps_and_propagates(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    real_popen = subprocess.Popen
    instances = []

    class RaiseOnce(real_popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._is_shell = bool(kwargs.get("shell"))

        def communicate(self, *args, **kwargs):
            if self._is_shell:
                raise daemon.WorkerShutdown("SIGTERM during native exec")
            return super().communicate(*args, **kwargs)

    orig_popen = daemon.subprocess.Popen

    def recording(*args, **kwargs):
        proc = RaiseOnce(*args, **kwargs)
        if kwargs.get("shell"):
            instances.append(proc)
        return proc

    monkeypatch.setattr(daemon.subprocess, "Popen", recording)
    try:
        with pytest.raises(daemon.WorkerShutdown):
            daemon.run_native({"task_id": "t-i", "action": "echo",
                               "instruction": "echo go; sleep 64"},
                              {"WORKER_ID": "MAC-01"})
    finally:
        monkeypatch.setattr(daemon.subprocess, "Popen", orig_popen)
    assert len(instances) == 1
    assert instances[0].poll() is not None  # reaped by finally: no zombie/orphan
    assert stray_sleep(64) == set()
