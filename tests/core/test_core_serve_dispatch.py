"""L2 serve dispatch pins: routing, auth wiring, SSE resume validation, 405s.

Tests-only hardening for courier_core.serve.Handler paths that the plumbing
pins (tests/core/test_core_serve_plumbing.py) and the live-endpoint tests
cover at a different level: the method/path routing matrix, Handler-level
auth wiring (discard-then-401), unexpected-error masking (500 without
internals), broken-pipe handling, PUT/DELETE/PATCH 405s, the /v1/shutdown
stop-thread wiring, and /v1/events Last-Event-ID validation including the
stream bound.

No sockets and no network: the Handler is built without a connection and
its transport methods (_send, _discard_body, _pump_events, _read_json) are
stubbed to record calls.
"""

import threading
from types import SimpleNamespace

from courier_core import serve
from courier_core.serve import Handler

TOKEN = "test-token-0123456789abcdef"


def make_handler(path, headers=None, controller=None, token=TOKEN, streams=None, body=None):
    handler = Handler.__new__(Handler)
    handler.path = path
    handler.headers = dict(headers or {})
    handler.close_connection = False
    handler.sent = []
    handler.discarded = 0
    handler.pumped = []

    def _send(status, response_body=None):
        handler.sent.append((status, response_body))

    def _discard():
        handler.discarded += 1
        handler.close_connection = True

    handler._send = _send
    handler._discard_body = _discard
    handler._pump_events = lambda controller_arg, last: handler.pumped.append((controller_arg, last))
    handler._read_json = lambda: body if body is not None else {}
    handler.server = SimpleNamespace(
        controller=controller if controller is not None else SimpleNamespace(),
        token=token,
        streams=streams if streams is not None else threading.BoundedSemaphore(serve.MAX_EVENT_STREAMS),
        stopping=threading.Event(),
        request_stop=lambda: None,
    )
    return handler


def auth_headers(extra=None):
    headers = {"X-Courier-Token": TOKEN}
    if extra:
        headers.update(extra)
    return headers


# -- 405s: method dispatch never reaches auth or routing -----------------------


def test_put_delete_patch_return_405_without_auth():
    for method in ("do_PUT", "do_DELETE", "do_PATCH"):
        handler = make_handler("/v1/health")
        getattr(handler, method)()
        assert handler.sent == [(405, {"error": "method_not_allowed"})]


def test_delete_and_patch_are_aliases_of_put():
    assert Handler.do_DELETE is Handler.do_PUT
    assert Handler.do_PATCH is Handler.do_PUT


# -- auth wiring: discard the body, then 401 ----------------------------------


def test_unauthorized_get_discards_body_then_401():
    handler = make_handler("/v1/health", {"X-Courier-Token": "wrong"})
    handler.do_GET()
    assert handler.discarded == 1
    assert handler.sent == [(401, {"error": "unauthorized", "message": "missing or invalid token"})]


def test_unauthorized_post_discards_body_then_401():
    controller = SimpleNamespace(claim=lambda body: (_ for _ in ()).throw(AssertionError("must not route")))
    handler = make_handler("/v1/claim", {"X-Courier-Token": ""}, controller=controller)
    handler.do_POST()
    assert handler.discarded == 1
    assert handler.sent == [(401, {"error": "unauthorized", "message": "missing or invalid token"})]


# -- routing: unknown paths and wrong-method paths are 404 ---------------------


def test_unknown_get_path_is_404():
    handler = make_handler("/v1/nope", auth_headers())
    handler.do_GET()
    assert handler.sent == [(404, {"error": "not_found", "message": "not_found"})]


def test_unknown_post_path_is_404():
    handler = make_handler("/v1/nope", auth_headers(), body={})
    handler.do_POST()
    assert handler.sent == [(404, {"error": "not_found", "message": "not_found"})]


def test_get_on_tasks_collection_is_404():
    handler = make_handler("/v1/tasks", auth_headers())
    handler.do_GET()
    assert handler.sent == [(404, {"error": "not_found", "message": "not_found"})]


