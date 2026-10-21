"""Item views and controller reads must stay bounded.

A long TASK_PROGRESS history is real journal data. Shipping every event makes
the item and support-export payloads grow without a limit, and nothing in the
view says the rest was left out. A controller that answers with a multi-megabyte
body is fully buffered today, and a 200 with that body is treated as healthy.
"""

import json
import threading
import tracemalloc
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.server import Hub

# A normal task is a handful of events. Two thousand progress lines must not
# all be copied into the item payload.
SHOWN_CAP = 200
PROGRESS_EVENTS = 2000
# Health and decision bodies are small. A megabyte answer must not be retained.
BODY_CAP = 64 * 1024
OVERSIZE = 1024 * 1024
PEAK_BUDGET = 512 * 1024

_CREATED = {
    "adapter": "synthetic",
    "params": {"title": "Carry the parcel"},
    "effect_class": "idempotent",
    "max_attempts": 3,
    "lease_ttl_s": 6,
}


def _hub(home, controller="http://127.0.0.1:9"):
    return Hub(Path(home), controller, actor="desktop:tester", timeout_s=5)


def _running_task(home, progress):
    with Journal(home / "courier.db") as journal:
        journal.append(Event(type=EventType.TASK_CREATED, task_id="t1", payload=dict(_CREATED)))
        journal.append(Event(
            type=EventType.TASK_CLAIMED, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1",
            payload={"ttl_s": 6},
        ))
        journal.append(Event(
            type=EventType.TASK_STARTED, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1",
        ))
        for _ in range(progress):
            journal.append(Event(
                type=EventType.TASK_PROGRESS, task_id="t1", attempt=1, dispatch_id="d1", payload={},
            ))
    return progress + 3


def _token(home):
    run = home / "run"
    run.mkdir(parents=True)
    (run / "controller.token").write_text("test-token", encoding="utf-8")


class _Stub(BaseHTTPRequestHandler):
    body = b"{}"
    status = 200

    def do_GET(self):
        self._reply()

    def do_POST(self):
        self._reply()

    def _reply(self):
        blob = type(self).body
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def log_message(self, fmt, *args):
        return


def _serve(body: bytes, status: int = 200):
    handler = type("Handler", (_Stub,), {"body": body, "status": status})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return server, thread


def _stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(5)


def _peak(fn):
    tracemalloc.start()
    tracemalloc.clear_traces()
    try:
        return fn(), tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_a_short_history_is_shown_in_full(tmp_path):
    home = tmp_path / "home"
    total = _running_task(home, progress=1)
    view = _hub(home).item_view("t1")
    assert view["events_truncated"] is False
    assert view["events_total"] == total
    assert view["events_shown"] == total
    assert len(view["support"]["events"]) == total
    export = _hub(home).support_export("t1")
    assert export["events_truncated"] is False
    assert export["events_total"] == total
    assert len(export["item"]["events"]) == total


def test_a_long_progress_history_is_capped_and_the_omission_is_counted(tmp_path):
    home = tmp_path / "home"
    total = _running_task(home, progress=PROGRESS_EVENTS)
    assert total == PROGRESS_EVENTS + 3
    hub = _hub(home)
    view = hub.item_view("t1")
    shown = view["support"]["events"]
    payload = json.dumps(view).encode("utf-8")
    # Uncapped, 2003 events serialize to about 400KB and the view has no truncation fields.
    assert len(shown) <= SHOWN_CAP
    assert len(payload) < 100_000
    assert view["events_truncated"] is True
    assert view["events_total"] == total
    assert view["events_shown"] == len(shown)
    assert view["events_total"] - view["events_shown"] == total - len(shown)
    assert shown[0]["seq"] < shown[-1]["seq"]
    assert shown[-1]["seq"] == total  # newest event is still present
    assert shown[0]["seq"] == total - len(shown) + 1
    export = hub.support_export("t1")
    assert export["events_truncated"] is True
    assert export["events_total"] == total
    assert export["events_shown"] == len(shown)
    assert len(export["item"]["events"]) == export["events_shown"]
    assert "events_truncated" in json.dumps(export)
    with Journal(home / "courier.db", readonly=True) as journal:
        stored = sum(1 for _ in journal.events(task_id="t1"))
    assert stored == total  # the journal is unchanged; only the view is capped


def test_a_small_controller_body_is_still_a_running_controller(tmp_path):
    home = tmp_path / "home"
    _token(home)
    server, thread = _serve(b'{"mode":"ok","head_seq":4}')
    try:
        status = _hub(home, f"http://127.0.0.1:{server.server_address[1]}").status()
    finally:
        _stop(server, thread)
    assert status["controller"] == "running"
    assert status["head_seq"] == 4


def test_an_oversized_controller_body_is_not_buffered_or_trusted(tmp_path):
    home = tmp_path / "home"
    _token(home)
    blob = b'{"mode":"running","pad":"' + (b"A" * OVERSIZE) + b'"}'
    assert len(blob) > BODY_CAP + 1
    server, thread = _serve(blob, status=200)
    hub = _hub(home, f"http://127.0.0.1:{server.server_address[1]}")
    try:
        status, peak = _peak(hub.status)
    finally:
        _stop(server, thread)
    assert status["controller"] == "unreachable"
    assert peak < PEAK_BUDGET
    assert "A" * 64 not in json.dumps(status)


def test_an_oversized_error_body_is_not_buffered(tmp_path):
    home = tmp_path / "home"
    _token(home)
    blob = b'{"error":"nope","pad":"' + (b"B" * OVERSIZE) + b'"}'
    server, thread = _serve(blob, status=500)
    hub = _hub(home, f"http://127.0.0.1:{server.server_address[1]}")
    measured = {}
    tracemalloc.start()
    tracemalloc.clear_traces()
    try:
        with pytest.raises(ConnectionError) as raised:
            hub._call("GET", "/v1/health")
    finally:
        measured["peak"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        _stop(server, thread)
    assert measured["peak"] < PEAK_BUDGET
    assert "B" * 64 not in str(raised.value)


def test_an_oversized_decision_answer_is_unavailable(tmp_path):
    home = tmp_path / "home"
    _token(home)
    blob = b'{"duplicate":false,"pad":"' + (b"C" * OVERSIZE) + b'"}'
    server, thread = _serve(blob, status=200)
    hub = _hub(home, f"http://127.0.0.1:{server.server_address[1]}")
    try:
        (status, payload), peak = _peak(lambda: hub.decide("t1", {"decision": "cancel", "attempt": 1}))
    finally:
        _stop(server, thread)
    assert status == 503
    assert payload["result"] == "unavailable"
    assert "Nothing was sent" not in payload["message"]
    assert peak < PEAK_BUDGET
    assert "C" * 64 not in json.dumps(payload)
