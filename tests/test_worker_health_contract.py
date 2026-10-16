"""Windows worker health and auth contract tests (ANTIGRAVITY 022).

Covers:
  1. Health with valid identity (200 OK, mode normal -> healthy)
  2. Health without token (401 Unauthorized -> rejected fail-closed)
  3. Wrong worker (worker ID mismatch -> claim refused fail-closed)
  4. Wrong endpoint (404 Not Found -> refused fail-closed)
  5. Version mismatch (incompatible major version or degraded mode -> rejected fail-closed)
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from courier_worker.service import ControllerClient

TOKEN = "valid-secret-token"


class HealthContractStub(BaseHTTPRequestHandler):
    server_version = "HealthContractStub/1"

    def log_message(self, *args):
        pass

    def _json(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        token = self.headers.get("X-Courier-Token", "")
        if self.path == "/v1/health":
            if token != TOKEN:
                self._json(401, {"error": "unauthorized", "message": "missing or invalid token"})
                return
            mode = getattr(self.server, "stub_mode", "normal")
            version = getattr(self.server, "stub_version", "1.0.0.dev0")
            payload = {
                "mode": mode,
                "head_seq": 10,
                "active_leases": 0,
                "build": {
                    "version": version,
                    "build_id": "test-build-1",
                    "source_sha256": "abcdef",
                    "python": "3.12.0",
                },
            }
            if mode != "normal":
                payload["reason"] = "integrity check failed"
            self._json(200, payload)
        else:
            self._json(404, {"error": "not_found", "message": "unknown endpoint"})

    def do_POST(self):
        token = self.headers.get("X-Courier-Token", "")
        if token != TOKEN:
            self._json(401, {"error": "unauthorized", "message": "missing or invalid token"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            body = {}

        if self.path == "/v1/claim":
            worker_id = body.get("worker_id")
            registered_worker = getattr(self.server, "registered_worker", "WIN-WORKER-01")
            if worker_id != registered_worker:
                # Mismatched/unregistered worker rejected fail-closed
                self._json(404, {"error": "unknown_worker", "message": "worker not found"})
                return
            self._json(200, {
                "task_id": "task-test-01",
                "dispatch_id": "dsp-test-01",
                "attempt": 1,
                "ttl_s": 30,
                "spec": {"adapter": "synthetic", "params": {}},
            })
        else:
            self._json(404, {"error": "not_found", "message": "unknown endpoint"})


@pytest.fixture()
def stub_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), HealthContractStub)
    server.stub_mode = "normal"
    server.stub_version = "1.0.0.dev0"
    server.registered_worker = "WIN-WORKER-01"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_health_with_valid_identity(stub_server):
    """1. Health mit gueltiger Identitaet: 200 OK + mode normal -> True."""
    _, base_url = stub_server
    client = ControllerClient(base_url, token=TOKEN)
    assert client.health() is True


def test_health_without_token(stub_server):
    """2. Health ohne Token: 401 Unauthorized -> False (fail-closed)."""
    _, base_url = stub_server
    # Missing token
    client_no_token = ControllerClient(base_url, token="")
    assert client_no_token.health() is False

    # Invalid token
    client_bad_token = ControllerClient(base_url, token="wrong-or-forged-token")
    assert client_bad_token.health() is False


def test_wrong_worker_claim_rejected(stub_server):
    """3. Falscher Worker: Mismatched/unregistered worker_id -> None (fail-closed)."""
    _, base_url = stub_server
    client = ControllerClient(base_url, token=TOKEN)

    # Correct worker claims successfully
    valid_claim = client.claim(worker_id="WIN-WORKER-01")
    assert valid_claim is not None
    assert valid_claim["worker_id" if "worker_id" in valid_claim else "task_id"] == "task-test-01"

    # Wrong worker rejected
    wrong_claim = client.claim(worker_id="FOREIGN-WORKER-99")
    assert wrong_claim is None


def test_wrong_endpoint_rejected(stub_server):
    """4. Falscher Endpoint: 404 Not Found -> False / None (fail-closed)."""
    _, base_url = stub_server
    client = ControllerClient(base_url, token=TOKEN)

    # Call wrong endpoint path via client._call
    status, payload = client._call("GET", "/nonexistent_health_endpoint")
    assert status == 404
    assert payload.get("error") == "not_found"


def test_version_mismatch_and_degraded_rejected(stub_server):
    """5. Versionsabweichung & degraded mode -> False (fail-closed)."""
    server, base_url = stub_server
    client = ControllerClient(base_url, token=TOKEN)

    # Incompatible major version (v2 vs expected v1)
    server.stub_version = "2.0.0"
    server.stub_mode = "normal"
    assert client.health() is False

    # Degraded mode (safe_mode / broken ledger)
    server.stub_version = "1.0.0.dev0"
    server.stub_mode = "degraded_readonly"
    assert client.health() is False

    # Restored to normal v1 -> healthy
    server.stub_mode = "normal"
    assert client.health() is True
