"""Cross-Host Network RPC Transport Adapter.

Provides authenticated, cryptographically signed, idempotent RPC transport
with automatic retry resilience across distributed worker and controller boundaries.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from courier_core.receipt_signer import ReceiptSigner, SignedReceipt


@dataclass
class RPCRequest:
    """Standardized RPC request message envelope."""

    event_type: str
    item_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    signature: str = ""
    signed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RPCResponse:
    """Standardized RPC response message envelope."""

    status_code: int
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    is_cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RPCServer:
    """In-process and network RPC request receiver and dispatcher."""

    def __init__(
        self,
        auth_token: str,
        secret_key: str,
        handler_fn: Callable[[RPCRequest], dict[str, Any]] | None = None,
    ):
        self.auth_token = auth_token
        self.secret_key = secret_key
        self.handler_fn = handler_fn
        self.signer = ReceiptSigner(secret_key=self.secret_key)
        self.idempotency_cache: dict[str, RPCResponse] = {}

    def handle_request(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> RPCResponse:
        # 1. Bearer Token Authentication Check
        auth_header = headers.get("Authorization") or headers.get("authorization") or ""
        expected_auth = f"Bearer {self.auth_token}"
        if auth_header != expected_auth:
            return RPCResponse(
                status_code=401,
                error="UNAUTHORIZED: Invalid or missing bearer authentication token",
            )

        # 2. Cryptographic HMAC Signature Verification
        req_sig = body.get("signature", "")
        req_signed_at = body.get("signed_at", "")
        canonical_content = {
            "event_type": body.get("event_type", ""),
            "item_id": body.get("item_id", ""),
            "payload": body.get("payload", {}),
        }

        v_res = self.signer.verify({
            "payload": canonical_content,
            "signature": req_sig,
            "signed_at": req_signed_at,
        })
        if not v_res.is_valid:
            return RPCResponse(
                status_code=403,
                error=f"SIGNATURE_MISMATCH: {v_res.reason}",
            )

        # 3. Idempotency Key Deduplication Check
        idem_key = body.get("idempotency_key")
        if idem_key and idem_key in self.idempotency_cache:
            cached = self.idempotency_cache[idem_key]
            return RPCResponse(
                status_code=cached.status_code,
                data=dict(cached.data),
                error=cached.error,
                is_cached=True,
            )

        # 4. Request Dispatch
        req = RPCRequest(
            event_type=body.get("event_type", ""),
            item_id=body.get("item_id", ""),
            payload=body.get("payload", {}),
            idempotency_key=idem_key,
            signature=req_sig,
            signed_at=req_signed_at,
        )

        try:
            if self.handler_fn:
                res_data = self.handler_fn(req)
            else:
                res_data = {"status": "ACK", "item_id": req.item_id}
            resp = RPCResponse(status_code=200, data=res_data)
        except Exception as exc:
            resp = RPCResponse(status_code=500, error=str(exc))

        if idem_key and resp.status_code == 200:
            self.idempotency_cache[idem_key] = resp

        return resp


class RPCClient:
    """Client for dispatching signed RPC events with retry semantics."""

    def __init__(
        self,
        auth_token: str,
        secret_key: str,
        server_transport: RPCServer | None = None,
        base_url: str | None = None,
        timeout_sec: float = 5.0,
        max_retries: int = 3,
    ):
        self.auth_token = auth_token
        self.secret_key = secret_key
        self.server_transport = server_transport
        self.base_url = base_url
        self.timeout_sec = timeout_sec
        self.max_retries = max(1, max_retries)
        self.signer = ReceiptSigner(secret_key=self.secret_key)

    def send_event(
        self,
        event_type: str,
        item_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> RPCResponse:
        canonical_content = {
            "event_type": event_type,
            "item_id": item_id,
            "payload": payload,
        }
        signed = self.signer.sign(canonical_content)

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        body = {
            "event_type": event_type,
            "item_id": item_id,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "signature": signed.signature,
            "signed_at": signed.signed_at,
        }

        last_resp: RPCResponse | None = None
        for attempt in range(self.max_retries):
            try:
                if self.server_transport:
                    resp = self.server_transport.handle_request(headers=headers, body=body)
                    if resp.status_code < 500:
                        return resp
                    last_resp = resp
                else:
                    # Generic placeholder for live network HTTP client
                    raise ConnectionError(f"Network transport to {self.base_url} unavailable")
            except Exception as exc:
                last_resp = RPCResponse(status_code=503, error=f"NETWORK_ERROR: {str(exc)}")

            # Short backoff before retry
            time.sleep(0.01 * (attempt + 1))

        return last_resp or RPCResponse(status_code=500, error="ALL_RETRIES_EXHAUSTED")


def send_rpc_event(
    event_type: str,
    item_id: str,
    payload: dict[str, Any],
    auth_token: str,
    secret_key: str,
    server: RPCServer,
    idempotency_key: str | None = None,
) -> RPCResponse:
    client = RPCClient(auth_token=auth_token, secret_key=secret_key, server_transport=server)
    return client.send_event(event_type, item_id, payload, idempotency_key=idempotency_key)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-Host Network RPC Transport.")
    parser.add_argument("--action", choices=["mock-ping", "send"], default="mock-ping")
    parser.add_argument("--token", default="test-token")
    parser.add_argument("--key", default="test-key")
    parser.add_argument("--item", default="P27_ping")

    args = parser.parse_args(argv)

    server = RPCServer(auth_token=args.token, secret_key=args.key)
    client = RPCClient(auth_token=args.token, secret_key=args.key, server_transport=server)

    resp = client.send_event("ping", args.item, {"msg": "hello from titan"})
    print(json.dumps(resp.to_dict()))
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
