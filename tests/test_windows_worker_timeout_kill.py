"""run_task() must not leave the PowerShell child running after a timeout.

communicate(timeout=...) raising TimeoutExpired does NOT kill the child
(Python docs); the daemon used to catch that as a generic exception and
return FAILED while the real process kept running unmanaged. This uses a
real subprocess (a portable stand-in for the hard-coded "powershell" call)
so the timeout/kill path is exercised for real, not mocked away.
"""
import importlib.util
import os
import subprocess
import time
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"


def load_daemon():
    spec = importlib.util.spec_from_file_location("windows_daemon_timeout_kill_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon


def test_timed_out_process_is_killed_not_left_running(monkeypatch):
    daemon = load_daemon()
    real_popen_class = subprocess.Popen
    real_communicate = subprocess.Popen.communicate  # captured before patching, else infinite recursion

    def spawn_sleep(cmd, **kwargs):
        # Stand-in for the hard-coded ["powershell", "-Command", instruction];
        # a real child process is what matters for this test, not its name.
        return real_popen_class(["sleep", "30"], **kwargs)

    def short_timeout(self, input=None, timeout=None):
        return real_communicate(self, input=input, timeout=0.2)

    monkeypatch.setattr(daemon.subprocess, "Popen", spawn_sleep)
    monkeypatch.setattr(real_popen_class, "communicate", short_timeout)

    result = daemon.run_task({"task_id": "t1", "instruction": "irrelevant", "goal_id": "g1"},
                             {"WORKER_ID": "WIN-TEST"})

    assert result["status"] == "FAILED"
    assert "Timed out" in result["stderr"]
    pid = int(result["run_id"])
    # The kill path used real communicate(); restore it before checking OS state.
    monkeypatch.setattr(real_popen_class, "communicate", real_communicate)
    deadline = time.monotonic() + 2
    alive = True
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
            break
        time.sleep(0.05)
    assert not alive, "child process from the timed-out task is still running (orphaned)"


def test_kill_process_tree_uses_taskkill_on_windows(monkeypatch):
    daemon = load_daemon()
    calls = []
    # daemon.os is the real os module (shared, singleton); patch only the
    # name it reads inside kill_process_tree, and always restore it, so this
    # test cannot leak "nt" into pathlib/pytest's own os.name for the process.
    real_name = daemon.os.name
    monkeypatch.setattr(daemon.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    try:
        daemon.os.name = "nt"
        daemon.kill_process_tree(4242)
    finally:
        daemon.os.name = real_name
    assert calls and calls[0][0][0][:2] == ["taskkill", "/PID"]
    assert "/T" in calls[0][0][0] and "/F" in calls[0][0][0]
