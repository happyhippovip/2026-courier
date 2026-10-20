"""Tests for Dual-Ledger Bridge and State Reconciler."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.ledger_sync import (
    LedgerBridge,
    SyncResult,
    sync_ledgers,
    reconcile_bidirectional,
    main,
)


def make_event(event_id: str, event_type: str, item_id: str, at: str, payload: dict | None = None) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "item_id": item_id,
        "at": at,
        "payload": payload or {},
    }


def write_jsonl(path: Path, events: list[dict]):
    lines = [json.dumps(e) for e in events]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_sync_unreplicated_events(tmp_path):
    source = tmp_path / "source.jsonl"
    target = tmp_path / "target.jsonl"

    events = [
        make_event("evt-1", "claim", "P1", "2026-10-18T10:00:00Z"),
        make_event("evt-2", "renew", "P1", "2026-10-18T10:15:00Z"),
    ]
    write_jsonl(source, events)

    bridge = LedgerBridge(source_path=str(source), target_path=str(target))
    res = bridge.sync_forward()

    assert res.synced_count == 2
    assert res.skipped_count == 0
    assert len(read_jsonl(target)) == 2


def test_idempotent_sync_no_duplicates(tmp_path):
    source = tmp_path / "source.jsonl"
    target = tmp_path / "target.jsonl"

    events = [
        make_event("evt-1", "claim", "P1", "2026-10-18T10:00:00Z"),
        make_event("evt-2", "release", "P1", "2026-10-18T10:30:00Z"),
    ]
    write_jsonl(source, events)

    bridge = LedgerBridge(source_path=str(source), target_path=str(target))
    res1 = bridge.sync_forward()
    assert res1.synced_count == 2

    # Second sync pass
    res2 = bridge.sync_forward()
    assert res2.synced_count == 0
    assert res2.skipped_count == 2
    assert len(read_jsonl(target)) == 2


def test_event_order_and_sequence_monotonicity(tmp_path):
    source = tmp_path / "source.jsonl"
    target = tmp_path / "target.jsonl"

    existing_target = [
        make_event("evt-0", "init", "SYSTEM", "2026-10-18T09:00:00Z"),
    ]
    write_jsonl(target, existing_target)

    new_source = [
        make_event("evt-1", "claim", "P1", "2026-10-18T10:00:00Z"),
        make_event("evt-2", "release", "P1", "2026-10-18T10:30:00Z"),
    ]
    write_jsonl(source, new_source)

    bridge = LedgerBridge(source_path=str(source), target_path=str(target))
    res = bridge.sync_forward()

    assert res.synced_count == 2
    target_events = read_jsonl(target)
    assert len(target_events) == 3
    ids = [e["event_id"] for e in target_events]
    assert ids == ["evt-0", "evt-1", "evt-2"]


def test_checksum_and_tamper_detection(tmp_path):
    source = tmp_path / "source.jsonl"
    target = tmp_path / "target.jsonl"

    # Target has evt-1 with different payload
    target_event = make_event("evt-1", "claim", "P1", "2026-10-18T10:00:00Z", {"holder": "attacker"})
    write_jsonl(target, [target_event])

    source_event = make_event("evt-1", "claim", "P1", "2026-10-18T10:00:00Z", {"holder": "legit-worker"})
    write_jsonl(source, [source_event])

    bridge = LedgerBridge(source_path=str(source), target_path=str(target))
    with pytest.raises(ValueError, match="Ledger conflict or tamper detected"):
        bridge.sync_forward()


def test_watermark_state_persistence(tmp_path):
    source = tmp_path / "source.jsonl"
    target = tmp_path / "target.jsonl"
    watermark_file = tmp_path / "sync.watermark"

    events = [
        make_event("evt-1", "claim", "P1", "2026-10-18T10:00:00Z"),
        make_event("evt-2", "release", "P1", "2026-10-18T10:30:00Z"),
    ]
    write_jsonl(source, events)

    bridge = LedgerBridge(
        source_path=str(source),
        target_path=str(target),
        watermark_path=str(watermark_file),
    )
    bridge.sync_forward()
    assert watermark_file.exists()
    assert "evt-2" in watermark_file.read_text(encoding="utf-8")

    # Append new event
    events.append(make_event("evt-3", "claim", "P2", "2026-10-18T11:00:00Z"))
    write_jsonl(source, events)

    res = bridge.sync_forward()
    assert res.synced_count == 1
    assert "evt-3" in watermark_file.read_text(encoding="utf-8")


def test_bidirectional_reconciliation(tmp_path):
    node_a = tmp_path / "node_a.jsonl"
    node_b = tmp_path / "node_b.jsonl"

    events_a = [
        make_event("evt-a1", "claim", "P1", "2026-10-18T10:00:00Z"),
    ]
    events_b = [
        make_event("evt-b1", "claim", "P2", "2026-10-18T10:05:00Z"),
    ]
    write_jsonl(node_a, events_a)
    write_jsonl(node_b, events_b)

    reconcile_bidirectional(str(node_a), str(node_b))

    a_events = read_jsonl(node_a)
    b_events = read_jsonl(node_b)

    assert len(a_events) == 2
    assert len(b_events) == 2
    assert {e["event_id"] for e in a_events} == {"evt-a1", "evt-b1"}
    assert {e["event_id"] for e in b_events} == {"evt-a1", "evt-b1"}


def test_cli_invocation(tmp_path):
    source = tmp_path / "cli_source.jsonl"
    target = tmp_path / "cli_target.jsonl"

    events = [make_event("evt-cli-1", "claim", "P18", "2026-10-18T12:00:00Z")]
    write_jsonl(source, events)

    code = main([
        "--source", str(source),
        "--target", str(target),
    ])
    assert code == 0
    assert len(read_jsonl(target)) == 1


def test_work_queue_events_without_event_id_and_compacted_watermark(tmp_path):
    source = tmp_path / "wq_source.jsonl"
    target = tmp_path / "wq_target.jsonl"
    wm = tmp_path / "wq.watermark"
    wm.write_text("compacted-old-event-id", encoding="utf-8")

    write_jsonl(source, [
        {"type": "CLAIM", "item_id": "P61", "holder": "windows-titan", "at": "2026-10-19T01:00:00Z"},
        {"type": "RELEASE", "item_id": "P61", "holder": "windows-titan", "result": "DONE", "at": "2026-10-19T01:05:00Z"},
    ])
    res = sync_ledgers(str(source), str(target), watermark_path=str(wm))
    assert res.synced_count == 2
    res2 = sync_ledgers(str(source), str(target), watermark_path=str(wm))
    assert res2.synced_count == 0
    assert res2.skipped_count == 2

