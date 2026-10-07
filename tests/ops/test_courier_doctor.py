import json
import os
from pathlib import Path
import sqlite3
import zipfile

import pytest

from scripts.courier_doctor import export_diagnostics, get_app_data_dir, load_config

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


def test_diagnostics_redacts_credential_env_vars(tmp_path, monkeypatch):
    """Credential-looking env vars beyond COURIER_API_KEY (verifier /
    provider keys) must not leak into bundled logs. Only the environment
    sweep can catch these: they appear nowhere in config or the token file."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier_key_xyz789")
    monkeypatch.setenv("PROVIDER_SECRET", "provider_secret_456")

    logs_dir = home / "logs"
    logs_dir.mkdir()
    (logs_dir / "worker.log").write_text(
        "using verifier_key_xyz789 and provider_secret_456 today")

    bundle_path = tmp_path / "bundle.zip"
    export_diagnostics(bundle_path)

    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        log_content = zf.read("logs/worker.log").decode("utf-8")
        assert "verifier_key_xyz789" not in log_content
        assert "provider_secret_456" not in log_content
        assert "***REDACTED***" in log_content
        
