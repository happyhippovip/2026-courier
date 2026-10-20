"""Tests for Cross-Host Network RPC Transport Adapter."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.rpc_transport import (
    RPCClient,
    RPCServer,
    RPCRequest,
    RPCResponse,
    send_rpc_event,
    main,
)


def test_successful_rpc_roundtrip():
    auth_token = "controller-token-secret-2026"
    secret_key = "hmac-signing-key-2026"

    received_events = []

    def handler(request: RPCRequest) -> dict:
        received_events.append(request)
        return {"status": "ACK", "item_id": request.item_id}

    server = RPCServer(auth_token=auth_token, secret_key=secret_key, handler_fn=handler)
    client = RPCClient(server_transport=server, auth_token=auth_token, secret_key=secret_key)

    resp = client.send_event(
        event_type="claim",
        item_id="P27",
        payload={"holder": "windows-titan"},
        idempotency_key="idem-key-001",
    )

    assert resp.status_code == 200
    assert resp.data["status"] == "ACK"
    assert resp.data["item_id"] == "P27"
    assert len(received_events) == 1
    assert received_events[0].item_id == "P27"


def test_invalid_bearer_token_rejected_401():
    server = RPCServer(auth_token="valid-token", secret_key="key")
    client_bad_token = RPCClient(server_transport=server, auth_token="invalid-token", secret_key="key")

    resp = client_bad_token.send_event(event_type="claim", item_id="P27", payload={})
    assert resp.status_code == 401
    assert "UNAUTHORIZED" in resp.error


def test_tampered_signature_rejected_403():
    server = RPCServer(auth_token="token", secret_key="valid-key")
    client_bad_key = RPCClient(server_transport=server, auth_token="token", secret_key="attacker-key")

    resp = client_bad_key.send_event(event_type="claim", item_id="P27", payload={})
    assert resp.status_code == 403
    assert "SIGNATURE_MISMATCH" in resp.error


def test_idempotent_deduplication_returns_cached_response():
    call_count = 0

    def counting_handler(req: RPCRequest) -> dict:
        nonlocal call_count
        call_count += 1
        return {"count": call_count}

    server = RPCServer(auth_token="token", secret_key="key", handler_fn=counting_handler)
    client = RPCClient(server_transport=server, auth_token="token", secret_key="key")

    resp1 = client.send_event("exec", "P27", {}, idempotency_key="same-key")
    assert resp1.status_code == 200
    assert resp1.data["count"] == 1

    # Second transmission with same idempotency key
    resp2 = client.send_event("exec", "P27", {}, idempotency_key="same-key")
    assert resp2.status_code == 200
    assert resp2.data["count"] == 1  # Not executed again!
    assert resp2.is_cached is True
    assert call_count == 1


def test_retry_on_transient_failure():
    attempts = 0

    def flaky_handler(req: RPCRequest) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionResetError("Transient network drop")
        return {"status": "SUCCESS_AFTER_RETRY"}

    server = RPCServer(auth_token="token", secret_key="key", handler_fn=flaky_handler)
    client = RPCClient(server_transport=server, auth_token="token", secret_key="key", max_retries=3)

    resp = client.send_event("sync", "P27", {})
    assert resp.status_code == 200
    assert resp.data["status"] == "SUCCESS_AFTER_RETRY"
    assert attempts == 2


def test_cli_invocation():
    code = main([
        "--action", "mock-ping",
        "--token", "test-token",
        "--key", "test-key",
    ])
    assert code == 0
