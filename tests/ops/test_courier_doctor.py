import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sqlite3
import threading
import zipfile

import pytest

from scripts.courier_doctor import check_server, export_diagnostics, get_app_data_dir, load_config


class _CodedHandler(BaseHTTPRequestHandler):
    code = 200

    def do_GET(self):
        self.send_response(type(self).code)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def http_server():
    servers = []

    def run(code):
        handler = type(f"H{code}", (_CodedHandler,), {"code": code})
        server = HTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        return server.server_address[1]

    yield run
    for server in servers:
        server.shutdown()


def test_server_5xx_is_not_healthy(http_server, monkeypatch):
    port = http_server(500)
    monkeypatch.setenv("COURIER_SERVER", f"http://127.0.0.1:{port}")
    passed, msg = check_server()
    assert passed is False
    assert "500" in msg


def test_server_2xx_and_auth_codes_are_healthy(http_server, monkeypatch):
    for code, expected in ((200, True), (401, True), (404, True)):
        port = http_server(code)
        monkeypatch.setenv("COURIER_SERVER", f"http://127.0.0.1:{port}")
        passed, _ = check_server()
        assert passed is expected

def test_diagnostics_bundle_v1(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    monkeypatch.delenv("PROGRAMDATA", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    
    # Create V1 files
    db_path = home / "courier.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT)")
    conn.execute("INSERT INTO events (type) VALUES ('START')")
    conn.commit()
    conn.close()
    
    run_dir = home / "run"
    run_dir.mkdir()
    token_file = run_dir / "controller.token"
    token_file.write_text("secret_token_12345")
    
    logs_dir = home / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "worker.log"
    log_file.write_text("worker log with secret_token_12345 and other things")
    
    config_file = home / "config.json"
    config_file.write_text(json.dumps({"COURIER_API_KEY": "secret_api_key_abc"}))
    
    # Test debug
    print("CONFIG IS:", load_config())
    print("APP_DATA:", get_app_data_dir())

    bundle_path = tmp_path / "bundle.zip"
    export_diagnostics(bundle_path)
    
    assert bundle_path.exists()
    
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert "courier.db" in names
        assert "config.json" in names
        assert "logs/worker.log" in names
        
        # Check redaction and token exclusion
        assert "run/controller.token" not in names
        assert "controller.token" not in names
        
        log_content = zf.read("logs/worker.log").decode("utf-8")
        assert "secret_token_12345" not in log_content
        
        config_content = zf.read("config.json").decode("utf-8")
        assert "secret_api_key_abc" not in config_content
        
