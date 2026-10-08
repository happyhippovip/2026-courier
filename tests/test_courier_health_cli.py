"""Customer health check: deploy/courier-health.sh speaks the canonical route.

Regression: the script used to call a silent fixed-port ``GET /health``
(``curl -s http://127.0.0.1:8080/health``), which the v1 controller never
serves, so a normal person saw empty output and no next action even with
Courier running. It must call ``GET <base>/v1/health`` and stay actionable.
"""

import http.server
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "courier-health.sh"

TOKEN = "health-test-token"


class _Stub(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):  # noqa: N802
        _Stub.seen.append((self.path, self.headers.get("X-Courier-Token")))
        if self.path != "/v1/health":
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("X-Courier-Token") != TOKEN:
            self.send_response(401)
            self.end_headers()
            return
        body = b'{"mode":"normal","head_seq":7}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pragma: no cover - quiet
        pass


def _serve():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _run(base, token=None):
    env = {"PATH": "/usr/bin:/bin", "COURIER_SERVER": base}
    if token is not None:
        env["COURIER_TOKEN"] = token
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, timeout=30, env=env)


def test_health_calls_versioned_endpoint_with_token():
    server = _serve()
    try:
        _Stub.seen.clear()
        result = _run(f"http://127.0.0.1:{server.server_port}", TOKEN)
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 0, result.stderr
    assert _Stub.seen and _Stub.seen[-1][0] == "/v1/health"
    assert "connected" in result.stdout.lower()
    assert TOKEN not in result.stdout


def test_health_unreachable_is_actionable_not_silent():
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    result = _run(f"http://127.0.0.1:{port}", TOKEN)
    assert result.returncode == 1
    assert result.stdout.strip(), "unreachable check must not print empty output"
    assert "isn't reachable" in result.stdout
    assert "Next:" in result.stdout


def test_health_unauthorized_names_token_action():
    server = _serve()
    try:
        result = _run(f"http://127.0.0.1:{server.server_port}", "wrong-token")
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode == 2
    assert "not authorized" in result.stdout
    assert "COURIER_TOKEN" in result.stdout
