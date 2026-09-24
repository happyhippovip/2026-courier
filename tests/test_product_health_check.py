import json
import os
import sys
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pytest

from scripts.product_health_check import get_api_key, run, main


def test_get_api_key_env(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "env-secret-123")
    assert get_api_key() == "env-secret-123"


def test_get_api_key_file(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with tempfile.TemporaryDirectory() as tmp_dir:
        env_file = os.path.join(tmp_dir, ".env.txt")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("COURIER_API_KEY=file-secret-456\n")

        key = get_api_key(repo_dir=tmp_dir)
        assert key == "file-secret-456"


def test_get_api_key_keyring(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.setattr("keyring.get_password", lambda s, k: "keyring-mock-key" if s == "courier_worker" and k == "courier_api_key" else None)
    with tempfile.TemporaryDirectory() as tmp_dir:
        key = get_api_key(repo_dir=tmp_dir)
        assert key == "keyring-mock-key"


def test_get_api_key_missing(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.setattr("keyring.get_password", lambda s, k: None)
    with tempfile.TemporaryDirectory() as tmp_dir:
        assert get_api_key(repo_dir=tmp_dir) is None


class MockCourierHandler(BaseHTTPRequestHandler):
    status_response = {"goals": {}, "tasks": {}}
    workers_response = {"verifier_01": {"last_heartbeat": 9999999999}}

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.status_response).encode("utf-8"))
        elif self.path == "/workers":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.workers_response).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockCourierHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_health_check_healthy(mock_server, monkeypatch, capsys):
    monkeypatch.setenv("COURIER_API_KEY", "valid-key")
    exit_code = run(server_url=mock_server)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "HEALTHY" in captured.out


def test_health_check_no_credentials(monkeypatch, capsys):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.setattr("keyring.get_password", lambda s, k: None)
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code = run(repo_dir=tmp_dir, server_url="http://127.0.0.1:9")
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "HUMAN_REQUIRED: No credentials found" in captured.out


def test_health_check_server_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("COURIER_API_KEY", "valid-key")
    # Port 1 is not running anything
    exit_code = run(server_url="http://127.0.0.1:1")
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "DEGRADED: Server unreachable" in captured.out
