import json
import os
from io import BytesIO
from pathlib import Path
import sqlite3
import zipfile

import pytest

import urllib.error
import urllib.request

from scripts.courier_doctor import (
    check_server,
    export_diagnostics,
    get_app_data_dir,
    load_config,
)

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


def test_check_server_requires_controller_token(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    ok, msg = check_server()
    assert ok is False
    assert "controller.token" in msg


def test_check_server_uses_token_and_reports_mode(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text("install-token", encoding="utf-8")
    (home / "config.json").write_text('{"COURIER_CONTROLLER_PORT": 8800}')
    monkeypatch.setenv("COURIER_HOME", str(home))

    captured = {}

    def fake_urlopen(req, timeout=2):
        captured["url"] = req.full_url
        captured["token"] = req.headers.get("X-courier-token") or req.headers.get("X-Courier-Token")
        body = json.dumps({"mode": "normal", "head_seq": 42}).encode("utf-8")

        class Resp:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, msg = check_server()
    assert ok is True
    assert captured["url"] == "http://127.0.0.1:8800/v1/health"
    assert captured["token"] == "install-token"
    assert "head_seq=42" in msg


def test_check_server_degraded_is_not_healthy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text("tok", encoding="utf-8")
    monkeypatch.setenv("COURIER_HOME", str(home))

    def fake_urlopen(req, timeout=2):
        body = json.dumps({"mode": "degraded_readonly", "head_seq": 1}).encode("utf-8")

        class Resp:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, msg = check_server()
    assert ok is False
    assert "degraded_readonly" in msg


def test_check_server_http_401_is_not_healthy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text("tok", encoding="utf-8")
    monkeypatch.setenv("COURIER_HOME", str(home))

    def fake_urlopen(req, timeout=2):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, msg = check_server()
    assert ok is False
    assert "401" in msg


def test_check_server_invalid_health_json(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text("tok", encoding="utf-8")
    monkeypatch.setenv("COURIER_HOME", str(home))

    def fake_urlopen(req, timeout=2):
        body = b"not-json"

        class Resp:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, msg = check_server()
    assert ok is False
    assert "invalid JSON" in msg


def test_check_server_http_500_is_not_healthy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text("tok", encoding="utf-8")
    monkeypatch.setenv("COURIER_HOME", str(home))

    def fake_urlopen(req, timeout=2):
        raise urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {}, BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ok, msg = check_server()
    assert ok is False

