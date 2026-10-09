import json
import os
from pathlib import Path
import sqlite3
import zipfile

import pytest

from scripts.courier_doctor import (
    check_ledger,
    check_stuck_tasks,
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


def _home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    return home


def test_check_ledger_missing(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    passed, msg = check_ledger()
    assert not passed
    assert "Missing" in msg
    assert str(home / "courier.db") in msg


def test_check_ledger_valid(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    db_path = home / "courier.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT)")
    conn.execute("INSERT INTO events (type) VALUES ('START')")
    conn.commit()
    conn.close()
    passed, msg = check_ledger()
    assert passed
    assert msg == "Ledger exists. 1 events recorded."


def test_check_ledger_unreadable(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    (home / "courier.db").write_text("{corrupt json", encoding="utf-8")
    passed, msg = check_ledger()
    assert not passed
    assert msg.startswith("Error reading ledger:")


def test_check_stuck_tasks_without_ledger(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    passed, msg = check_stuck_tasks()
    assert passed
    assert msg == "No local state to check"


def test_check_stuck_tasks_points_at_status(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    (home / "courier.db").write_bytes(b"")
    passed, msg = check_stuck_tasks()
    assert passed
    assert "courier_core.cli status" in msg
        
