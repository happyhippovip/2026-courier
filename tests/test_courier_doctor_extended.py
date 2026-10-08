import json
import os
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

from scripts.courier_doctor import (
    get_app_data_dir,
    load_config,
    check_ledger,
    check_server,
    check_stuck_tasks,
    redact_secrets,
    export_diagnostics,
)


def test_get_app_data_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path / "custom_courier"))
    app_dir = get_app_data_dir()
    assert app_dir == tmp_path / "custom_courier"


def test_load_config_missing_vs_present(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    assert load_config() == {}

    cfg = {"COURIER_SERVER": "http://localhost:9090", "TEST_KEY": "secret123"}
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    assert load_config() == cfg


def test_check_ledger_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    ok, msg = check_ledger()
    assert ok is False
    assert "Missing ledger" in msg


def test_check_ledger_present_with_events(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    db_file = tmp_path / "courier.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, event TEXT);")
    conn.execute("INSERT INTO events (seq, event) VALUES (1, 'e1'), (2, 'e2'), (42, 'e42');")
    conn.commit()
    conn.close()

    ok, msg = check_ledger()
    assert ok is True
    assert "42 events recorded" in msg


def test_check_server_success_and_failure(monkeypatch):
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        ok, msg = check_server()
        assert ok is True
        assert "Server responding" in msg

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        ok, msg = check_server()
        assert ok is False
        assert "unreachable" in msg


def test_redact_secrets():
    content = "Connecting with token_secret_12345 and API_KEY_abcdef to server"
    secrets = ["token_secret_12345", "API_KEY_abcdef", "abc"]  # 'abc' is <= 4 chars, ignored
    redacted = redact_secrets(content, secrets)
    assert "token_secret_12345" not in redacted
    assert "API_KEY_abcdef" not in redacted
    assert "***REDACTED***" in redacted


def test_export_diagnostics(tmp_path, monkeypatch):
    app_data = tmp_path / "courier_home"
    app_data.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(app_data))
    monkeypatch.setenv("COURIER_API_KEY", "super_secret_api_key_999")

    # Write db
    (app_data / "courier.db").write_text("sqlite-simulated-content", encoding="utf-8")
    # Write config
    cfg = {"API_KEY": "super_secret_api_key_999", "PORT": 8080}
    (app_data / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    # Write log
    log_dir = app_data / "logs"
    log_dir.mkdir()
    (log_dir / "courier.log").write_text("Worker started with key super_secret_api_key_999", encoding="utf-8")

    out_zip = tmp_path / "diagnostics.zip"
    export_diagnostics(out_zip)
    assert out_zip.exists()

    with zipfile.ZipFile(out_zip, "r") as zf:
        names = zf.namelist()
        assert "courier.db" in names
        assert "config.json" in names
        assert "logs/courier.log" in names

        log_content = zf.read("logs/courier.log").decode("utf-8")
        assert "super_secret_api_key_999" not in log_content
        assert "***REDACTED***" in log_content
