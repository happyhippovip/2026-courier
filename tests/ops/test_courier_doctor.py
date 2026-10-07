import json
import os
from pathlib import Path
import sqlite3
import zipfile

import pytest

from tests.core.core_builders import Attempt, created

from courier_core.journal import Journal
from scripts.courier_doctor import check_stuck_tasks, export_diagnostics, get_app_data_dir, load_config

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


def test_check_stuck_tasks_no_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    ok, msg = check_stuck_tasks()
    assert ok and "No local state" in msg


def test_check_stuck_tasks_healthy_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    from tests.core.core_builders import golden_path

    with Journal(tmp_path / "courier.db") as journal:
        for event in golden_path("ok-task"):
            journal.append(event)
    ok, msg = check_stuck_tasks()
    assert ok and "No active tasks" in msg


def test_check_stuck_tasks_flags_retry_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    attempt = Attempt("stuck", 1)
    events = [
        created("stuck", effect_class="non_idempotent"),
        attempt.claimed(),
        attempt.started(),
        attempt.lease_expired(),
    ]
    with Journal(tmp_path / "courier.db") as journal:
        for event in events:
            journal.append(event)
    ok, msg = check_stuck_tasks()
    assert not ok and "stuck" in msg and "retry-pending" in msg.lower()


def test_check_stuck_tasks_zero_byte_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    (tmp_path / "courier.db").write_bytes(b"")
    ok, msg = check_stuck_tasks()
    assert ok is False
    assert "journal" in msg.lower() or "integrity" in msg.lower()


def test_check_stuck_tasks_non_database_file(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_HOME", str(tmp_path))
    (tmp_path / "courier.db").write_text("not a sqlite database", encoding="utf-8")
    ok, msg = check_stuck_tasks()
    assert ok is False
    assert "journal" in msg.lower() or "integrity" in msg.lower()

