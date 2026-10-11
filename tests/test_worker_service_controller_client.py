"""Offline pins for courier_worker.service ControllerClient (P9, tests-only).

No production code is changed by this file. Every HTTP interaction is
stubbed -- either a fake connection object behind ``ControllerClient._conn``
or a stubbed ``ControllerClient._call`` -- so no test opens a socket and no
test needs credentials, a controller, or the network. Token values below are
fixed obvious fakes, never real secrets, and are never logged.
"""

import http.client
import json
import socket

import pytest

from courier_worker import service as S


FAKE_TOKEN = "test-token-value"


# -- constructor -----------------------------------------------------------

class TestClientInit:
    def test_rejects_non_http_scheme(self):
        with pytest.raises(S.ControllerError):
            S.ControllerClient("ftp://127.0.0.1:9/x", FAKE_TOKEN)

    def test_rejects_missing_hostname(self):
        with pytest.raises(S.ControllerError):
            S.ControllerClient("http://", FAKE_TOKEN)

    def test_rejects_bare_word(self):
        with pytest.raises(S.ControllerError):
            S.ControllerClient("not-a-url", FAKE_TOKEN)

    def test_strips_trailing_slash(self):
        client = S.ControllerClient("http://127.0.0.1:9/", FAKE_TOKEN)
        assert client.base_url == "http://127.0.0.1:9"

    def test_stores_token_and_default_timeout(self):
        client = S.ControllerClient("http://127.0.0.1:9", FAKE_TOKEN)
        assert client.token == FAKE_TOKEN
        assert client.timeout_s == S.REQUEST_TIMEOUT_S

    def test_custom_timeout_honored(self):
        client = S.ControllerClient("http://127.0.0.1:9", FAKE_TOKEN, timeout_s=1.5)
        assert client.timeout_s == 1.5

    def test_error_hierarchy(self):
        assert issubclass(S.ControllerUnreachable, S.ControllerError)
        assert issubclass(S.StaleDispatch, S.ControllerError)


# -- _conn selection (object construction only; no socket is opened) --------

class TestConnSelection:
    def test_http_uses_http_connection_port_80(self):
        conn = S.ControllerClient("http://127.0.0.1", FAKE_TOKEN)._conn()
        assert isinstance(conn, http.client.HTTPConnection)
        assert conn.port == 80
        conn.close()

    def test_https_uses_https_connection_port_443(self):
        conn = S.ControllerClient("https://127.0.0.1", FAKE_TOKEN)._conn()
        assert isinstance(conn, http.client.HTTPSConnection)
        assert conn.port == 443
        conn.close()

    def test_explicit_port_honored(self):
        conn = S.ControllerClient("http://127.0.0.1:8123", FAKE_TOKEN)._conn()
        assert conn.port == 8123
        conn.close()


# -- _call wire discipline via a fake connection (no network) ---------------

class FakeResponse:
    def __init__(self, status, raw):
        self.status = status
        self._raw = raw

    def read(self):
        return self._raw


class FakeConn:
    """Stands in for http.client.HTTPConnection; records the request."""

    def __init__(self, status=200, raw=b"{}", fail=None):
        self.status = status
        self.raw = raw
        self.fail = fail
        self.closed = False
        self.request_args = None

    def request(self, method, path, body=None, headers=None):
        if self.fail is not None:
            raise self.fail
        self.request_args = (method, path, body, dict(headers or {}))

    def getresponse(self):
        return FakeResponse(self.status, self.raw)

    def close(self):
        self.closed = True


def _client_with(monkeypatch, **fake_kwargs):
    client = S.ControllerClient("http://127.0.0.1:9/", FAKE_TOKEN)
    fake = FakeConn(**fake_kwargs)
    monkeypatch.setattr(client, "_conn", lambda: fake)
    return client, fake


class TestCallWire:
    def test_get_has_no_content_type_but_has_token(self, monkeypatch):
        client, fake = _client_with(monkeypatch)
        status, payload = client._call("GET", "/health")
        assert status == 200
        assert payload == {}
        method, path, body, headers = fake.request_args
        assert (method, path, body) == ("GET", "/v1/health", None)
        assert headers["X-Courier-Token"] == FAKE_TOKEN
        assert headers["Accept"] == "application/json"
        assert "Content-Type" not in headers
        assert fake.closed

    def test_post_body_is_json_with_content_type(self, monkeypatch):
        client, fake = _client_with(monkeypatch, raw=b'{"a": 1}')
        status, payload = client._call("POST", "/claim", {"worker_id": "w-1"})
        assert (status, payload) == (200, {"a": 1})
        _, _, body, headers = fake.request_args
        assert json.loads(body) == {"worker_id": "w-1"}
        assert headers["Content-Type"] == "application/json"

    def test_5xx_is_controller_error(self, monkeypatch):
        client, _ = _client_with(monkeypatch, status=500, raw=b"boom")
        with pytest.raises(S.ControllerError):
            client._call("GET", "/health")

    def test_empty_body_gives_none_payload(self, monkeypatch):
        client, _ = _client_with(monkeypatch, raw=b"")
        assert client._call("GET", "/health") == (200, None)

    def test_invalid_json_gives_none_payload(self, monkeypatch):
        client, _ = _client_with(monkeypatch, raw=b"not json{")
        assert client._call("GET", "/health") == (200, None)

    def test_non_utf8_body_gives_none_payload(self, monkeypatch):
        client, _ = _client_with(monkeypatch, raw=b"\xff\xfe binary")
        assert client._call("GET", "/health") == (200, None)

    def test_oserror_is_controller_error_and_conn_closed(self, monkeypatch):
        client, fake = _client_with(monkeypatch, fail=OSError("down"))
        with pytest.raises(S.ControllerError):
            client._call("GET", "/health")
        assert fake.closed

    def test_socket_timeout_is_controller_error(self, monkeypatch):
        client, _ = _client_with(monkeypatch, fail=socket.timeout("slow"))
        with pytest.raises(S.ControllerError):
            client._call("GET", "/health")

    def test_http_exception_is_controller_error(self, monkeypatch):
        client, _ = _client_with(monkeypatch, fail=http.client.HTTPException("bad"))
        with pytest.raises(S.ControllerError):
            client._call("GET", "/health")


