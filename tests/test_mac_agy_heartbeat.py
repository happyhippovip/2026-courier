"""run_agy in-execution heartbeat (M2 mac reliability lane).

Proves: while agy executes, the worker heartbeats (same 30s cadence as
run_muse) so the server's 300s reclaim_stale cannot quarantine a still-
running task. Without the fix, a silent run posts zero heartbeats.
"""
import importlib.util
import os
import stat
import subprocess
import time
from pathlib import Path

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_agy_heartbeat", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def make_fake_agy(tmp_path, body):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    agy = bindir / "agy"
    agy.write_text("#!/bin/sh\n" + body + "\n")
    agy.chmod(agy.stat().st_mode | stat.S_IEXEC)
    return bindir


def run_with(daemon, monkeypatch, tmp_path, body, config, interval=1):
    bindir = make_fake_agy(tmp_path, body)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    beats = []
    monkeypatch.setattr(daemon, "http_post",
                        lambda cfg, endpoint, data: beats.append((endpoint, data)) or ({}, None))
    monkeypatch.setattr(daemon, "AGY_HEARTBEAT_INTERVAL_SECONDS", interval, raising=False)
    task = {"task_id": "task-agy-hb-1", "instruction": "do work"}
    started = time.monotonic()
    result = daemon.run_agy(task, config)
    return result, beats, time.monotonic() - started


def test_agy_heartbeats_during_execution(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    body = ('sleep 4; printf \'```json\\n{"status": "SUCCESS", '
            '"stdout_summary": "ok"}\\n```\\n\'')
    result, beats, _ = run_with(daemon, monkeypatch, tmp_path, body, {
        "WORKER_ID": "MAC-01", "COURIER_SERVER": "http://courier.invalid",
        "AGY_TIMEOUT_SECONDS": 30})
    assert result["status"] == "SUCCESS"
    hb = [data for endpoint, data in beats if endpoint == "/workers/heartbeat"]
    assert len(hb) >= 2, f"expected heartbeats during 4s run, got {beats}"
    assert all(d.get("worker_id") == "MAC-01" for d in hb)


def test_agy_no_server_configured_no_heartbeat_attempt(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    body = 'printf \'```json\\n{"status": "SUCCESS", "stdout_summary": "ok"}\\n```\\n\''
    result, beats, _ = run_with(daemon, monkeypatch, tmp_path, body,
                                {"WORKER_ID": "MAC-01", "AGY_TIMEOUT_SECONDS": 30})
    assert result["status"] == "SUCCESS"
    assert beats == []


def test_agy_timeout_still_fail_closed_with_heartbeat(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    result, beats, elapsed = run_with(daemon, monkeypatch, tmp_path, "sleep 60", {
        "WORKER_ID": "MAC-01", "COURIER_SERVER": "http://courier.invalid",
        "AGY_TIMEOUT_SECONDS": 3}, interval=1)
    assert result["status"] == "FAILED"
    assert result["reason"] == "TIMEOUT"
    assert elapsed < 30
    hb = [data for endpoint, data in beats if endpoint == "/workers/heartbeat"]
    assert len(hb) >= 1
    try:
        out = subprocess.check_output(["pgrep", "-f", "^sleep 60$"], text=True)
        assert out.strip() == "", f"stray sleep survived: {out}"
    except subprocess.CalledProcessError:
        pass