def test_query_string_is_ignored_for_routing():
    controller = SimpleNamespace(health=lambda: {"mode": "NORMAL"})
    handler = make_handler("/v1/health?probe=1", auth_headers(), controller=controller)
    handler.do_GET()
    assert handler.sent == [(200, {"mode": "NORMAL"})]


def test_task_id_outside_charset_is_404():
    controller = SimpleNamespace()
    handler = make_handler("/v1/tasks/bad!id", auth_headers(), controller=controller)
    handler.do_GET()
    assert handler.sent == [(404, {"error": "not_found", "message": "not_found"})]


# -- routing: delegation carries the path id and the parsed body ----------------


def test_task_view_cancel_resolve_delegation():
    calls = []
    controller = SimpleNamespace(
        task_view=lambda task_id: calls.append(("task_view", task_id)) or {"task_id": task_id},
        cancel=lambda task_id, body: calls.append(("cancel", task_id, body)) or {"cancelled": True},
        resolve=lambda task_id, body: calls.append(("resolve", task_id, body)) or {"resolved": True},
    )
    handler = make_handler("/v1/tasks/t-1", auth_headers(), controller=controller)
    handler.do_GET()
    assert handler.sent == [(200, {"task_id": "t-1"})]

    handler = make_handler("/v1/tasks/t-1/cancel", auth_headers(), controller=controller,
                           body={"actor": "op", "reason": "r"})
    handler.do_POST()
    assert handler.sent == [(200, {"cancelled": True})]

    handler = make_handler("/v1/tasks/t-1/resolve", auth_headers(), controller=controller,
                           body={"decision": "cancel", "actor": "op", "attempt": 1, "reason": "r"})
    handler.do_POST()
    assert handler.sent == [(200, {"resolved": True})]

    assert calls == [
        ("task_view", "t-1"),
        ("cancel", "t-1", {"actor": "op", "reason": "r"}),
        ("resolve", "t-1", {"decision": "cancel", "actor": "op", "attempt": 1, "reason": "r"}),
    ]


def test_claim_none_maps_to_204_and_lease_maps_to_200():
    controller = SimpleNamespace(claim=lambda body: None)
    handler = make_handler("/v1/claim", auth_headers(), controller=controller,
                           body={"worker_id": "w1", "resource_state": "NORMAL"})
    handler.do_POST()
    assert handler.sent == [(204, None)]

    lease = {"dispatch_id": "d1", "task_id": "t1"}
    controller = SimpleNamespace(claim=lambda body: lease)
    handler = make_handler("/v1/claim", auth_headers(), controller=controller,
                           body={"worker_id": "w1", "resource_state": "NORMAL"})
    handler.do_POST()
    assert handler.sent == [(200, lease)]


# -- errors: masked 500s, broken pipes, shutdown wiring -------------------------


def test_unexpected_controller_error_is_masked_as_500(monkeypatch):
    logged = []
    monkeypatch.setattr(serve, "log", SimpleNamespace(exception=lambda *a, **k: logged.append(a)))

    def _boom():
        raise RuntimeError("secret internals")

    controller = SimpleNamespace(health=_boom)
    handler = make_handler("/v1/health", auth_headers(), controller=controller)
    handler.do_GET()
    assert handler.sent == [(500, {"error": "internal", "message": "internal error; see controller log"})]
    assert handler.close_connection is False
    assert logged, "the masked error must still reach the controller log"


def test_broken_pipe_closes_without_response():
    for error in (BrokenPipeError("x"), ConnectionResetError("x")):
        def _boom(err=error):
            raise err

        controller = SimpleNamespace(health=_boom)
        handler = make_handler("/v1/health", auth_headers(), controller=controller)
        handler.do_GET()
        assert handler.sent == []
        assert handler.close_connection is True


