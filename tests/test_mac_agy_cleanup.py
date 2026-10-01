"""mac run_agy: timeout must kill+drain+reap, never orphan child+fds (M04 R-AGY-ORPHAN)."""
import os
import subprocess
import sys

import pytest

from test_mac_worker_recovery import load_daemon


def test_fast_exit_passes_through(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    proc = subprocess.Popen([sys.executable, "-c", "print('hi')"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out, out, err = daemon.communicate_bounded(proc, 10)
    assert timed_out is False
    assert out.strip() == "hi"
    assert proc.poll() is not None


def test_timeout_kills_and_reaps_child(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pid = proc.pid
    timed_out, _, _ = daemon.communicate_bounded(proc, 0.2, drain_timeout=2, wait_timeout=2)
    assert timed_out is True
    assert proc.poll() is not None, "direct child must be reaped (no zombie)"
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_run_agy_timeout_returns_distinct_reason(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setattr(daemon.shutil, "which", lambda *a, **k: "/bin/sleep")
    calls = {}

    class FakeProc:
        def communicate(self, timeout=None):
            calls["communicate"] = True
            raise subprocess.TimeoutExpired("cmd", timeout)
        def kill(self):
            calls["kill"] = True
        def wait(self, timeout=None):
            calls["wait"] = True
            return -9

    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: FakeProc())
    result = daemon.run_agy({"task_id": "t1", "instruction": "x"}, {})
    assert result["status"] == "FAILED"
    assert result["reason"] == "AGY_TIMEOUT"
    assert result["execution_mode"] == "ANTIGRAVITY"
    assert calls.get("kill") and calls.get("wait")
