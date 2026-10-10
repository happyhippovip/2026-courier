"""SSE stream framing pins for courier_core.serve (lane L4, P9 test hardening).

Tests only; no behavior change. Covers the GET /v1/events byte contract that
the L3 worker's SSE client (courier_worker.service.CancelWatcher) depends on:
status line, required response headers (Content-Type, Cache-Control,
Connection: close, no chunked framing), and the per-event frame layout
``id: <seq>`` / ``event: <type>`` / ``data: <compact-json>`` plus blank line.

All HTTP is loopback-only (127.0.0.1) against a Service bound to port 0.
"""
from __future__ import annotations

import http.client
import json
import re
import socket
import threading
from pathlib import Path

import pytest

from courier_core import serve as S
from courier_core.serve import Service

TASK_BODY = {
    "adapter": "synthetic",
    "params": {},
    "effect_class": "idempotent",
    "max_attempts": 1,
    "lease_ttl_s": 60,
}

FRAME_RE = re.compile(
    r"^id: (\d+)\nevent: ([A-Z_]+)\ndata: (\{.*\})\n\n$", re.DOTALL
)


@pytest.fixture()
def live_service(tmp_path: Path):
    home = tmp_path / "home"
    service = Service(home, 0)
    thread = threading.Thread(target=service.run, name="test-sse-serve", daemon=True)
    thread.start()
    try:
        _wait_healthy(service.port, service.token)
        yield service
    finally:
        service.request_stop()
        service.shutdown()
        thread.join(timeout=15)


def _wait_healthy(port: int, token: str, tries: int = 100) -> None:
    import time
    last = None
    for _ in range(tries):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            try:
                conn.request("GET", "/v1/health",
                             headers={"X-Courier-Token": token})
                resp = conn.getresponse()
                body = resp.read()
                if resp.status == 200 and json.loads(body)["mode"] in ("normal", "degraded_readonly"):
                    return
            finally:
                conn.close()
        except (OSError, ValueError, KeyError) as exc:
            last = exc
        time.sleep(0.1)
    raise AssertionError(f"controller did not become healthy: {last!r}")


def _post_task(port: int, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body or TASK_BODY).encode()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", "/v1/tasks", body=data,
                     headers={"X-Courier-Token": token,
                              "Content-Type": "application/json"})
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8"))
        assert resp.status in (200, 201), payload
        return payload
    finally:
        conn.close()


class StreamReader:
    """Raw-socket SSE reader: headers first, then one frame at a time."""

    def __init__(self, port: int, token: str, after: str = "0"):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=15)
        self.sock.sendall(
            (f"GET /v1/events?after={after} HTTP/1.1\r\n"
             f"Host: 127.0.0.1:{port}\r\n"
             f"X-Courier-Token: {token}\r\n"
             "Accept: text/event-stream\r\n"
             "Connection: close\r\n\r\n").encode())
        self.buf = b""
        self.headers = self._read_headers()

    def _recv(self) -> bytes:
        chunk = self.sock.recv(65536)
        assert chunk, "server closed the stream mid-frame"
        return chunk

    def _read_headers(self) -> str:
        while b"\r\n\r\n" not in self.buf:
            self.buf += self._recv()
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        return head.decode("latin-1")

    def read_frame(self) -> str:
        while self.buf.count(b"\n\n") == 0:
            self.buf += self._recv()
        raw, self.buf = self.buf.split(b"\n\n", 1)
        return (raw + b"\n\n").decode("utf-8")

    def close(self) -> None:
        self.sock.close()


def _header_map(raw: str) -> dict:
    lines = raw.split("\r\n")
    assert lines[0].startswith("HTTP/1.1 200 "), lines[0]
    out: dict = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        out[name.strip().lower()] = value.strip()
    return out


def test_sse_stream_status_and_headers(live_service: Service):
    stream = StreamReader(live_service.port, live_service.token)
    try:
        headers = _header_map(stream.headers)
    finally:
        stream.close()
    assert headers["content-type"] == "text/event-stream"
    assert headers["cache-control"] == "no-store"
    assert headers["connection"] == "close"
    assert "transfer-encoding" not in headers


def _head_seq(port: int, token: str) -> int:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", "/v1/health", headers={"X-Courier-Token": token})
        resp = conn.getresponse()
        assert resp.status == 200
        return int(json.loads(resp.read().decode("utf-8"))["head_seq"])
    finally:
        conn.close()


def test_sse_frame_layout_for_created_task(live_service: Service):
    before = _head_seq(live_service.port, live_service.token)
    created = _post_task(live_service.port, live_service.token)
    stream = StreamReader(live_service.port, live_service.token, after=str(before))
    try:
        frame = stream.read_frame()
    finally:
        stream.close()
    match = FRAME_RE.match(frame)
    assert match is not None, frame
    seq, event_type, data_raw = match.groups()
    assert int(seq) >= 1
    assert event_type == "TASK_CREATED"
    data = json.loads(data_raw)
    assert data["seq"] == int(seq)
    assert data["type"] == "TASK_CREATED"
    assert data["task_id"] == created["task_id"]
    assert "event_id" in data


def test_sse_data_payload_is_compact_json(live_service: Service):
    _post_task(live_service.port, live_service.token)
    stream = StreamReader(live_service.port, live_service.token, after="0")
    try:
        frame = stream.read_frame()
    finally:
        stream.close()
    data_raw = FRAME_RE.match(frame).group(3)
    data = json.loads(data_raw)
    assert data_raw == json.dumps(data, separators=(",", ":"))


def test_sse_resume_after_skips_older_frames(live_service: Service):
    _post_task(live_service.port, live_service.token)
    first = StreamReader(live_service.port, live_service.token, after="0")
    try:
        first_id = int(FRAME_RE.match(first.read_frame()).group(1))
    finally:
        first.close()
    _post_task(live_service.port, live_service.token)
    resumed = StreamReader(live_service.port, live_service.token, after=str(first_id))
    try:
        resumed_id = int(FRAME_RE.match(resumed.read_frame()).group(1))
    finally:
        resumed.close()
    assert resumed_id > first_id


def test_sse_second_stream_served_while_first_held(live_service: Service):
    first = StreamReader(live_service.port, live_service.token)
    try:
        headers = _header_map(first.headers)
        assert headers["content-type"] == "text/event-stream"
        second = StreamReader(live_service.port, live_service.token)
        try:
            second_headers = _header_map(second.headers)
        finally:
            second.close()
        assert second_headers["content-type"] == "text/event-stream"
    finally:
        first.close()


def test_sse_flush_padding_is_a_large_comment():
    assert S.SSE_FLUSH_PADDING.startswith(b":")
    assert S.SSE_FLUSH_PADDING.endswith(b"\n\n")
    assert len(S.SSE_FLUSH_PADDING) > 512
