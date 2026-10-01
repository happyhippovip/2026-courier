"""windows run_task: timeout must kill+drain+reap, never orphan child+fds (M04)."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_win_daemon():
    spec = importlib.util.spec_from_file_location(
        "windows_daemon_cleanup_under_test",
        ROOT / "scripts" / "windows_worker" / "daemon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fast_exit_passes_through():
    daemon = load_win_daemon()
    proc = subprocess.Popen([sys.executable, "-c", "print('hi')"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out, out, _ = daemon.communicate_bounded(proc, 10)
    assert timed_out is False
    assert out.strip() == "hi"
    assert proc.poll() is not None


def test_timeout_kills_and_reaps_child():
    daemon = load_win_daemon()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pid = proc.pid
    timed_out, _, _ = daemon.communicate_bounded(proc, 0.2, drain_timeout=2, wait_timeout=2)
    assert timed_out is True
    assert proc.poll() is not None, "direct child must be reaped (no zombie)"
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_run_task_timeout_shape_and_cleanup(monkeypatch):
    daemon = load_win_daemon()

    class FakeProc:
        pid = 4242
        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired("cmd", timeout)
        def kill(self):
            pass
        def wait(self, timeout=None):
            return -9

    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: FakeProc())
    result = daemon.run_task({"task_id": "t1", "instruction": "x"},
                             {"WORKER_ID": "WINDOWS-01"})
    assert result["status"] == "FAILED"
    assert result["reason"] == "TASK_TIMEOUT"
    assert result["task_id"] == "t1"
    assert result["run_id"] == "4242"
