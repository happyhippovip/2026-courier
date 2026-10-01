"""run_agy timeout kill+reap (G1 mac restart/cleanup lane, read-only harness).

Proves: on timeout the wrapper+agy process GROUP is killed (not just the
direct child — limit_wrapper.sh spawns agy as a grandchild, so plain
kill() would orphan it) and the direct child is reaped (no zombie).
"""
import importlib.util
import os
import stat
import subprocess
import time
import types
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch, timeout=2):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_agy_reap", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(daemon.time, "sleep", lambda seconds: None)
    config = {"COURIER_SERVER": "http://courier.invalid", "WORKER_ID": "MAC-01",
              "AGY_TIMEOUT_SECONDS": timeout}
    return daemon, config


def make_fake_agy(tmp_path, body):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    agy = bindir / "agy"
    agy.write_text("#!/bin/sh\n" + body + "\n")
    agy.chmod(agy.stat().st_mode | stat.S_IEXEC)
    return bindir


def recording_popen_ns(instances):
    real = subprocess.Popen

    class RecordingPopen(real):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

    return types.SimpleNamespace(
        PIPE=subprocess.PIPE,
        DEVNULL=subprocess.DEVNULL,
        TimeoutExpired=subprocess.TimeoutExpired,
        Popen=RecordingPopen,
    )


def run_with_fake_agy(daemon, monkeypatch, tmp_path, body, timeout=2):
    bindir = make_fake_agy(tmp_path, body)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    instances = []
    monkeypatch.setattr(daemon, "subprocess", recording_popen_ns(instances))
    task = {"task_id": "task-agy-1", "instruction": "do work"}
    started = time.monotonic()
    result = daemon.run_agy(task, {"AGY_TIMEOUT_SECONDS": timeout})
    elapsed = time.monotonic() - started
    return result, instances, elapsed


def test_agy_timeout_kills_group_and_reaps(tmp_path, monkeypatch):
    daemon, _ = load_daemon(tmp_path, monkeypatch)
    result, instances, elapsed = run_with_fake_agy(
        daemon, monkeypatch, tmp_path, "sleep 60", timeout=2)
    assert result["status"] == "FAILED"
    assert result["reason"] == "TIMEOUT"
    assert result["execution_mode"] == "ANTIGRAVITY"
    assert elapsed < 30  # timeout + grace, not the 60s sleep
    assert len(instances) == 1
    proc = instances[0]
    assert proc.poll() is not None  # direct child reaped: no zombie
    assert daemon.group_exists(proc.pid) is False  # group incl. grandchild dead


def test_agy_fast_success_unaffected(tmp_path, monkeypatch):
    daemon, _ = load_daemon(tmp_path, monkeypatch)
    body = 'printf \'```json\\n{"status": "SUCCESS", "stdout_summary": "ok"}\\n```\\n\''
    result, instances, _ = run_with_fake_agy(
        daemon, monkeypatch, tmp_path, body, timeout=30)
    assert result["status"] == "SUCCESS"
    assert result["execution_mode"] == "ANTIGRAVITY"
    assert len(instances) == 1
    assert instances[0].poll() is not None
