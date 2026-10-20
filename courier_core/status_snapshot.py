"""Write a read-only status snapshot for one Courier home (P8).

Read-only, fail-closed inspection of a Courier home directory and its journal
database. Gathers status, events summary, active workers, lockfiles, and configuration
presence, and produces a cryptographically attestable snapshot without acquiring
locks or mutating journal state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from courier_core.events import EventType, canonical_json


@dataclass(frozen=True)
class StatusSnapshot:
    status: str  # "OK", "EMPTY", "NOT_FOUND", "CORRUPT"
    home: str
    captured_at_utc: str
    db_present: bool = False
    journal_events_count: int = 0
    last_event_seq: int | None = None
    last_event_type: str | None = None
    last_event_utc: str | None = None
    tasks_summary: dict[str, int] = field(default_factory=dict)
    active_workers: list[str] = field(default_factory=list)
    locks_present: list[str] = field(default_factory=list)
    config_present: bool = False
    evidence_dir_present: bool = False
    snapshot_sha256: str = ""
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "home": self.home,
            "captured_at_utc": self.captured_at_utc,
            "db_present": self.db_present,
            "journal_events_count": self.journal_events_count,
            "last_event_seq": self.last_event_seq,
            "last_event_type": self.last_event_type,
            "last_event_utc": self.last_event_utc,
            "tasks_summary": self.tasks_summary,
            "active_workers": self.active_workers,
            "locks_present": self.locks_present,
            "config_present": self.config_present,
            "evidence_dir_present": self.evidence_dir_present,
            "snapshot_sha256": self.snapshot_sha256,
            "error_detail": self.error_detail,
        }


def take_status_snapshot(home: Path | str) -> StatusSnapshot:
    """Capture a read-only snapshot of one Courier home directory."""
    home_path = Path(home).resolve()
    now_utc = datetime.now(timezone.utc).isoformat()

    if not home_path.exists() or not home_path.is_dir():
        return StatusSnapshot(
            status="NOT_FOUND",
            home=str(home_path),
            captured_at_utc=now_utc,
            error_detail=f"Home directory not found: {home_path}",
        )

    db_path = home_path / "courier.db"
    config_path = home_path / "config.json"
    evidence_path = home_path / "evidence"

    config_present = config_path.exists() and config_path.is_file()
    evidence_present = evidence_path.exists() and evidence_path.is_dir()

    # Discover lock files in home and home/run
    locks_present: list[str] = []
    for candidate in home_path.glob("*.lock"):
        locks_present.append(candidate.name)
    run_dir = home_path / "run"
    if run_dir.exists() and run_dir.is_dir():
        for candidate in run_dir.glob("*.lock"):
            locks_present.append(f"run/{candidate.name}")

    if not db_path.exists():
        empty_payload = {
            "home": str(home_path),
            "status": "EMPTY",
            "db_present": False,
        }
        digest = hashlib.sha256(canonical_json(empty_payload).encode("utf-8")).hexdigest()
        return StatusSnapshot(
            status="EMPTY",
            home=str(home_path),
            captured_at_utc=now_utc,
            db_present=False,
            locks_present=sorted(locks_present),
            config_present=config_present,
            evidence_dir_present=evidence_present,
            snapshot_sha256=digest,
        )

    # Open database strictly in read-only mode
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only = ON;")
    except sqlite3.Error as exc:
        return StatusSnapshot(
            status="CORRUPT",
            home=str(home_path),
            captured_at_utc=now_utc,
            db_present=True,
            error_detail=f"Failed to open database in read-only mode: {exc}",
        )

    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events';"
        )
        if not cursor.fetchone():
            conn.close()
            empty_payload = {
                "home": str(home_path),
                "status": "EMPTY",
                "db_present": True,
            }
            digest = hashlib.sha256(canonical_json(empty_payload).encode("utf-8")).hexdigest()
            return StatusSnapshot(
                status="EMPTY",
                home=str(home_path),
                captured_at_utc=now_utc,
                db_present=True,
                locks_present=sorted(locks_present),
                config_present=config_present,
                evidence_dir_present=evidence_present,
                snapshot_sha256=digest,
            )

        # Count total events and get last event
        cursor.execute("SELECT COUNT(*) AS total FROM events;")
        events_count = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT seq, type, ts_utc FROM events ORDER BY seq DESC LIMIT 1;"
        )
        last_row = cursor.fetchone()
        last_seq = last_row["seq"] if last_row else None
        last_type = last_row["type"] if last_row else None
        last_utc = last_row["ts_utc"] if last_row else None

        # Task lifecycle summaries
        tasks_summary: dict[str, int] = {
            "total_created": 0,
            "total_claimed": 0,
            "total_started": 0,
            "total_results_ready": 0,
            "total_accepted": 0,
            "total_failed": 0,
        }

        cursor.execute(
            """
            SELECT type, COUNT(*) AS count
            FROM events
            GROUP BY type;
            """
        )
        for row in cursor.fetchall():
            etype = row["type"]
            cnt = row["count"]
            if etype == EventType.TASK_CREATED.value:
                tasks_summary["total_created"] = cnt
            elif etype == EventType.TASK_CLAIMED.value:
                tasks_summary["total_claimed"] = cnt
            elif etype == EventType.TASK_STARTED.value:
                tasks_summary["total_started"] = cnt
            elif etype == EventType.RESULT_READY.value:
                tasks_summary["total_results_ready"] = cnt
            elif etype == EventType.RESULT_ACCEPTED.value:
                tasks_summary["total_accepted"] = cnt
            elif etype in (EventType.TASK_FAILED.value, EventType.TASK_CANCELLED.value):
                tasks_summary["total_failed"] += cnt

        # Identify active distinct workers from recent events
        cursor.execute(
            """
            SELECT DISTINCT worker_id
            FROM events
            WHERE worker_id IS NOT NULL AND worker_id != ''
            ORDER BY worker_id ASC;
            """
        )
        active_workers = [r["worker_id"] for r in cursor.fetchall()]

        conn.close()

    except sqlite3.Error as exc:
        try:
            conn.close()
        except Exception:
            pass
        return StatusSnapshot(
            status="CORRUPT",
            home=str(home_path),
            captured_at_utc=now_utc,
            db_present=True,
            error_detail=f"Database query failed: {exc}",
        )

    # Deterministic SHA-256 digest of the captured snapshot
    snapshot_data = {
        "home": str(home_path),
        "status": "OK",
        "events_count": events_count,
        "last_event_seq": last_seq,
        "last_event_type": last_type,
        "tasks_summary": tasks_summary,
        "active_workers": active_workers,
        "locks_present": sorted(locks_present),
    }
    canonical_repr = canonical_json(snapshot_data)
    digest = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    return StatusSnapshot(
        status="OK",
        home=str(home_path),
        captured_at_utc=now_utc,
        db_present=True,
        journal_events_count=events_count,
        last_event_seq=last_seq,
        last_event_type=last_type,
        last_event_utc=last_utc,
        tasks_summary=tasks_summary,
        active_workers=active_workers,
        locks_present=sorted(locks_present),
        config_present=config_present,
        evidence_dir_present=evidence_present,
        snapshot_sha256=digest,
    )


def write_status_snapshot(
    home: Path | str,
    output_path: Path | str | None = None,
) -> StatusSnapshot:
    """Capture snapshot and write to file."""
    snap = take_status_snapshot(home)
    target = Path(output_path) if output_path else Path(home) / "status_snapshot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snap.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return snap


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for status snapshot."""
    parser = argparse.ArgumentParser(description="Capture read-only status snapshot for one Courier home.")
    parser.add_argument("--home", type=str, required=True, help="Path to Courier home directory")
    parser.add_argument("--output", type=str, help="Destination JSON file path")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output display format")

    args = parser.parse_args(argv)
    snap = take_status_snapshot(args.home)

    if args.output:
        Path(args.output).write_text(json.dumps(snap.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(snap.to_dict(), indent=2, sort_keys=True))
    else:
        print("=== COURIER HOME STATUS SNAPSHOT ===")
        print(f"Home:           {snap.home}")
        print(f"Status:         {snap.status}")
        print(f"Captured UTC:   {snap.captured_at_utc}")
        print(f"Database:       {'Present' if snap.db_present else 'Absent'}")
        print(f"Events Count:   {snap.journal_events_count}")
        print(f"Last Event:     seq={snap.last_event_seq} type={snap.last_event_type} at={snap.last_event_utc}")
        print(f"Tasks Summary:  {snap.tasks_summary}")
        print(f"Active Workers: {', '.join(snap.active_workers) if snap.active_workers else 'None'}")
        print(f"Locks Present:  {', '.join(snap.locks_present) if snap.locks_present else 'None'}")
        print(f"Snapshot SHA:   {snap.snapshot_sha256}")
        if snap.error_detail:
            print(f"Error Detail:   {snap.error_detail}")

    return 0 if snap.status in ("OK", "EMPTY") else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
