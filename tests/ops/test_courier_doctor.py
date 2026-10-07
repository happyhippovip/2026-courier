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

        note = zf.read("courier.db.REDACTION.txt").decode("utf-8")
        assert "redacted copy" in note
        assert "hash chain" in note
        assert "not modified" in note

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


_NOTE_LEAK = "FAKE-LEAK-9999"
_BEARER = "fakecourier.bearer-token-HHHH8888"
_SK_TOKEN = "sk-fakecourierTESTKEY9999abcd"
_GHP_TOKEN = "ghp_fakecourierTOKEN9999abcd"
_ENTROPY_TOKEN = "kR7mQ2xL9pV4nW8sT1bY6cH3"
_VALUE_SECRETS = (_NOTE_LEAK, _BEARER, _SK_TOKEN, _GHP_TOKEN, _ENTROPY_TOKEN)


def test_diagnostics_redacts_secret_hidden_under_harmless_key(tmp_path, monkeypatch):
    """A credential written inside a note must not survive in the bundle.

    Key-name redaction misses {"note": "deploy with api_key=..."}. The value
    itself has to be learned, including bearer tokens, sk-/ghp_ shapes, and
    long high-entropy strings that carry no label.
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
            "note": f"deploy with api_key={_NOTE_LEAK} tonight",
            "message": f"Authorization: Bearer {_BEARER}",
            "description": f"provider {_SK_TOKEN} and {_GHP_TOKEN}",
            "query": _ENTROPY_TOKEN,
            "path": "/tmp/inbox",
        },
        "effect_class": "idempotent",
    }
    db_path = home / "courier.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT, payload TEXT NOT NULL)")
    conn.execute(
        "INSERT INTO events (type, payload) VALUES (?, ?)",
        ("TASK_CREATED", json.dumps(payload)),
    )
    conn.commit()
    conn.close()
    original_db = db_path.read_bytes()

    bundle_path = tmp_path / "bundle.zip"
    export_diagnostics(bundle_path)

    assert db_path.read_bytes() == original_db
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert "courier.db.REDACTION.txt" in names
        redaction = zf.read("courier.db.REDACTION.txt").decode("utf-8")
        assert "redacted copy" in redaction
        assert "hash chain" in redaction
        assert "not modified" in redaction
        for name in names:
            blob = zf.read(name)
            for secret in _VALUE_SECRETS:
                assert secret.encode("utf-8") not in blob, f"{secret} leaked in {name}"
        exported = tmp_path / "exported-note.db"
        exported.write_bytes(zf.read("courier.db"))

    exported_conn = sqlite3.connect(exported)
    try:
        stored = json.loads(exported_conn.execute("SELECT payload FROM events").fetchone()[0])
    finally:
        exported_conn.close()
    assert stored["params"]["path"] == "/tmp/inbox"
    assert "deploy with api_key=" in stored["params"]["note"]
    assert _NOTE_LEAK not in stored["params"]["note"]
    assert "Bearer" in stored["params"]["message"]


def test_diagnostics_omits_logs_when_ledger_harvest_fails(tmp_path, monkeypatch):
    """An unread ledger must not leave its secrets behind in exported logs.

    The string is not a token shape, so pattern redaction of the log would
    not catch it. Fail closed by leaving the log out of the bundle.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("COURIER_HOME", str(home))
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.delenv("COURIER_VERIFIER_API_KEY", raising=False)
    monkeypatch.delenv("PROGRAMDATA", raising=False)

    secret = "unread-ledger-secret-value"
    db_path = home / "courier.db"
    db_path.write_bytes(b"not a sqlite database\n" + secret.encode("utf-8"))

    logs_dir = home / "logs"
    logs_dir.mkdir()
    (logs_dir / "worker.log").write_text(f"worker echoed {secret}\n")

    (home / "config.json").write_text(json.dumps({"log_level": "info"}))

    bundle_path = tmp_path / "bundle.zip"
    export_diagnostics(bundle_path)

    assert db_path.read_bytes().startswith(b"not a sqlite database")
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert "courier.db" not in names
        assert "logs/worker.log" not in names
        assert "config.json" in names
        assert "courier.db.REDACTION.txt" in names
        redaction = zf.read("courier.db.REDACTION.txt").decode("utf-8")
        assert "hash chain" in redaction
        assert "could not be read" in redaction
        assert "Log files were also omitted" in redaction
        for name in names:
            assert secret.encode("utf-8") not in zf.read(name), name
        assert "info" in zf.read("config.json").decode("utf-8")

