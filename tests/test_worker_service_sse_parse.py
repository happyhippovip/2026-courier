"""P9 hardening: CancelWatcher ``_subscribe`` wire-parse edges (tests only).

Covers ``courier_worker.service.CancelWatcher._subscribe`` — the raw-socket
SSE response parser — with a fake socket, so no network, no subprocesses,
no waiting on a live stub controller:

- request line carries ``GET /v1/events`` plus the worker token header;
- clean EOF returns normally and always closes the socket;
- non-200 status, chunked encoding, oversized headers, and missing headers
  (deadline) each raise ``ControllerError`` instead of hanging or parsing on;
- headers split across reads are accumulated before parsing;
- a cancel event for our task sets the flag; other types, malformed JSON,
  and trailing data without a blank-line delimiter do not;
- a pre-set stop flag wins over pending stream data;
- ``:`` keep-alive comments and ``id:``/``event:`` lines are ignored.

This sits beside the open ``P9-service_sse_dispatch`` PR, which pins only
``_dispatch_event`` (event-document handling); nothing here touches that
unit. No behavior change.
"""

from __future__ import annotations

import json
import socket

import pytest

from courier_worker.service import CANCEL_TYPES, CancelWatcher, ControllerError

TOKEN = "test-token"
BASE_URL = "http://controller.invalid/"


class _FakeSocket:
    """Canned-byte socket double for ``socket.create_connection``."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = b""
        self.recv_calls = 0
        self.closed = False
        self.timeout = None

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def settimeout(self, timeout) -> None:
        self.timeout = timeout

    def recv(self, _n: int) -> bytes:
        self.recv_calls += 1
        if self._chunks:
            return self._chunks.pop(0)
        raise socket.timeout("timed out")

    def close(self) -> None:
        self.closed = True


def _install(fake: _FakeSocket, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "create_connection", lambda *_args, **_kwargs: fake
    )


def _watcher(timeout_s: float = 5.0) -> CancelWatcher:
    return CancelWatcher(BASE_URL, TOKEN, "t-7", timeout_s=timeout_s)


def _headers(status: bytes = b"HTTP/1.1 200 OK") -> bytes:
    return status + b"\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n"


def _cancel_frame(task_id: str = "t-7") -> bytes:
    doc = json.dumps({"type": "TASK_CANCEL_REQUESTED", "task_id": task_id})
    return b"data: " + doc.encode() + b"\n\n"


# -- request shape ------------------------------------------------------------


def test_request_line_and_token_header(monkeypatch):
    fake = _FakeSocket([_headers(), b""])
    _install(fake, monkeypatch)
    _watcher()._subscribe()
    assert fake.sent.startswith(b"GET /v1/events HTTP/1.1\r\n")
    assert b"X-Courier-Token: test-token\r\n" in fake.sent
    assert b"Accept: text/event-stream\r\n" in fake.sent


def test_clean_eof_returns_and_closes(monkeypatch):
    fake = _FakeSocket([_headers(), b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is False
    assert fake.closed is True


# -- fail-closed parse edges --------------------------------------------------


def test_non_200_status_raises_and_closes(monkeypatch):
    fake = _FakeSocket([_headers(b"HTTP/1.1 503 Service Unavailable")])
    _install(fake, monkeypatch)
    with pytest.raises(ControllerError, match="status 503"):
        _watcher()._subscribe()
    assert fake.closed is True


def test_chunked_stream_rejected(monkeypatch):
    head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
    fake = _FakeSocket([head])
    _install(fake, monkeypatch)
    with pytest.raises(ControllerError, match="chunked"):
        _watcher()._subscribe()
    assert fake.closed is True


def test_oversized_headers_rejected(monkeypatch):
    fake = _FakeSocket([b"x" * 65537])
    _install(fake, monkeypatch)
    with pytest.raises(ControllerError, match="oversized headers"):
        _watcher()._subscribe()
    assert fake.closed is True


def test_missing_headers_hit_deadline(monkeypatch):
    fake = _FakeSocket([])
    _install(fake, monkeypatch)
    with pytest.raises(ControllerError, match="no response headers"):
        _watcher(timeout_s=0.2)._subscribe()
    assert fake.closed is True


def test_split_headers_accumulated(monkeypatch):
    part1 = b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r"
    part2 = b"\nConnection: close\r\n\r\n"
    fake = _FakeSocket([part1, part2, b""])
    _install(fake, monkeypatch)
    assert _watcher()._subscribe() is None
    assert fake.closed is True


# -- event application through the wire ---------------------------------------


def test_cancel_event_sets_cancelled(monkeypatch):
    fake = _FakeSocket([_headers() + _cancel_frame(), b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is True
    assert CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})


def test_non_cancel_event_ignored(monkeypatch):
    doc = json.dumps({"type": "TASK_HEARTBEAT", "task_id": "t-7"})
    fake = _FakeSocket([_headers() + b"data: " + doc.encode() + b"\n\n", b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is False


def test_malformed_event_ignored(monkeypatch):
    fake = _FakeSocket([_headers() + b"data: not json\n\n", b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is False


def test_trailing_undelimited_data_dropped(monkeypatch):
    fake = _FakeSocket([_headers() + _cancel_frame().rstrip(b"\n"), b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is False


def test_stop_takes_priority_over_pending_data(monkeypatch):
    fake = _FakeSocket([_headers() + _cancel_frame(), b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    watcher._stop.set()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is False
    assert fake.recv_calls == 0
    assert fake.closed is True


def test_keepalive_and_meta_lines_ignored(monkeypatch):
    frame = b": keep-alive\nid: 7\nevent: ping\n" + _cancel_frame()
    fake = _FakeSocket([_headers() + frame, b""])
    _install(fake, monkeypatch)
    watcher = _watcher()
    assert watcher._subscribe() is None
    assert watcher.cancelled() is True