def test_shutdown_sends_stopping_and_stops_server():
    stopped = threading.Event()

    def _request_stop():
        stopped.set()

    controller = SimpleNamespace()
    handler = make_handler("/v1/shutdown", auth_headers(), controller=controller, body={})
    handler.server.request_stop = _request_stop
    handler.do_POST()
    assert handler.sent == [(200, {"status": "STOPPING"})]
    assert handler.close_connection is True
    assert stopped.wait(timeout=5), "shutdown must trigger request_stop on a background thread"


# -- /v1/events: Last-Event-ID validation (no pumping on rejects) ----------------


def test_events_default_resume_is_zero_and_releases_slot():
    streams = threading.BoundedSemaphore(serve.MAX_EVENT_STREAMS)
    for _ in range(serve.MAX_EVENT_STREAMS - 1):
        assert streams.acquire(blocking=False)
    controller = SimpleNamespace()
    handler = make_handler("/v1/events", auth_headers(), controller=controller, streams=streams)
    handler.do_GET()
    assert handler.sent == []
    assert handler.pumped == [(controller, 0)]
    # The pump slot was released: the last free slot is acquirable again.
    assert streams.acquire(blocking=False)
    for _ in range(serve.MAX_EVENT_STREAMS):
        streams.release()


def test_events_header_resume_value_is_used():
    controller = SimpleNamespace()
    handler = make_handler("/v1/events", auth_headers({"Last-Event-ID": "7"}), controller=controller)
    handler.do_GET()
    assert handler.sent == []
    assert handler.pumped == [(controller, 7)]


def test_events_header_whitespace_is_stripped():
    controller = SimpleNamespace()
    handler = make_handler("/v1/events", auth_headers({"Last-Event-ID": "  12 "}), controller=controller)
    handler.do_GET()
    assert handler.pumped == [(controller, 12)]


def test_events_bad_header_is_400():
    handler = make_handler("/v1/events", auth_headers({"Last-Event-ID": "abc"}))
    handler.do_GET()
    assert handler.sent == [(400, {"error": "invalid_request",
                                   "message": "Last-Event-ID must be a journal seq"})]
    assert handler.pumped == []


def test_events_bad_query_after_is_400():
    handler = make_handler("/v1/events?after=xyz", auth_headers())
    handler.do_GET()
    assert handler.sent == [(400, {"error": "invalid_request",
                                   "message": "Last-Event-ID must be a journal seq"})]
    assert handler.pumped == []


def test_events_blank_header_falls_back_to_query():
    controller = SimpleNamespace()
    handler = make_handler("/v1/events?after=9", auth_headers({"Last-Event-ID": ""}),
                           controller=controller)
    handler.do_GET()
    assert handler.sent == []
    assert handler.pumped == [(controller, 9)]


def test_events_header_wins_over_query():
    controller = SimpleNamespace()
    handler = make_handler("/v1/events?after=xyz", auth_headers({"Last-Event-ID": "7"}),
                           controller=controller)
    handler.do_GET()
    assert handler.sent == []
    assert handler.pumped == [(controller, 7)]


def test_events_bad_header_wins_over_good_query():
    handler = make_handler("/v1/events?after=9", auth_headers({"Last-Event-ID": "abc"}))
    handler.do_GET()
    assert handler.sent == [(400, {"error": "invalid_request",
                                   "message": "Last-Event-ID must be a journal seq"})]
    assert handler.pumped == []


def test_events_503_when_streams_exhausted():
    streams = threading.BoundedSemaphore(serve.MAX_EVENT_STREAMS)
    held = 0
    try:
        for _ in range(serve.MAX_EVENT_STREAMS):
            assert streams.acquire(blocking=False)
            held += 1
        handler = make_handler("/v1/events", auth_headers({"Last-Event-ID": "3"}), streams=streams)
        handler.do_GET()
        assert handler.sent == [(503, {"error": "too_many_streams",
                                       "message": f"at most {serve.MAX_EVENT_STREAMS} event streams"})]
        assert handler.pumped == []
    finally:
        for _ in range(held):
            streams.release()
