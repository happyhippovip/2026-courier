"""Offline status-mapping pins for courier_worker.service (P9-service_deliver).

Tests-only hardening: pins how ControllerClient maps HTTP statuses to
return values / exceptions, and how CancelWatcher._dispatch_event maps SSE
payloads to the cancel latch. Every HTTP interaction is faked by
monkeypatching ControllerClient._call, so no test performs network IO.
No behavior change.
"""

import pytest

from courier_worker import service as S


def _client(monkeypatch, fake):
    client = S.ControllerClient("http://127.0.0.1:9", "dummy-token")
    monkeypatch.setattr(client, "_call", fake)
    return client


# -- ControllerClient init ----------------------------------------------------

def test_client_rejects_bad_url():
    with pytest.raises(S.ControllerError):
        S.ControllerClient("not-a-url", "dummy-token")
    with pytest.raises(S.ControllerError):
        S.ControllerClient("ftp://example.invalid/x", "dummy-token")
    with pytest.raises(S.ControllerError):
        S.ControllerClient("http://", "dummy-token")


def test_client_strips_trailing_slash():
    client = S.ControllerClient("http://127.0.0.1:9/", "dummy-token")
    assert client.base_url == "http://127.0.0.1:9"


# -- health -------------------------------------------------------------------

def test_health_true_on_200(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (200, None))
    assert client.health() is True


def test_health_false_on_non_200(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (503, None))
    assert client.health() is False


def test_health_false_on_error(monkeypatch):
    def _boom(*a, **k):
        raise S.ControllerError("down")
    client = _client(monkeypatch, _boom)
    assert client.health() is False


# -- claim --------------------------------------------------------------------

def test_claim_returns_payload_on_200_dict(monkeypatch):
    payload = {"task_id": "t1", "dispatch_id": "d1"}
    client = _client(monkeypatch, lambda *a, **k: (200, dict(payload)))
    assert client.claim("w1") == payload


def test_claim_none_on_204(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (204, None))
    assert client.claim("w1") is None


def test_claim_none_on_error(monkeypatch):
    def _boom(*a, **k):
        raise S.ControllerError("down")
    client = _client(monkeypatch, _boom)
    assert client.claim("w1") is None


def test_claim_none_on_200_non_dict(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (200, ["not", "a", "dict"]))
    assert client.claim("w1") is None


def test_claim_none_on_unexpected_status(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (400, {"task_id": "t"}))
    assert client.claim("w1") is None


# -- start --------------------------------------------------------------------

def test_start_ok_on_200(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (200, None))
    assert client.start("d1") is None


@pytest.mark.parametrize("status", [404, 409, 400, 500])
def test_start_raises_stale_on_reject_status(monkeypatch, status):
    client = _client(monkeypatch, lambda *a, **k: (status, None))
    with pytest.raises(S.StaleDispatch):
        client.start("d1")


def test_start_raises_stale_on_error(monkeypatch):
    def _boom(*a, **k):
        raise S.ControllerError("down")
    client = _client(monkeypatch, _boom)
    with pytest.raises(S.StaleDispatch):
        client.start("d1")


# -- heartbeat ----------------------------------------------------------------

def test_heartbeat_returns_payload(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (200, {"cancel": []}))
    assert client.heartbeat("w1", ["d1"]) == {"cancel": []}


def test_heartbeat_none_payload_becomes_empty(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (200, None))
    assert client.heartbeat("w1", []) == {}


def test_heartbeat_raises_on_non_200(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (400, {}))
    with pytest.raises(S.ControllerError):
        client.heartbeat("w1", [])


# -- deliver ------------------------------------------------------------------

@pytest.mark.parametrize(
    "body",
    [{"status": "ACCEPTED_FOR_VERIFY"}, {"status": "ACK_DUPLICATE"}, {"other": 1}, None],
)
def test_deliver_accepted_on_200(monkeypatch, body):
    client = _client(monkeypatch, lambda *a, **k: (200, body))
    assert client.deliver({"dispatch_id": "d1"}) == "accepted"


@pytest.mark.parametrize("status", [404, 409])
def test_deliver_stale_on_gone(monkeypatch, status):
    client = _client(monkeypatch, lambda *a, **k: (status, None))
    assert client.deliver({"dispatch_id": "d1"}) == "stale"


def test_deliver_raises_on_unexpected_status(monkeypatch):
    client = _client(monkeypatch, lambda *a, **k: (400, {}))
    with pytest.raises(S.ControllerError):
        client.deliver({"dispatch_id": "d1"})


def test_deliver_propagates_call_error(monkeypatch):
    def _boom(*a, **k):
        raise S.ControllerError("down")
    client = _client(monkeypatch, _boom)
    with pytest.raises(S.ControllerError):
        client.deliver({"dispatch_id": "d1"})


# -- CancelWatcher._dispatch_event (pure, no sockets) --------------------------

def _watcher(task_id="t1"):
    return S.CancelWatcher("http://127.0.0.1:9", "dummy-token", task_id, timeout_s=1.0)


@pytest.mark.parametrize("cancel_type", ["TASK_CANCEL_REQUESTED", "TASK_CANCELLED"])
def test_dispatch_event_sets_cancel_on_type(cancel_type):
    watcher = _watcher("t1")
    watcher._dispatch_event([f'{{"type": "{cancel_type}", "task_id": "t1"}}'])
    assert watcher.cancelled() is True


def test_dispatch_event_accepts_event_type_key():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"event_type": "TASK_CANCELLED", "task_id": "t1"}'])
    assert watcher.cancelled() is True


def test_dispatch_event_accepts_inner_payload_shape():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"payload": {"type": "TASK_CANCELLED", "task_id": "t1"}}'])
    assert watcher.cancelled() is True


def test_dispatch_event_ignores_other_task():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"type": "TASK_CANCELLED", "task_id": "t-other"}'])
    assert watcher.cancelled() is False


def test_dispatch_event_ignores_non_cancel_type():
    watcher = _watcher("t1")
    watcher._dispatch_event(['{"type": "TASK_COMPLETED", "task_id": "t1"}'])
    assert watcher.cancelled() is False


def test_dispatch_event_ignores_bad_json_and_shapes():
    watcher = _watcher("t1")
    watcher._dispatch_event(["not json"])
    watcher._dispatch_event(['[1, 2]'])
    watcher._dispatch_event([])
    assert watcher.cancelled() is False