# -- method mapping via a stubbed _call (no network) -------------------------

def _stub_client(monkeypatch, result=None, exc=None):
    client = S.ControllerClient("http://127.0.0.1:9", FAKE_TOKEN)
    calls = []

    def fake_call(method, path, body=None):
        calls.append((method, path, body))
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(client, "_call", fake_call)
    return client, calls


class TestMethodMapping:
    def test_health_true_on_200(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(200, {}))
        assert client.health() is True

    def test_health_false_on_non_200(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(404, None))
        assert client.health() is False

    def test_health_false_on_error(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, exc=S.ControllerError("down"))
        assert client.health() is False

    def test_claim_returns_dict_on_200(self, monkeypatch):
        claim = {"task_id": "t", "dispatch_id": "d"}
        client, calls = _stub_client(monkeypatch, result=(200, claim))
        assert client.claim("w-1") == claim
        # The v1 controller rejects unknown fields: the claim body is exactly this.
        assert calls == [("POST", "/claim", {"worker_id": "w-1"})]

    def test_claim_none_on_204(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(204, None))
        assert client.claim("w-1") is None

    def test_claim_none_on_non_dict_payload(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(200, ["not", "a", "dict"]))
        assert client.claim("w-1") is None

    def test_claim_none_on_error(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, exc=S.ControllerError("down"))
        assert client.claim("w-1") is None

    def test_start_ok_on_200(self, monkeypatch):
        client, calls = _stub_client(monkeypatch, result=(200, {}))
        assert client.start("d-1") is None
        assert calls == [("POST", "/start", {"dispatch_id": "d-1"})]

    @pytest.mark.parametrize("status", [404, 409, 500])
    def test_start_stale_on_rejection(self, monkeypatch, status):
        client, _ = _stub_client(monkeypatch, result=(status, None))
        with pytest.raises(S.StaleDispatch):
            client.start("d-1")

    def test_start_stale_on_error(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, exc=S.ControllerError("down"))
        with pytest.raises(S.StaleDispatch):
            client.start("d-1")

    def test_heartbeat_returns_payload(self, monkeypatch):
        client, calls = _stub_client(monkeypatch, result=(200, {"cancel": []}))
        assert client.heartbeat("w-1", ["d-1"]) == {"cancel": []}
        assert calls == [("POST", "/heartbeat", {"worker_id": "w-1", "dispatch_ids": ["d-1"]})]

    def test_heartbeat_none_payload_becomes_empty(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(200, None))
        assert client.heartbeat("w-1", []) == {}

    def test_heartbeat_raises_on_non_200(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(503, None))
        with pytest.raises(S.ControllerError):
            client.heartbeat("w-1", [])

    @pytest.mark.parametrize("body", [
        {"status": "ACCEPTED_FOR_VERIFY"},
        {"status": "ACK_DUPLICATE"},
        {"status": "SOMETHING_ELSE"},
        None,
    ])
    def test_deliver_accepted_on_200(self, monkeypatch, body):
        client, _ = _stub_client(monkeypatch, result=(200, body))
        assert client.deliver({"dispatch_id": "d"}) == "accepted"

    @pytest.mark.parametrize("status", [404, 409])
    def test_deliver_stale_on_rejection(self, monkeypatch, status):
        client, _ = _stub_client(monkeypatch, result=(status, None))
        assert client.deliver({"dispatch_id": "d"}) == "stale"

    def test_deliver_raises_on_other_status(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, result=(500, None))
        with pytest.raises(S.ControllerError):
            client.deliver({"dispatch_id": "d"})

    def test_deliver_reraises_controller_error(self, monkeypatch):
        client, _ = _stub_client(monkeypatch, exc=S.ControllerError("down"))
        with pytest.raises(S.ControllerError):
            client.deliver({"dispatch_id": "d"})


# -- module constants ---------------------------------------------------------

class TestConstants:
    def test_request_timeout_is_ten_seconds(self):
        assert S.REQUEST_TIMEOUT_S == 10.0

    def test_cancel_types_exact(self):
        assert S.CANCEL_TYPES == frozenset({"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"})
