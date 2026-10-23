"""Crash recovery for the Windows daemon using local files only.

The phases on disk are CLAIMED, STARTED, RESULT_READY, and RELEASE_PENDING.
A claimed task may run once. A task that already started must not run again.
A delivered result must not run again. Nothing here calls a provider.
"""
import json
import logging

from tests.test_windows_worker_contract import (
    Bridge,
    central,
    go,
    load_daemon,
    load_daemon_again,
    state_file,
)


def _capture_log():
    """Record the daemon's own stdout log lines.

    Pytest configures the root logger before the daemon's basicConfig can,
    and that root level drops INFO. Production starts with the daemon's
    INFO file handler. The test lowers the level only while it listens.
    """
    lines = []

    class Capture(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    root = logging.getLogger()
    previous = root.level
    root.setLevel(logging.INFO)
    handler = Capture()
    root.addHandler(handler)
    return root, previous, handler, lines


def _claim(http, headers):
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    claimed["worker_phase"] = "CLAIMED"
    return claimed


def test_queue_file_survives_process_replacement(tmp_path, monkeypatch):
    """CUR-WIN-045: an abrupt process end leaves the same queue bytes."""
    _srv, http, headers = central(tmp_path, monkeypatch)
    daemon = load_daemon(tmp_path, monkeypatch)
    claimed = _claim(http, headers)
    path = state_file(daemon)
    path.write_text(json.dumps(claimed))
    raw = path.read_bytes()

    daemon2 = load_daemon_again(tmp_path, monkeypatch)
    assert state_file(daemon2).read_bytes() == raw
    assert json.loads(raw)["worker_phase"] == "CLAIMED"


def test_claimed_workkey_resumes_once(tmp_path, monkeypatch):
    """CUR-WIN-046: a claim that never started is run once, then delivered."""
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    claimed = _claim(http, headers)
    state_file(daemon).write_text(json.dumps(claimed))
    effect = daemon.APP_DATA_DIR / "effect.txt"
    root, previous, handler, lines = _capture_log()
    try:
        go(daemon, monkeypatch, Bridge(http, headers, max_calls=6), executions, effect=effect, tmp_path=tmp_path)
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)

    evidence = daemon.LOG_DIR / "recovery-claimed.log"
    evidence.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert executions == ["task-1"]
    assert not state_file(daemon).exists()
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"
    assert "Found unfinished task task-1 in phase CLAIMED" in evidence.read_text(encoding="utf-8")


def test_crash_after_started_does_not_rerun(tmp_path, monkeypatch):
    """CUR-WIN-047: STARTED may already have had effects, so recovery releases it."""
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    claimed = _claim(http, headers)
    claimed["worker_phase"] = "STARTED"
    state_file(daemon).write_text(json.dumps(claimed))
    root, previous, handler, lines = _capture_log()
    try:
        go(daemon, monkeypatch, Bridge(http, headers, max_calls=6), executions, tmp_path=tmp_path)
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)

    evidence = daemon.LOG_DIR / "recovery-started.log"
    evidence.write_text("\n".join(lines) + "\n", encoding="utf-8")
    text = evidence.read_text(encoding="utf-8")
    assert executions == []
    assert not state_file(daemon).exists()
    task = srv.load_state()["tasks"]["task-1"]
    assert task["status"] == "HUMAN_REQUIRED"
    assert task["recovery_reason"] == "WORKER_RESTARTED_AND_LOST_STATE"
    assert "interrupted during execution" in text
    assert "Running task" not in text


def test_restart_after_final_does_not_execute_again(tmp_path, monkeypatch):
    """CUR-WIN-049: a delivered result is not claimed or executed on the next start."""
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    effect = daemon.APP_DATA_DIR / "effect.txt"
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=4), executions, effect=effect, tmp_path=tmp_path)
    assert executions == ["task-1"]
    assert not state_file(daemon).exists()
    attempts = srv.load_state()["tasks"]["task-1"]["attempts"]

    daemon2, again = load_daemon_again(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon2.APP_DATA_DIR)
    bridge = Bridge(http, headers, max_calls=4)
    go(daemon2, monkeypatch, bridge, again, tmp_path=tmp_path)

    assert again == []
    assert bridge.posted("/tasks/result") == []
    task = srv.load_state()["tasks"]["task-1"]
    assert task["status"] == "RESULT_RECEIVED"
    assert task["attempts"] == attempts
    assert not state_file(daemon2).exists()
