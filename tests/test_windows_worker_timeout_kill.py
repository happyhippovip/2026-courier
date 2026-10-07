"""run_task() must not leave the PowerShell child running after a timeout.

communicate(timeout=...) raising TimeoutExpired does NOT kill the child
(Python docs); the daemon used to catch that as a generic exception and
return FAILED while the real process kept running unmanaged. This uses a
real subprocess (a portable stand-in for the hard-coded "powershell" call)
so the timeout/kill path is exercised for real, not mocked away.
"""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import psutil
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
        # Stand-in for the hard-coded ["powershell", ...] call only; every other
        # Popen (e.g. taskkill inside kill_process_tree on Windows) stays real,
        # otherwise the kill path itself would be replaced and never kill.
        if cmd and cmd[0] == "powershell":
            # The interpreter exists on every runner; there is no `sleep` on Windows.
            cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
        return real_popen_class(cmd, **kwargs)

    def short_timeout(self, input=None, timeout=None):
        # Shorten only run_task's 600 s wait; taskkill and the post-kill drain
        # keep their real timeouts.
        return real_communicate(self, input=input, timeout=0.2 if timeout == 600 else timeout)

    monkeypatch.setattr(daemon.subprocess, "Popen", spawn_sleep)
    monkeypatch.setattr(real_popen_class, "communicate", short_timeout)

    result = daemon.run_task({"task_id": "t1", "instruction": "irrelevant", "goal_id": "g1"},
                             {"WORKER_ID": "WIN-TEST"})

    assert result["status"] == "FAILED"
    assert "Timed out" in result["stderr"]
    pid = int(result["run_id"])
    # The kill path used real communicate(); restore it before checking OS state.
    monkeypatch.setattr(real_popen_class, "communicate", real_communicate)
    deadline = time.monotonic() + 5
    alive = True
    # psutil, not os.kill(pid, 0): on Windows os.kill(pid, 0) terminates the process.
    while time.monotonic() < deadline:
        try:
            alive = psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            alive = False
        if not alive:
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
