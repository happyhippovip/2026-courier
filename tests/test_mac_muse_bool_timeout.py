"""run_muse rejects a bool timeout before any child starts.

True is an int. float(True) is 1.0, so MUSE_TIMEOUT_SECONDS true used to
start Muse and then kill it about one second later.
"""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"
POSIX_ONLY = pytest.mark.skipif(
    importlib.util.find_spec("fcntl") is None,
    reason="scripts/mac_worker imports the POSIX-only fcntl module",
)
TASK = {
    "goal_id": "g-muse-bool",
    "task_id": "t-muse-bool",
    "attempt_id": "a-1",
    "dispatch_id": "d-1",
    "instruction": "x",
    "mode": "MUSE",
    "estimated_cost_eur": 0.0,
}


def stray_sleep(seconds):
    try:
        out = subprocess.check_output(["pgrep", "-f", f"^sleep {seconds}$"], text=True)
    except subprocess.CalledProcessError:
        return set()
    return {int(p) for p in out.split()}


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_muse_bool", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "ws").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(daemon, "cost_gate", lambda *a, **k: {"allowed": True})
    monkeypatch.setenv("COURIER_MUSE_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("COURIER_MUSE_CLI", '{"protocol": "headless-v1"}')
    return daemon


def hang_instead(daemon, monkeypatch, instances, seconds):
    real_popen = daemon.subprocess.Popen

    def recording(*args, **kwargs):
        if kwargs.get("start_new_session"):
            proc = real_popen(
                ["sleep", str(seconds)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            instances.append(proc)
            return proc
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(daemon.subprocess, "Popen", recording)


@POSIX_ONLY
def test_bool_muse_timeout_does_not_spawn(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    assert stray_sleep(66) == set()
    instances = []
    hang_instead(daemon, monkeypatch, instances, 66)
    started = time.monotonic()
    try:
        result = daemon.run_muse(
            dict(TASK),
            {"WORKER_ID": "MAC-01", "MUSE_TIMEOUT_SECONDS": True},
        )
    except Exception as exc:
        result = {"status": "RAISED", "reason": type(exc).__name__, "error": str(exc)}
    elapsed = time.monotonic() - started
    assert instances == [], (
        round(elapsed, 3),
        [proc.returncode for proc in instances],
        result,
    )
    assert result["status"] == "FAILED"
    assert result.get("blocked") is True
    assert result.get("reason") == "INVALID_TIMEOUT"
    assert result["execution_mode"] == "MUSE"
    try:
        false_result = daemon.run_muse(
            dict(TASK),
            {"WORKER_ID": "MAC-01", "MUSE_TIMEOUT_SECONDS": False},
        )
    except Exception as exc:
        false_result = {"status": "RAISED", "reason": type(exc).__name__, "error": str(exc)}
    assert instances == []
    assert false_result["status"] == "FAILED"
    assert false_result.get("blocked") is True
    assert false_result.get("reason") == "INVALID_TIMEOUT"
    assert stray_sleep(66) == set()


@POSIX_ONLY
def test_numeric_muse_timeout_still_starts(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    instances = []
    real_popen = daemon.subprocess.Popen

    def recording(*args, **kwargs):
        if kwargs.get("start_new_session"):
            proc = real_popen(
                [sys.executable, "-c",
                 "print('```json\\n{\"status\": \"SUCCESS\"}\\n```')"],
                stdin=kwargs.get("stdin", subprocess.DEVNULL),
                stdout=kwargs.get("stdout"),
                stderr=kwargs.get("stderr"),
                start_new_session=True,
            )
            instances.append(proc)
            return proc
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(daemon.subprocess, "Popen", recording)
    result = daemon.run_muse(
        dict(TASK),
        {"WORKER_ID": "MAC-01", "MUSE_TIMEOUT_SECONDS": 30},
    )
    assert len(instances) == 1
    assert instances[0].poll() is not None
    assert result["status"] == "SUCCESS"
    assert result.get("reason") != "INVALID_TIMEOUT"
