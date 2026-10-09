"""P9 hardening: Handler request-plumbing pins for courier_core.serve.

Complementary to the HTTP-integration angle (in-process server on an
ephemeral port). These are direct unit pins for the fail-closed plumbing
helpers with mocked handler state: no server socket, no subprocess, no
network. Tests only; no production code changes.
"""

from __future__ import annotations

import io
import json
import types

import pytest

from courier_core.controller import ApiError
from courier_core import serve


TOKEN = "plumbing-dummy-token-0123456789abcdef"


def make_handler(headers=None, body_bytes=b"", token=TOKEN):
    handler = serve.Handler.__new__(serve.Handler)
    handler.headers = dict(headers or {})
    handler.rfile = io.BytesIO(body_bytes)
    handler.wfile = io.BytesIO()
    handler.server = types.SimpleNamespace(token=token)
    handler.close_connection = False
    sent = {}
    handler._sent = sent

    def send_response(status):
        sent["status"] = status

    def send_header(key, value):
        sent.setdefault("headers", {})[key] = value

    def end_headers():
        sent["ended"] = True

    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = end_headers
    return handler


# ---------------------------------------------------------------- constants


def test_body_bound_constants():
    assert serve.MAX_BODY_BYTES == 1024 * 1024
    assert serve.MAX_DISCARD_BYTES == 4 * serve.MAX_BODY_BYTES
    assert serve.MAX_EVENT_STREAMS == 32
    assert serve.TOKEN_HEADER == "X-Courier-Token"


def test_handler_protocol_constants():
    assert serve.Handler.protocol_version == "HTTP/1.1"
    assert serve.Handler.server_version == "Courier/1"
    assert serve.Handler.timeout == 30
    assert serve.Handler.sys_version == ""


# --------------------------------------------------------------- authorized


def test_authorized_accepts_exact_token():
    handler = make_handler(headers={serve.TOKEN_HEADER: TOKEN})
    assert handler._authorized() is True


def test_authorized_rejects_wrong_token():
    handler = make_handler(headers={serve.TOKEN_HEADER: "wrong-token"})
    assert handler._authorized() is False


def test_authorized_rejects_missing_token():
    handler = make_handler(headers={})
    assert handler._authorized() is False


def test_authorized_rejects_empty_token():
    handler = make_handler(headers={serve.TOKEN_HEADER: ""})
    assert handler._authorized() is False


def test_authorized_rejects_different_length_token():
    handler = make_handler(headers={serve.TOKEN_HEADER: TOKEN + "-extra"})
    assert handler._authorized() is False


# --------------------------------------------------------------- read_json


def test_read_json_missing_length_returns_empty_and_closes():
    handler = make_handler(headers={})
    assert handler._read_json() == {}
    assert handler.close_connection is True


def test_read_json_chunked_is_refused():
    handler = make_handler(headers={"Content-Length": "5", "Transfer-Encoding": "chunked"},
                           body_bytes=b"hello")
    with pytest.raises(ApiError) as exc_info:
        handler._read_json()
    assert exc_info.value.status == 411
    assert exc_info.value.code == "length_required"
    assert handler.close_connection is True


def test_read_json_non_digit_length_is_refused():
    handler = make_handler(headers={"Content-Length": "abc"}, body_bytes=b"{}")
    with pytest.raises(ApiError) as exc_info:
        handler._read_json()
    assert exc_info.value.status == 411
    assert handler.close_connection is True


def test_read_json_zero_length_returns_empty():
    handler = make_handler(headers={"Content-Length": "0"}, body_bytes=b"{}")
    assert handler._read_json() == {}


def test_read_json_oversized_calls_discard_and_raises_413(monkeypatch):
    big = serve.MAX_BODY_BYTES + 1
    handler = make_handler(headers={"Content-Length": str(big)}, body_bytes=b"x" * 10)
    called = []
    original = handler._discard_body

    def spy():
        called.append(True)
        return original()

    monkeypatch.setattr(handler, "_discard_body", spy)
    with pytest.raises(ApiError) as exc_info:
        handler._read_json()
    assert exc_info.value.status == 413
    assert exc_info.value.code == "too_large"
    assert called == [True]


def test_read_json_valid_object():
    payload = {"task_id": "t-1", "n": 2}
    raw = json.dumps(payload).encode("utf-8")
    handler = make_handler(headers={"Content-Length": str(len(raw))}, body_bytes=raw)
    assert handler._read_json() == payload
    assert handler.close_connection is False


def test_read_json_short_read_returns_empty():
    handler = make_handler(headers={"Content-Length": "5"}, body_bytes=b"")
    assert handler._read_json() == {}


def test_read_json_invalid_json_raises_400():
    raw = b"{not json"
    handler = make_handler(headers={"Content-Length": str(len(raw))}, body_bytes=raw)
    with pytest.raises(ApiError) as exc_info:
        handler._read_json()
    assert exc_info.value.status == 400
    assert exc_info.value.code == "invalid_json"


def test_read_json_non_utf8_raises_400():
    raw = b"\xff\xfe\x00bad"
    handler = make_handler(headers={"Content-Length": str(len(raw))}, body_bytes=raw)
    with pytest.raises(ApiError) as exc_info:
        handler._read_json()
    assert exc_info.value.status == 400


# ------------------------------------------------------------- discard_body


def test_discard_body_always_closes_connection():
    handler = make_handler(headers={})
    handler._discard_body()
    assert handler.close_connection is True


def test_discard_body_missing_length_reads_nothing():
    handler = make_handler(headers={}, body_bytes=b"leftover")
    handler._discard_body()
    assert handler.rfile.read() == b"leftover"


def test_discard_body_non_digit_length_reads_nothing():
    handler = make_handler(headers={"Content-Length": "abc"}, body_bytes=b"leftover")
    handler._discard_body()
    assert handler.rfile.read() == b"leftover"


def test_discard_body_oversized_length_reads_nothing():
    huge = serve.MAX_DISCARD_BYTES + 1
    handler = make_handler(headers={"Content-Length": str(huge)}, body_bytes=b"leftover")
    handler._discard_body()
    assert handler.rfile.read() == b"leftover"


def test_discard_body_small_length_drains_body():
    handler = make_handler(headers={"Content-Length": "5"}, body_bytes=b"hello-world")
    handler._discard_body()
    assert handler.rfile.read() == b"-world"


def test_discard_body_short_read_does_not_hang():
    handler = make_handler(headers={"Content-Length": "100"}, body_bytes=b"hi")
    handler._discard_body()
    assert handler.rfile.read() == b""


# ------------------------------------------------------------------- _send


def test_send_none_body_has_zero_length_and_no_write():
    handler = make_handler()
    handler._send(204)
    assert handler._sent["status"] == 204
    assert handler._sent["headers"]["Content-Length"] == "0"
    assert handler._sent["headers"]["Content-Type"] == "application/json"
    assert handler._sent["headers"]["Cache-Control"] == "no-store"
    assert handler._sent["ended"] is True
    assert handler.wfile.getvalue() == b""


def test_send_dict_body_is_compact_json():
    handler = make_handler()
    handler._send(200, {"status": "ok", "n": 1})
    expected = json.dumps({"status": "ok", "n": 1}, separators=(",", ":")).encode("utf-8")
    assert handler._sent["status"] == 200
    assert handler._sent["headers"]["Content-Length"] == str(len(expected))
    assert handler.wfile.getvalue() == expected
