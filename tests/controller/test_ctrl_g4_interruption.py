"""Gate 4 – surface (Explorer/Hub) frozen or crashed while controller and worker run on.

Invariant (plan §9): a broken surface never means lost work.
"""
import socket
import struct
import time

import pytest

from courier_core import serve
from ctrl_helpers import LiveService, task_body
from test_ctrl_service import golden_over_http, journal_seqs, sse_ids


@pytest.fixture
def live(tmp_path):
    service = LiveService(tmp_path / "home")
    yield service
    service.stop()


def _raw_sse(live, rcvbuf=None):
    sock = socket.create_connection(("127.0.0.1", live.service.port), timeout=5)
    if rcvbuf:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    sock.sendall((f"GET /v1/events HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Courier-Token: {live.service.token}\r\n"
                  "Last-Event-ID: 0\r\n\r\n").encode())
    return sock


def _crash(sock):
    """Process death: the OS resets the socket, no orderly close."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    sock.close()


def test_frozen_surface_never_reading_does_not_stall_controller_or_worker(live):
    frozen = _raw_sse(live, rcvbuf=4096)          # an Explorer/Hub that hangs and never reads again
    try:
        time.sleep(0.3)
        start = time.monotonic()
        ids = [live.post("/v1/tasks", task_body()).json()["task_id"] for _ in range(50)]  # fills its buffers
        for task_id in ids:
            assert live.post(f"/v1/tasks/{task_id}/cancel", {}).status_code == 200
        golden_over_http(live)
        assert time.monotonic() - start < 30
        assert live.get("/v1/health").status_code == 200
    finally:
        _crash(frozen)


def test_crashed_surface_loses_no_work_and_reconnect_resumes_exactly(live):
    ui = _raw_sse(live)
    time.sleep(0.3)
    _crash(ui)
    task_id, _ = golden_over_http(live)            # controller/worker carried on without the UI
    seqs = journal_seqs(live.service.home)
    assert sse_ids(live, 0, seqs[-1]) == seqs      # a restarted UI sees the full, exact history
    assert live.get(f"/v1/tasks/{task_id}").json()["status"] == "COMPLETE"


@pytest.mark.xfail(strict=True, reason=(
    "G4 UI crash: an SSE slot of a crashed client is released only when the next write fails, i.e. on "
    "the next event or after SSE_KEEPALIVE_S=15 s. A crash-looping Hub that used all MAX_EVENT_STREAMS "
    "slots leaves an idle controller answering 503 too_many_streams to the restarted Hub for up to 15 s."))
def test_restarted_surface_can_subscribe_right_after_crashed_clients(live):
    clients = [_raw_sse(live) for _ in range(serve.MAX_EVENT_STREAMS)]
    time.sleep(0.5)
    for sock in clients:
        _crash(sock)
    deadline = time.monotonic() + 2.0
    status = None
    while time.monotonic() < deadline:
        with live.session.get(live.base + "/v1/events", headers={"Last-Event-ID": "0"}, stream=True,
                              timeout=(5, 2)) as response:
            status = response.status_code
        if status == 200:
            break
        time.sleep(0.1)
    assert status == 200, f"restarted UI still refused after 2 s: {status}"
