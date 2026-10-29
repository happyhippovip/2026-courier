"""P9-service_client_errors: hardening pins for courier_worker.service.

Covers the controller-client error mapping (claim/start/heartbeat/health/
deliver), the spec-failure payload shape, and the heartbeat cancel/stop
mapping. Tests only; no behavior change.

Everything here is offline: ``ControllerClient._call`` is stubbed per test,
and no watcher thread is ever started.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from courier_worker import service as S


def _client(monkeypatch, fn):
    client = S.ControllerClient("http://127.0.0.1:9", "test-token")
    monkeypatch.setattr(client, "_call", fn)
    return client


# -- ControllerClient init ----------------------------------------------------

def test_init_rejects_bad_scheme():
    with pytest.raises(S.ControllerError):
        S.ControllerClient("ftp://example.com/x", "tok")


def test_init_rejects_missing_host():
    with pytest.raises(S.ControllerError):
        S.ControllerClient("http://", "tok")


def test_init_strips_trailing_slash():
    client = S.ControllerClient("http://127.0.0.1:9/", "tok")
    assert client.base_url == "http://127.0.0.1:9"


# -- claim --------------------------------------------------------------------

def test_claim_204_is_none(monkeypatch):
    client = _client(monkeypatch, lambda *a: (204, None))
    assert client.claim("w1") is None


def test_claim_200_dict_is_payload(monkeypatch):
    payload = {"task_id": "t1", "dispatch_id": "d1"}
    client = _client(monkeypatch, lambda *a: (200, payload))
    assert client.claim("w1") == payload


def test_claim_200_nondict_is_none(monkeypatch):
    client = _client(monkeypatch, lambda *a: (200, ["not", "a", "dict"]))
    assert client.claim("w1") is None


def test_claim_404_is_none(monkeypatch):
    client = _client(monkeypatch, lambda *a: (404, None))
    assert client.claim("w1") is None


def test_claim_transport_error_is_none(monkeypatch):
    def boom(*args):
        raise S.ControllerError("down")

    client = _client(monkeypatch, boom)
    assert client.claim("w1") is None


# -- start --------------------------------------------------------------------

def test_start_200_returns_none(monkeypatch):
    client = _client(monkeypatch, lambda *a: (200, {}))
    assert client.start("d1") is None


@pytest.mark.parametrize("status", [404, 409])
def test_start_rejected_dispatch_is_stale(monkeypatch, status):
    client = _client(monkeypatch, lambda *a: (status, None))
    with pytest.raises(S.StaleDispatch):
        client.start("d1")


def test_start_unexpected_status_is_stale(monkeypatch):
    client = _client(monkeypatch, lambda *a: (500, None))
    with pytest.raises(S.StaleDispatch):
        client.start("d1")


def test_start_transport_error_is_stale(monkeypatch):
    def boom(*args):
        raise S.ControllerError("down")

    client = _client(monkeypatch, boom)
    with pytest.raises(S.StaleDispatch):
        client.start("d1")


# -- heartbeat ----------------------------------------------------------------

def test_heartbeat_200_returns_payload(monkeypatch):
    client = _client(monkeypatch, lambda *a: (200, {"cancel": []}))
    assert client.heartbeat("w1", []) == {"cancel": []}


def test_heartbeat_200_empty_body_is_empty_dict(monkeypatch):
    client = _client(monkeypatch, lambda *a: (200, None))
    assert client.heartbeat("w1", []) == {}


def test_heartbeat_non_200_raises(monkeypatch):
    client = _client(monkeypatch, lambda *a: (400, {}))
    with pytest.raises(S.ControllerError):
        client.heartbeat("w1", [])


# -- health -------------------------------------------------------------------

def test_health_true_on_200(monkeypatch):
    client = _client(monkeypatch, lambda *a: (200, {"ok": True}))
    assert client.health() is True


def test_health_false_on_non_200(monkeypatch):
    client = _client(monkeypatch, lambda *a: (404, None))
    assert client.health() is False


def test_health_false_on_transport_error(monkeypatch):
    def boom(*args):
        raise S.ControllerError("down")

    client = _client(monkeypatch, boom)
    assert client.health() is False


# -- deliver ------------------------------------------------------------------

@pytest.mark.parametrize("status", [404, 409])
def test_deliver_rejected_dispatch_is_stale(monkeypatch, status):
    client = _client(monkeypatch, lambda *a: (status, None))
    assert client.deliver({"dispatch_id": "d1"}) == "stale"


@pytest.mark.parametrize("body", [
    {"status": "ACCEPTED_FOR_VERIFY"},
    {"status": "ACK_DUPLICATE"},
    {},
    None,
])
def test_deliver_200_is_accepted(monkeypatch, body):
    client = _client(monkeypatch, lambda *a: (200, body))
    assert client.deliver({"dispatch_id": "d1"}) == "accepted"


def test_deliver_unexpected_status_raises(monkeypatch):
    client = _client(monkeypatch, lambda *a: (400, {}))
    with pytest.raises(S.ControllerError):
        client.deliver({"dispatch_id": "d1"})


def test_deliver_transport_error_propagates(monkeypatch):
    def boom(*args):
        raise S.ControllerError("down")

    client = _client(monkeypatch, boom)
    with pytest.raises(S.ControllerError):
        client.deliver({"dispatch_id": "d1"})


# -- build_spec_failure_payload -----------------------------------------------

def test_spec_failure_payload_shape():
    payload = S.build_spec_failure_payload("d1", "r-d1", "spec-invalid: no task_id")
    assert payload == {
        "dispatch_id": "d1",
        "result_id": "r-d1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "spec-invalid: no task_id",
    }


# -- WorkerLoop._send_heartbeat cancel/stop mapping ----------------------------

def _loop_with_watcher(tmp_path):
    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:9", "w1", 0.2,
                        engine=object())
    watcher = S.CancelWatcher("http://127.0.0.1:9", "tok", "t1")
    loop._watchers["d1"] = watcher
    return loop, watcher


def test_send_heartbeat_cancel_marks_watcher(tmp_path):
    loop, watcher = _loop_with_watcher(tmp_path)
    client = SimpleNamespace(heartbeat=lambda wid, ids: {"cancel": ["d1"]})
    assert loop._send_heartbeat(client, SimpleNamespace(dispatch_id="d1")) is True
    assert watcher.cancelled() is True


def test_send_heartbeat_stop_marks_watcher(tmp_path):
    loop, watcher = _loop_with_watcher(tmp_path)
    client = SimpleNamespace(heartbeat=lambda wid, ids: {"stop": ["d1"]})
    assert loop._send_heartbeat(client, SimpleNamespace(dispatch_id="d1")) is True
    assert watcher.cancelled() is True


def test_send_heartbeat_unrelated_leaves_watcher_clear(tmp_path):
    loop, watcher = _loop_with_watcher(tmp_path)
    client = SimpleNamespace(heartbeat=lambda wid, ids: {"cancel": ["other"]})
    assert loop._send_heartbeat(client, SimpleNamespace(dispatch_id="d1")) is True
    assert watcher.cancelled() is False


def test_send_heartbeat_without_watcher_does_not_crash(tmp_path):
    loop = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:9", "w1", 0.2,
                        engine=object())
    client = SimpleNamespace(heartbeat=lambda wid, ids: {"cancel": ["d1"]})
    assert loop._send_heartbeat(client, SimpleNamespace(dispatch_id="d1")) is True
