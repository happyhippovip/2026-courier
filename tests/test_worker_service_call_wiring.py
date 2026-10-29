"""P9-service_call_wiring: wire discipline of ControllerClient._call/_conn.

Offline pins for courier_worker.service: how one controller call is shaped
(path prefix, headers, body encoding) and mapped (status/payload decoding,
5xx and transport failures, connection close discipline). The transport is
a fake connection object, so no network is used.
"""

import http.client
import json
import socket

import pytest

from courier_worker.service import ControllerClient, ControllerError


class _FakeResponse:
    def __init__(self, status, raw):
        self.status = status
        self._raw = raw

    def read(self):
        return self._raw


class _FakeConn:
    """Records request() args, replays one canned response or raises."""

    def __init__(self, status=200, raw=b"{}", exc=None):
        self.calls = []
        self.closed = False
        self._status = status
        self._raw = raw
        self._exc = exc

    def request(self, method, path, body=None, headers=None):
        self.calls.append({
            "method": method,
            "path": path,
            "body": body,
            "headers": dict(headers or {}),
        })
        if self._exc is not None:
            raise self._exc

    def getresponse(self):
        return _FakeResponse(self._status, self._raw)

    def close(self):
        self.closed = True


def _client_with(monkeypatch, base_url="http://127.0.0.1:9", **fake_kw):
    client = ControllerClient(base_url, "dummy-token")
    fake = _FakeConn(**fake_kw)
    monkeypatch.setattr(client, "_conn", lambda: fake)
    return client, fake


def test_conn_http_uses_port_80_by_default():
    client = ControllerClient("http://ctrl.local", "dummy-token")
    conn = client._conn()
    assert isinstance(conn, http.client.HTTPConnection)
    assert conn.host == "ctrl.local"
    assert conn.port == 80
    assert conn.timeout == client.timeout_s


def test_conn_https_uses_port_443_by_default():
    client = ControllerClient("https://ctrl.local", "dummy-token")
    conn = client._conn()
    assert isinstance(conn, http.client.HTTPSConnection)
    assert conn.port == 443


def test_conn_explicit_port_is_respected():
    client = ControllerClient("http://ctrl.local:8080", "dummy-token")
    assert client._conn().port == 8080


def test_call_prefixes_path_with_v1(monkeypatch):
    client, fake = _client_with(monkeypatch)
    client._call("GET", "/health")
    assert fake.calls[0]["method"] == "GET"
    assert fake.calls[0]["path"] == "/v1/health"


def test_call_always_sends_token_and_accept(monkeypatch):
    client, fake = _client_with(monkeypatch)
    client._call("GET", "/health")
    headers = fake.calls[0]["headers"]
    assert headers["X-Courier-Token"] == "dummy-token"
    assert headers["Accept"] == "application/json"


def test_call_sets_content_type_only_with_body(monkeypatch):
    client, fake = _client_with(monkeypatch)
    client._call("GET", "/health")
    assert "Content-Type" not in fake.calls[0]["headers"]
    client._call("POST", "/claim", {"worker_id": "w-1"})
    headers = fake.calls[1]["headers"]
    assert headers["Content-Type"] == "application/json"
    assert json.loads(fake.calls[1]["body"]) == {"worker_id": "w-1"}


def test_call_returns_status_and_parsed_payload(monkeypatch):
    client, _ = _client_with(monkeypatch, raw=b'{"a": 1}')
    assert client._call("GET", "/health") == (200, {"a": 1})


def test_call_empty_body_is_none_payload(monkeypatch):
    client, _ = _client_with(monkeypatch, raw=b"")
    assert client._call("GET", "/health") == (200, None)


def test_call_invalid_json_is_none_payload(monkeypatch):
    client, _ = _client_with(monkeypatch, raw=b"not-json{")
    assert client._call("GET", "/health") == (200, None)


@pytest.mark.parametrize("status", [500, 503])
def test_call_5xx_raises_controller_error(monkeypatch, status):
    client, fake = _client_with(monkeypatch, status=status, raw=b"{}")
    with pytest.raises(ControllerError):
        client._call("GET", "/health")
    assert fake.closed


@pytest.mark.parametrize("exc", [
    OSError("down"),
    socket.timeout("timed out"),
    http.client.HTTPException("broken"),
])
def test_call_transport_error_raises_and_closes(monkeypatch, exc):
    client, fake = _client_with(monkeypatch, exc=exc)
    with pytest.raises(ControllerError):
        client._call("GET", "/health")
    assert fake.closed


def test_call_closes_connection_on_success(monkeypatch):
    client, fake = _client_with(monkeypatch)
    client._call("GET", "/health")
    assert fake.closed
