from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from courier_core.receipt_projector import project_receipts, ReceiptProjectionReport


def test_project_receipts_home_not_found(tmp_path: Path):
    nonexistent = tmp_path / "nowhere"
    report = project_receipts(nonexistent)
    assert isinstance(report, ReceiptProjectionReport)
    assert report.valid is False
    assert len(report.violations) > 0


def test_project_receipts_empty_home(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    report = project_receipts(home)
    assert report.valid is True
    assert report.total_receipts == 0
    assert len(report.receipts) == 0


def test_project_receipts_from_journal_jsonl(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    journal = home / "journal.jsonl"
    events = [
        {"type": "TASK_ACCEPTED", "task_id": "t-1", "dispatch_id": "d-1", "worker_id": "w-1", "attempt": 1, "at": "2026-10-18T10:00:00Z"},
        {"type": "TASK_STARTED", "task_id": "t-1", "dispatch_id": "d-1", "worker_id": "w-1", "attempt": 1, "at": "2026-10-18T10:00:01Z"},
        {
            "type": "FINAL_ACCEPTED",
            "task_id": "t-1",
            "dispatch_id": "d-1",
            "worker_id": "w-1",
            "attempt": 1,
            "outcome": "success",
            "returncode": 0,
            "duration_s": 2.5,
            "artifacts": [{"name": "out.txt", "sha256": "abc123"}],
            "at": "2026-10-18T10:00:04Z",
        },
    ]
    with open(journal, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    report = project_receipts(home)
    assert report.valid is True
    assert report.total_receipts == 1
    assert report.success_count == 1
    r = report.receipts[0]
    assert r.task_id == "t-1"
    assert r.dispatch_id == "d-1"
    assert r.worker_id == "w-1"
    assert r.returncode == 0
    assert r.duration_s == 2.5
    assert r.artifact_count == 1
    assert len(r.proof_digest) == 64


def test_project_receipts_detects_evidence_missing_violation(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    journal = home / "journal.jsonl"
    # Success without artifacts violates evidence-before-done
    event = {
        "type": "FINAL_ACCEPTED",
        "task_id": "t-bad",
        "dispatch_id": "d-bad",
        "worker_id": "w-1",
        "attempt": 1,
        "outcome": "success",
        "returncode": 0,
        "duration_s": 1.0,
        "artifacts": [],
        "at": "2026-10-18T10:00:00Z",
    }
    journal.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = project_receipts(home)
    assert report.valid is False
    assert report.success_count == 0
    assert report.failed_count == 1
    assert any("evidence_missing" in v for v in report.violations)


def test_project_receipts_from_events_sqlite(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    db_path = home / "events.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE events (event_id TEXT, event_type TEXT, payload TEXT, at TEXT)")
    payload = json.dumps({
        "task_id": "t-sql",
        "dispatch_id": "d-sql",
        "worker_id": "w-sql",
        "attempt": 1,
        "outcome": "success",
        "returncode": 0,
        "duration_s": 1.2,
        "artifacts": ["sha256:1111"],
    })
    conn.execute("INSERT INTO events VALUES ('e-1', 'TASK_RESULT_DELIVERED', ?, '2026-10-18T12:00:00Z')", (payload,))
    conn.commit()
    conn.close()

    report = project_receipts(home)
    assert report.valid is True
    assert report.total_receipts == 1
    assert report.receipts[0].task_id == "t-sql"


def test_project_receipts_never_mutates_database(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    db_path = home / "events.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE events (id TEXT, event_type TEXT, payload TEXT, at TEXT)")
    conn.commit()
    conn.close()

    mtime_before = db_path.stat().st_mtime
    report = project_receipts(home)
    assert report.valid is True
    mtime_after = db_path.stat().st_mtime
    assert mtime_before == mtime_after


def test_cli_invocation_happy_and_filter(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    journal = home / "journal.jsonl"
    ev1 = {
        "type": "FINAL_ACCEPTED",
        "task_id": "t-A",
        "dispatch_id": "d-A",
        "worker_id": "w-1",
        "attempt": 1,
        "outcome": "success",
        "returncode": 0,
        "duration_s": 0.5,
        "artifacts": ["artA"],
        "at": "2026-10-18T11:00:00Z",
    }
    ev2 = {
        "type": "FINAL_ACCEPTED",
        "task_id": "t-B",
        "dispatch_id": "d-B",
        "worker_id": "w-2",
        "attempt": 1,
        "outcome": "failed",
        "returncode": 1,
        "duration_s": 0.3,
        "artifacts": [],
        "at": "2026-10-18T11:01:00Z",
    }
    journal.write_text(json.dumps(ev1) + "\n" + json.dumps(ev2) + "\n", encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "courier_core.receipt_projector", str(home), "--task-id", "t-A"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["valid"] is True
    assert data["total_receipts"] == 1
    assert data["receipts"][0]["task_id"] == "t-A"
