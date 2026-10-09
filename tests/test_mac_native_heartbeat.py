"""run_native in-execution heartbeat (M2 mac reliability lane).

Proves: while a native child executes, the worker heartbeats (same 30s
cadence as run_muse/run_agy) so the server's 300s reclaim_stale cannot
quarantine a still-running task. NATIVE_TIMEOUT_SECONDS allows up to 600s,
twice the threshold. Without the fix, a silent run posts zero heartbeats.
"""
import importlib.util
import subprocess
from pathlib import Path

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_native_heartbeat", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def run_with(daemon, monkeypatch, instruction, config, interval=1):
    beats = []
    monkeypatch.setattr(daemon, "http_post",
                        lambda cfg, endpoint, data: beats.append((endpoint, data)) or ({}, None))
    monkeypatch.setattr(daemon, "NATIVE_HEARTBEAT_INTERVAL_SECONDS", interval, raising=False)
    task = {"task_id": "task-native-hb-1", "action": "echo", "instruction": instruction}
    return daemon.run_native(task, config), beats


def hang_sleep_instead(daemon, monkeypatch, seconds):
    """Echo no longer spawns a shell, so task text cannot stretch a run. Tests
    needing a long-lived child simulate one here: heartbeat cadence, not task
    text, is what they exercise."""
    real_popen = daemon.subprocess.Popen

    def hang_instead(*args, **kwargs):
        assert kwargs.get("shell") in (None, False)  # no shell anywhere
        if not kwargs.get("start_new_session"):
            # ps probes (process_identity) and friends run untouched.
            return real_popen(*args, **kwargs)
        return real_popen(["sleep", str(seconds)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True,
                          start_new_session=True)

    monkeypatch.setattr(daemon.subprocess, "Popen", hang_instead)


def test_native_heartbeats_during_execution(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    hang_sleep_instead(daemon, monkeypatch, 4)
    result, beats = run_with(daemon, monkeypatch, "echo go", {
        "WORKER_ID": "MAC-01", "COURIER_SERVER": "http://courier.invalid",
        "NATIVE_TIMEOUT_SECONDS": 30})
    assert result["status"] == "SUCCESS"
    hb = [data for endpoint, data in beats if endpoint == "/workers/heartbeat"]
    assert len(hb) >= 2, f"expected heartbeats during 4s run, got {beats}"
    assert all(d.get("worker_id") == "MAC-01" for d in hb)


def test_native_no_server_configured_no_heartbeat_attempt(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    result, beats = run_with(daemon, monkeypatch, "echo hi",
                             {"WORKER_ID": "MAC-01", "NATIVE_TIMEOUT_SECONDS": 30})
    assert result["status"] == "SUCCESS"
    assert result["stdout"] == "hi\n"
    assert beats == []


def test_native_timeout_still_fail_closed_with_heartbeat(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    hang_sleep_instead(daemon, monkeypatch, 60)
    result, beats = run_with(daemon, monkeypatch, "echo go", {
        "WORKER_ID": "MAC-01", "COURIER_SERVER": "http://courier.invalid",
        "NATIVE_TIMEOUT_SECONDS": 3}, interval=1)
    assert result["status"] == "FAILED"
    assert result["reason"] == "TIMEOUT"
    hb = [data for endpoint, data in beats if endpoint == "/workers/heartbeat"]
    assert len(hb) >= 1
    try:
        out = subprocess.check_output(["pgrep", "-f", "^sleep 60$"], text=True)
        assert out.strip() == "", f"stray sleep survived: {out}"
    except subprocess.CalledProcessError:
        pass
