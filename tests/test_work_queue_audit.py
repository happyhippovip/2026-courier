from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from courier_core.work_queue_audit import (
    WorkQueueAuditor,
    audit_work_queue_ledger,
    main,
)

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_ledger(path: Path, events: list[dict]) -> None:
    lines = [json.dumps(e) + "\n" for e in events]
    path.write_text("".join(lines), encoding="utf-8")


def test_empty_or_nonexistent_ledger(tmp_path):
    report = audit_work_queue_ledger(tmp_path / "nonexistent.jsonl")
    assert report.valid is True
    assert report.events_count == 0
    assert len(report.violations) == 0

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    report = audit_work_queue_ledger(empty)
    assert report.valid is True
    assert report.events_count == 0


def test_clean_lifecycle_and_idempotency(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    events = [
        {
            "type": "CLAIM",
            "item_id": "P2",
            "holder": "window-a",
            "host": "local-win",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Idempotent replay of same claim
        {
            "type": "CLAIM",
            "item_id": "P2",
            "holder": "window-a",
            "host": "local-win",
            "created_at": _stamp(NOW + timedelta(seconds=5)),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Renewal
        {
            "type": "RENEW",
            "item_id": "P2",
            "holder": "window-a",
            "created_at": _stamp(NOW + timedelta(minutes=5)),
            "expires_at": _stamp(NOW + timedelta(minutes=20)),
        },
        # Release
        {
            "type": "RELEASE",
            "item_id": "P2",
            "holder": "window-a",
            "created_at": _stamp(NOW + timedelta(minutes=8)),
            "result": "draft PR #287",
        },
        # Idempotent replay of release
        {
            "type": "RELEASE",
            "item_id": "P2",
            "holder": "window-a",
            "created_at": _stamp(NOW + timedelta(minutes=9)),
            "result": "draft PR #287",
        },
    ]
    _write_ledger(ledger, events)
    report = audit_work_queue_ledger(ledger)
    assert report.valid is True
    assert report.events_count == 5
    assert len(report.violations) == 0
    assert report.completed_count == 1
    assert report.active_leases_count == 0
    assert report.items["P2"]["status"] == "DONE"


def test_duplicate_claim_and_time_travel_violations(tmp_path):
    ledger = tmp_path / "bad_claims.jsonl"
    events = [
        {
            "type": "CLAIM",
            "item_id": "P3",
            "holder": "holder-1",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Time travel: created_at earlier than prior event
        {
            "type": "CLAIM",
            "item_id": "P4",
            "holder": "holder-2",
            "host": "host-2",
            "created_at": _stamp(NOW - timedelta(minutes=5)),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Duplicate claim by different holder while P3 is unexpired
        {
            "type": "CLAIM",
            "item_id": "P3",
            "holder": "holder-rogue",
            "host": "host-3",
            "created_at": _stamp(NOW + timedelta(minutes=2)),
            "expires_at": _stamp(NOW + timedelta(minutes=12)),
        },
    ]
    _write_ledger(ledger, events)
    report = audit_work_queue_ledger(ledger)
    assert report.valid is False
    codes = [v.code for v in report.violations]
    assert "TIME_TRAVEL" in codes
    assert "DUPLICATE_CLAIM" in codes


def test_not_holder_and_expired_renew(tmp_path):
    ledger = tmp_path / "renew_violations.jsonl"
    events = [
        {
            "type": "CLAIM",
            "item_id": "P5",
            "holder": "holder-orig",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(minutes=5)),
        },
        # Non-holder tries to renew
        {
            "type": "RENEW",
            "item_id": "P5",
            "holder": "holder-other",
            "created_at": _stamp(NOW + timedelta(minutes=1)),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Original holder tries to renew after lease expired (at minute 6)
        {
            "type": "RENEW",
            "item_id": "P5",
            "holder": "holder-orig",
            "created_at": _stamp(NOW + timedelta(minutes=6)),
            "expires_at": _stamp(NOW + timedelta(minutes=15)),
        },
    ]
    _write_ledger(ledger, events)
    report = audit_work_queue_ledger(ledger)
    assert report.valid is False
    codes = [v.code for v in report.violations]
    assert "NOT_HOLDER" in codes
    assert "LEASE_EXPIRED" in codes


def test_action_after_done_violation(tmp_path):
    ledger = tmp_path / "done_violations.jsonl"
    events = [
        {
            "type": "CLAIM",
            "item_id": "P6",
            "holder": "holder-1",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        {
            "type": "RELEASE",
            "item_id": "P6",
            "holder": "holder-1",
            "created_at": _stamp(NOW + timedelta(minutes=2)),
            "result": "completed successfully",
        },
        # Trying to claim a DONE item
        {
            "type": "CLAIM",
            "item_id": "P6",
            "holder": "holder-2",
            "host": "host-2",
            "created_at": _stamp(NOW + timedelta(minutes=5)),
            "expires_at": _stamp(NOW + timedelta(minutes=15)),
        },
        # Conflicting release
        {
            "type": "RELEASE",
            "item_id": "P6",
            "holder": "holder-1",
            "created_at": _stamp(NOW + timedelta(minutes=6)),
            "result": "different result text",
        },
    ]
    _write_ledger(ledger, events)
    report = audit_work_queue_ledger(ledger)
    assert report.valid is False
    codes = [v.code for v in report.violations]
    assert "ALREADY_DONE" in codes
    assert "CONFLICTING_RELEASE" in codes


def test_ttl_and_past_expiry_violations(tmp_path):
    ledger = tmp_path / "ttl_bad.jsonl"
    events = [
        {
            "type": "CLAIM",
            "item_id": "P7",
            "holder": "holder-1",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW - timedelta(seconds=1)),  # Expired in past
        },
        {
            "type": "CLAIM",
            "item_id": "P8",
            "holder": "holder-1",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(days=30)),  # Exceeds max TTL
        },
    ]
    _write_ledger(ledger, events)
    report = audit_work_queue_ledger(ledger)
    assert report.valid is False
    codes = [v.code for v in report.violations]
    assert "EXPIRES_IN_PAST" in codes
    assert "TTL_OUT_OF_BOUNDS" in codes


def test_syntax_errors_and_malformed_records(tmp_path):
    ledger = tmp_path / "syntax_bad.jsonl"
    ledger.write_text('{"type": "CLAIM"}\nnot a json\n{"type": "UNKNOWN"}\n', encoding="utf-8")
    report = audit_work_queue_ledger(ledger)
    assert report.valid is False
    codes = [v.code for v in report.violations]
    assert "JSON_SYNTAX_ERROR" in codes


def test_concurrent_scope_overlap_detection(tmp_path):
    catalog_dir = tmp_path / "items"
    catalog_dir.mkdir()
    (catalog_dir / "A.json").write_text(
        json.dumps({
            "id": "A",
            "title": "A",
            "files_scope": ["courier_core/shared.py", "courier_core/a.py"],
        }),
        encoding="utf-8",
    )
    (catalog_dir / "B.json").write_text(
        json.dumps({
            "id": "B",
            "title": "B",
            "files_scope": ["courier_core/shared.py", "courier_core/b.py"],
        }),
        encoding="utf-8",
    )
    (catalog_dir / "C.json").write_text(
        json.dumps({
            "id": "C",
            "title": "C",
            "files_scope": ["docs/independent.md"],
        }),
        encoding="utf-8",
    )

    ledger = tmp_path / "ledger.jsonl"
    events = [
        # Claim A
        {
            "type": "CLAIM",
            "item_id": "A",
            "holder": "holder-1",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Concurrently claim C (no overlap with A -> valid)
        {
            "type": "CLAIM",
            "item_id": "C",
            "holder": "holder-2",
            "host": "host-2",
            "created_at": _stamp(NOW + timedelta(minutes=1)),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
        # Concurrently claim B (overlaps shared.py with active A -> violation!)
        {
            "type": "CLAIM",
            "item_id": "B",
            "holder": "holder-3",
            "host": "host-3",
            "created_at": _stamp(NOW + timedelta(minutes=2)),
            "expires_at": _stamp(NOW + timedelta(minutes=10)),
        },
    ]
    _write_ledger(ledger, events)
    report = audit_work_queue_ledger(ledger, items_dir=catalog_dir)
    assert report.valid is False
    codes = [v.code for v in report.violations]
    assert "CONCURRENT_SCOPE_CONFLICT" in codes


def test_cli_execution_clean_and_error(tmp_path, capsys):
    clean_ledger = tmp_path / "clean.jsonl"
    _write_ledger(clean_ledger, [
        {
            "type": "CLAIM",
            "item_id": "P1",
            "holder": "holder-1",
            "host": "host-1",
            "created_at": _stamp(NOW),
            "expires_at": _stamp(NOW + timedelta(minutes=5)),
        },
        {
            "type": "RELEASE",
            "item_id": "P1",
            "holder": "holder-1",
            "created_at": _stamp(NOW + timedelta(minutes=2)),
            "result": "done",
        },
    ])

    ret_clean = main(["--ledger", str(clean_ledger)])
    assert ret_clean == 0
    out = capsys.readouterr().out
    assert "WorkQueue Audit: PASSED" in out

    # CLI with --json
    ret_json = main(["--ledger", str(clean_ledger), "--json"])
    assert ret_json == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["valid"] is True
    assert parsed["events_count"] == 2

    # CLI with broken ledger
    bad_ledger = tmp_path / "bad.jsonl"
    bad_ledger.write_text("invalid json\n", encoding="utf-8")
    ret_bad = main(["--ledger", str(bad_ledger)])
    assert ret_bad == 2
    err = capsys.readouterr().err
    assert "WorkQueue Audit: FAILED" in err
