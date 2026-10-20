"""Unit tests for courier_core.status_snapshot (P8)."""

import hashlib
import json
import sqlite3
import pytest
from pathlib import Path

from courier_core.journal import Journal
from courier_core.events import Event, EventType
from courier_core.status_snapshot import (
    take_status_snapshot,
    write_status_snapshot,
    main,
    StatusSnapshot,
)


def test_status_snapshot_home_not_found(tmp_path):
    snap = take_status_snapshot(tmp_path / "nonexistent")
    assert snap.status == "NOT_FOUND"
    assert snap.db_present is False
    assert snap.error_detail is not None


def test_status_snapshot_empty_home(tmp_path):
    empty = tmp_path / "empty_home"
    empty.mkdir()
    snap = take_status_snapshot(empty)
    assert snap.status == "EMPTY"
    assert snap.db_present is False
    assert snap.journal_events_count == 0
    assert len(snap.snapshot_sha256) == 64


def test_status_snapshot_with_journal_events(tmp_path):
    home = tmp_path / "home_with_events"
    home.mkdir()
    db_path = home / "courier.db"

    journal = Journal(db_path).open()
    journal.append(Event(EventType.CONTROLLER_STARTED))
    journal.append(
        Event(
            EventType.TASK_CREATED,
            task_id="t-1",
            payload={
                "adapter": "synthetic",
                "params": {"test": "val"},
                "effect_class": "idempotent",
                "max_attempts": 3,
                "lease_ttl_s": 30,
            },
        )
    )
    journal.append(
        Event(
            EventType.TASK_CLAIMED,
            task_id="t-1",
            attempt=1,
            dispatch_id="d-1",
            worker_id="worker-win-1",
            payload={"ttl_s": 30},
        )
    )
    journal.append(
        Event(
            EventType.TASK_STARTED,
            task_id="t-1",
            attempt=1,
            dispatch_id="d-1",
            worker_id="worker-win-1",
        )
    )
    journal.append(
        Event(
            EventType.RESULT_READY,
            task_id="t-1",
            attempt=1,
            dispatch_id="d-1",
            worker_id="worker-win-1",
            result_id="r-1",
            payload={"outcome": "success", "artifacts": []},
        )
    )
    journal.append(
        Event(
            EventType.RESULT_ACCEPTED,
            task_id="t-1",
            attempt=1,
            dispatch_id="d-1",
            result_id="r-1",
        )
    )
    journal.close()

    snap = take_status_snapshot(home)
    assert snap.status == "OK"
    assert snap.db_present is True
    assert snap.journal_events_count == 6
    assert snap.last_event_type == EventType.RESULT_ACCEPTED.value
    assert snap.last_event_seq == 6
    assert "worker-win-1" in snap.active_workers
    assert snap.tasks_summary["total_created"] == 1
    assert snap.tasks_summary["total_claimed"] == 1
    assert snap.tasks_summary["total_accepted"] == 1
    assert len(snap.snapshot_sha256) == 64


def test_status_snapshot_read_only_never_mutates_db(tmp_path):
    home = tmp_path / "ro_home"
    home.mkdir()
    db_path = home / "courier.db"

    journal = Journal(db_path).open()
    journal.append(Event(EventType.CONTROLLER_STARTED))
    journal.close()

    before_bytes = db_path.read_bytes()
    before_mtime = db_path.stat().st_mtime_ns

    snap = take_status_snapshot(home)
    assert snap.status == "OK"

    after_bytes = db_path.read_bytes()
    after_mtime = db_path.stat().st_mtime_ns

    assert before_bytes == after_bytes
    assert before_mtime == after_mtime


def test_status_snapshot_detects_locks_and_config(tmp_path):
    home = tmp_path / "home_with_meta"
    home.mkdir()
    (home / "config.json").write_text('{"host": "local"}', encoding="utf-8")

    run_dir = home / "run"
    run_dir.mkdir()
    (run_dir / "worker.lock").write_bytes(b"\0")

    snap = take_status_snapshot(home)
    assert snap.config_present is True
    assert any("worker.lock" in l for l in snap.locks_present)


def test_status_snapshot_corrupt_db(tmp_path):
    home = tmp_path / "corrupt_home"
    home.mkdir()
    db_path = home / "courier.db"
    db_path.write_bytes(b"NOT A VALID SQLITE DATABASE 1234567890")

    snap = take_status_snapshot(home)
    assert snap.status == "CORRUPT"
    assert snap.error_detail is not None


def test_write_status_snapshot(tmp_path):
    home = tmp_path / "write_home"
    home.mkdir()
    out_file = home / "status_report.json"

    snap = write_status_snapshot(home, output_path=out_file)
    assert out_file.exists()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["home"] == str(home.resolve())
    assert data["status"] == "EMPTY"
    assert data["snapshot_sha256"] == snap.snapshot_sha256


def test_cli_invocation(tmp_path, capsys):
    home = tmp_path / "cli_home"
    home.mkdir()

    # JSON format
    code = main(["--home", str(home), "--format", "json"])
    assert code == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["status"] == "EMPTY"

    # Text format
    code = main(["--home", str(home), "--format", "text"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "COURIER HOME STATUS SNAPSHOT" in captured
