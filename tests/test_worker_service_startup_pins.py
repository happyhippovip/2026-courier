"""Startup + watcher pins for courier_worker.service (lane L4, P9, tests only).

Covers the worker's startup edge that the other service-hardening lanes do
not pin: reading the controller token from the home directory
(WorkerLoop._default_client, no connection attempted), the CancelWatcher
thread lifecycle without any network (start/stop/_follow with a faked
_subscribe), and _deliver_payload outbox durability with a fake client.

No behavior change. No network: every controller/socket interaction is
faked or pointed at an unroutable local port that is never connected to.
"""

from __future__ import annotations

import os
import threading

import pytest

import courier_worker.service as SVC
from courier_worker.host import outbox_read_all
from courier_worker.service import (
    CancelWatcher,
    ControllerError,
    ControllerUnreachable,
    WorkerLoop,
)

UNROUTABLE = "http://127.0.0.1:9"


def _loop(home, **kwargs):
    kwargs.setdefault("engine", object())
    return WorkerLoop(home, UNROUTABLE, "worker-test", 1.0, **kwargs)


def _write_token(home: str, content: str) -> str:
    rundir = os.path.join(home, "run")
    os.makedirs(rundir, exist_ok=True)
    path = os.path.join(rundir, "controller.token")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# -- WorkerLoop._default_client ------------------------------------------------


def test_default_client_missing_token_file_is_unreachable(tmp_path):
    loop = _loop(str(tmp_path))
    with pytest.raises(ControllerUnreachable):
        loop._default_client()


def test_default_client_missing_token_names_path_not_value(tmp_path):
    loop = _loop(str(tmp_path))
    with pytest.raises(ControllerUnreachable) as excinfo:
        loop._default_client()
    assert "controller.token" in str(excinfo.value)


def test_default_client_empty_token_file_is_unreachable(tmp_path):
    _write_token(str(tmp_path), "")
    with pytest.raises(ControllerUnreachable):
        _loop(str(tmp_path))._default_client()


def test_default_client_blank_token_file_is_unreachable(tmp_path):
    _write_token(str(tmp_path), "  \n\t\n")
    with pytest.raises(ControllerUnreachable):
        _loop(str(tmp_path))._default_client()


def test_default_client_reads_token_without_connecting(tmp_path):
    _write_token(str(tmp_path), "local-dummy-token\n")
    client = _loop(str(tmp_path))._default_client()
    assert client.token == "local-dummy-token"
    assert client.base_url == UNROUTABLE
    assert client.timeout_s == SVC.REQUEST_TIMEOUT_S


def test_default_client_strips_surrounding_whitespace(tmp_path):
    _write_token(str(tmp_path), "  spaced-token\t\n")
    client = _loop(str(tmp_path))._default_client()
    assert client.token == "spaced-token"


# -- CancelWatcher lifecycle (no network) --------------------------------------


def test_watcher_starts_uncancelled_and_not_degraded():
    watcher = CancelWatcher(UNROUTABLE, "tok", "task-1")
    assert watcher.cancelled() is False
    assert watcher.degraded is False
    assert watcher._thread is None


def test_watcher_stop_without_start_is_safe():
    watcher = CancelWatcher(UNROUTABLE, "tok", "task-1")
    watcher.stop()  # must not raise
    assert watcher.cancelled() is False


def test_watcher_start_stop_joins_daemon_thread(monkeypatch):
    watcher = CancelWatcher(UNROUTABLE, "tok", "task-1")
    monkeypatch.setattr(CancelWatcher, "_subscribe",
                        lambda self: self._stop.wait(30))
    watcher.start()
    assert watcher._thread is not None
    assert watcher._thread.daemon is True
    watcher.stop()
    assert watcher._thread is None
    assert watcher.cancelled() is False
    assert watcher.degraded is False


def test_watcher_follow_clean_eof_is_not_degraded(monkeypatch):
    watcher = CancelWatcher(UNROUTABLE, "tok", "task-1")
    monkeypatch.setattr(CancelWatcher, "_subscribe", lambda self: None)
    watcher._follow()
    assert watcher.degraded is False
    assert watcher.cancelled() is False


def test_watcher_follow_gives_up_as_degraded(monkeypatch):
    watcher = CancelWatcher(UNROUTABLE, "tok", "task-1")

    def _boom(self):
        raise ControllerError("no controller here")

    monkeypatch.setattr(CancelWatcher, "_subscribe", _boom)
    monkeypatch.setattr(SVC, "SSE_RECONNECTS", 1)
    watcher._follow()
    assert watcher.degraded is True
    assert watcher.cancelled() is False


# -- WorkerLoop._deliver_payload outbox durability ------------------------------


class _FakeClient:
    def __init__(self, behavior="accepted"):
        self.behavior = behavior
        self.seen = []

    def deliver(self, payload):
        self.seen.append(payload)
        if self.behavior == "raise":
            raise ControllerError("controller down")
        return self.behavior


def test_deliver_payload_success_leaves_empty_outbox(tmp_path):
    loop = _loop(str(tmp_path))
    loop._client = _FakeClient("accepted")
    payload = {"dispatch_id": "d-1", "result_id": "r-d-1", "outcome": "success"}
    loop._deliver_payload(payload)
    assert outbox_read_all(str(tmp_path)) == []
    assert loop._client.seen == [payload]


def test_deliver_payload_stays_queued_when_controller_down(tmp_path):
    loop = _loop(str(tmp_path))
    loop._client = _FakeClient("raise")
    payload = {"dispatch_id": "d-2", "result_id": "r-d-2", "outcome": "failure"}
    loop._deliver_payload(payload)  # must not raise: next flush retries
    queued = outbox_read_all(str(tmp_path))
    assert [p for _, p in queued] == [payload]


def test_deliver_payload_stale_answer_is_drained(tmp_path):
    loop = _loop(str(tmp_path))
    loop._client = _FakeClient("stale")
    payload = {"dispatch_id": "d-3", "result_id": "r-d-3", "outcome": "failure"}
    loop._deliver_payload(payload)
    assert outbox_read_all(str(tmp_path)) == []
