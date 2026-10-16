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


def test_diagnostics_generic_secret_pattern_redaction(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    
    logs_dir = home / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "worker.log"
    log_file.write_text(
        "Logged lines:\n"
        "auth: Bearer sk-ant-api03-abcdef1234567890abcdef1234567890\n"
        "github: ghp_111122223333444455556666777788889999\n"
        "aws: AKIAIOSFODNN7EXAMPLE\n"
    )
    
    bundle_path = tmp_path / "bundle_redacted.zip"
    export_diagnostics(bundle_path)
    
    with zipfile.ZipFile(bundle_path, "r") as zf:
        log_content = zf.read("logs/worker.log").decode("utf-8")
        assert "ghp_111122223333444455556666777788889999" not in log_content
        assert "AKIAIOSFODNN7EXAMPLE" not in log_content
        assert "sk-ant-api03-abcdef1234567890abcdef1234567890" not in log_content
        assert "***REDACTED" in log_content


def test_diagnostics_includes_critical_snapshot_and_receipts(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))

    run_dir = home / "run"
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True)

    snap_file = run_dir / "critical_snapshot_l0.json"
    snap_file.write_text(json.dumps({"snapshot_id": "SNAP-1", "verdict": "SAFE"}), encoding="utf-8")

    rcpt_file = receipts_dir / "RCPT-1.json"
    rcpt_file.write_text(json.dumps({"receipt_id": "RCPT-1", "outcome": "COMPLETED"}), encoding="utf-8")

    health_file = home / "device_health.jsonl"
    health_file.write_text('{"cpu": 10.0}\n', encoding="utf-8")

    bundle_path = tmp_path / "bundle_full.zip"
    export_diagnostics(bundle_path)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert "run/critical_snapshot_l0.json" in names
        assert "run/receipts/RCPT-1.json" in names
        assert "device_health.jsonl" in names

