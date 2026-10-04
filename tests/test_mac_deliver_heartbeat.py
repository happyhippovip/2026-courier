"""deliver_result inter-attempt heartbeat (M2 mac reliability lane).

Proves: while result delivery retries with exponential backoff (worst case
255s sleeps + 8 slow POST timeouts > the server 300s reclaim_stale
threshold, and result POSTs never touch last_seen), the worker heartbeats
between attempts so an actively-redelivering worker cannot go stale.
Without the fix, a full retry cycle posts zero heartbeats.
"""
import importlib.util
from pathlib import Path

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_deliver_heartbeat", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def run_failing_cycle(daemon, monkeypatch):
    calls = []
    sleeps = []

    def fake_post(config, endpoint, data):
        calls.append(endpoint)
        if endpoint == "/tasks/result":
            return None, "HTTP Error 500: boom"
        return {"status": "OK"}, None

    monkeypatch.setattr(daemon, "http_post", fake_post)
    monkeypatch.setattr(daemon.time, "sleep", lambda s: sleeps.append(s))
    outcome = daemon.deliver_result(
        {"WORKER_ID": "MAC-01", "COURIER_SERVER": "http://courier.invalid"},
        {"task_id": "t-deliver-1"})
    return outcome, calls, sleeps


def test_deliver_heartbeats_between_attempts(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    outcome, calls, sleeps = run_failing_cycle(daemon, monkeypatch)
    assert outcome == "UNDELIVERED"
    assert sleeps == [2 ** attempt for attempt in range(8)], sleeps
    heartbeats = [c for c in calls if c == "/workers/heartbeat"]
    assert len(heartbeats) == 8, f"expected a heartbeat per failed attempt, got {calls}"
    assert calls.count("/tasks/result") == 8


def test_deliver_success_posts_no_extra_heartbeat(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(daemon, "http_post",
                        lambda cfg, endpoint, data: calls.append(endpoint) or ({"ok": True}, None))
    monkeypatch.setattr(daemon.time, "sleep", lambda s: None)
    outcome = daemon.deliver_result({"WORKER_ID": "MAC-01"}, {"task_id": "t-deliver-2"})
    assert outcome == "DELIVERED"
    assert calls == ["/tasks/result"]
