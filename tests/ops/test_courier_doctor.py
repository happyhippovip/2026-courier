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


# Obviously fake. Long enough that redact_secrets will consider them, and
# distinct from anything a developer machine or CI might actually hold.
_DB_TOKEN = "fakecourier-task-token-ZZZZ1111"
_DB_API_KEY = "fakecourier-task-apikey-YYYY2222"
_DB_PASSWORD = "fakecourier-task-password-XXXX3333"
_CONFIG_API_KEY = "fakecourier-config-apikey-AAAA4444"
_CONTROLLER_TOKEN = "fakecourier-controller-token-BBBB5555"
_FAKE_SECRETS = (_DB_TOKEN, _DB_API_KEY, _DB_PASSWORD, _CONFIG_API_KEY, _CONTROLLER_TOKEN)


def test_diagnostics_bundle_redacts_database_secrets(tmp_path, monkeypatch):
    """Task params are stored verbatim. The bundle must not contain them.

    Config and log redaction already strips known secrets from those text
    files. The ledger copy is the hole: events.payload and tasks.params keep
    tokens, API keys and passwords, and the zip currently stores that file raw.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.delenv("COURIER_VERIFIER_API_KEY", raising=False)
    monkeypatch.delenv("PROGRAMDATA", raising=False)

    payload = {
        "adapter": "synthetic",
        "params": {
            "token": _DB_TOKEN,
            "api_key": _DB_API_KEY,
            "password": _DB_PASSWORD,
            "path": "/tmp/inbox",
        },
        "effect_class": "idempotent",
        "note": f"operator pasted {_CONFIG_API_KEY} and {_CONTROLLER_TOKEN}",
    }
    params = {
        "token": _DB_TOKEN,
        "api_key": _DB_API_KEY,
        "password": _DB_PASSWORD,
        "path": "/tmp/inbox",
    }

    db_path = home / "courier.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE events (
            seq INTEGER PRIMARY KEY,
            event_id TEXT NOT NULL,
            type TEXT NOT NULL,
            task_id TEXT,
            payload TEXT NOT NULL
        );
        CREATE TRIGGER events_no_update BEFORE UPDATE ON events
        BEGIN SELECT RAISE(ABORT, 'courier journal is append-only'); END;
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            adapter TEXT NOT NULL,
            params TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO events (event_id, type, task_id, payload) VALUES (?, ?, ?, ?)",
        ("evt-diag-1", "TASK_CREATED", "task-diag-1", json.dumps(payload)),
    )
    conn.execute(
        "INSERT INTO tasks (task_id, status, adapter, params) VALUES (?, ?, ?, ?)",
        ("task-diag-1", "QUEUED", "synthetic", json.dumps(params)),
    )
    conn.commit()
    conn.close()
    original_db = db_path.read_bytes()

    run_dir = home / "run"
    run_dir.mkdir()
    (run_dir / "controller.token").write_text(_CONTROLLER_TOKEN)

    logs_dir = home / "logs"
    logs_dir.mkdir()
    (logs_dir / "worker.log").write_text(
        f"worker started task-diag-1\nconfig key {_CONFIG_API_KEY}\n"
    )

    (home / "config.json").write_text(json.dumps({
        "COURIER_API_KEY": _CONFIG_API_KEY,
        "log_level": "info",
    }))

    bundle_path = tmp_path / "bundle.zip"
    export_diagnostics(bundle_path)

    # The live ledger is evidence. Export must not rewrite it.
    assert db_path.read_bytes() == original_db

    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert "courier.db" in names
        assert "config.json" in names
        assert "logs/worker.log" in names
        assert "run/controller.token" not in names
        assert "controller.token" not in names

        for name in names:
            blob = zf.read(name)
            for secret in _FAKE_SECRETS:
                assert secret.encode("utf-8") not in blob, f"{secret} leaked in {name}"

        log_text = zf.read("logs/worker.log").decode("utf-8")
        assert "worker started task-diag-1" in log_text

        config_text = zf.read("config.json").decode("utf-8")
        assert "log_level" in config_text
        assert "info" in config_text

        exported = tmp_path / "exported.db"
        exported.write_bytes(zf.read("courier.db"))

    exported_conn = sqlite3.connect(exported)
    try:
        row = exported_conn.execute(
            "SELECT type, task_id, payload FROM events WHERE seq = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "TASK_CREATED"
        assert row[1] == "task-diag-1"
        exported_payload = json.loads(row[2])
        assert exported_payload["adapter"] == "synthetic"
        assert exported_payload["params"]["path"] == "/tmp/inbox"
        assert exported_payload["effect_class"] == "idempotent"

        task = exported_conn.execute(
            "SELECT status, adapter, params FROM tasks WHERE task_id = ?",
            ("task-diag-1",),
        ).fetchone()
        assert task is not None
        assert task[0] == "QUEUED"
        assert task[1] == "synthetic"
        assert json.loads(task[2])["path"] == "/tmp/inbox"
    finally:
        exported_conn.close()

