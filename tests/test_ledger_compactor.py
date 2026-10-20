import json
import pytest
from pathlib import Path
from courier_core.ledger_compactor import (
    LedgerCompactor,
    LedgerSnapshot,
    CompactStateRecord,
    rebuild_ledger_state,
)


def create_sample_ledger(path: Path) -> list[dict]:
    events = [
        # Item 1: completed
        {"event_type": "CLAIM", "item_id": "P1", "holder": "worker-a", "expires_at": "2026-10-18T10:00:00Z", "timestamp": "2026-10-18T09:00:00Z"},
        {"event_type": "RENEW", "item_id": "P1", "holder": "worker-a", "expires_at": "2026-10-18T11:00:00Z", "timestamp": "2026-10-18T09:30:00Z"},
        {"event_type": "RELEASE", "item_id": "P1", "holder": "worker-a", "result": "DONE", "timestamp": "2026-10-18T10:15:00Z"},
        # Item 2: active lease
        {"event_type": "CLAIM", "item_id": "P2", "holder": "worker-b", "expires_at": "2026-10-18T12:00:00Z", "timestamp": "2026-10-18T11:00:00Z"},
        # Item 3: failed
        {"event_type": "CLAIM", "item_id": "P3", "holder": "worker-c", "expires_at": "2026-10-18T12:00:00Z", "timestamp": "2026-10-18T11:15:00Z"},
        {"event_type": "RELEASE", "item_id": "P3", "holder": "worker-c", "result": "FAILED", "timestamp": "2026-10-18T11:45:00Z"},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    return events


def test_rebuild_ledger_state_collapsing(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    create_sample_ledger(ledger_path)

    state, total_events = rebuild_ledger_state(ledger_path)
    assert total_events == 6
    assert len(state) == 3

    # P1
    p1 = state["P1"]
    assert p1.item_id == "P1"
    assert p1.status == "DONE"
    assert p1.last_holder == "worker-a"
    assert p1.event_count == 3

    # P2
    p2 = state["P2"]
    assert p2.item_id == "P2"
    assert p2.status == "CLAIMED"
    assert p2.last_holder == "worker-b"
    assert p2.event_count == 1

    # P3
    p3 = state["P3"]
    assert p3.item_id == "P3"
    assert p3.status == "FAILED"
    assert p3.last_holder == "worker-c"
    assert p3.event_count == 2


def test_create_and_load_snapshot(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    snapshot_path = tmp_path / "snapshot.json"
    create_sample_ledger(ledger_path)

    compactor = LedgerCompactor()
    snapshot = compactor.create_snapshot(ledger_path, snapshot_path)

    assert snapshot.total_events_compacted == 6
    assert len(snapshot.records) == 3
    assert snapshot.checksum_sha256 != ""
    assert snapshot_path.exists()

    # Verify loaded snapshot
    loaded = compactor.load_snapshot(snapshot_path)
    assert loaded.total_events_compacted == 6
    assert loaded.checksum_sha256 == snapshot.checksum_sha256
    assert loaded.records["P1"].status == "DONE"
    assert loaded.records["P2"].status == "CLAIMED"


def test_state_equivalence_verification(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    snapshot_path = tmp_path / "snapshot.json"
    create_sample_ledger(ledger_path)

    compactor = LedgerCompactor()
    compactor.create_snapshot(ledger_path, snapshot_path)

    is_equiv, diff = compactor.verify_equivalence(ledger_path, snapshot_path)
    assert is_equiv is True
    assert diff == []


def test_checksum_tamper_detection(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    snapshot_path = tmp_path / "snapshot.json"
    create_sample_ledger(ledger_path)

    compactor = LedgerCompactor()
    compactor.create_snapshot(ledger_path, snapshot_path)

    # Tamper with snapshot content
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    data["records"]["P1"]["status"] = "TAMPERED"
    snapshot_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        compactor.load_snapshot(snapshot_path)
    assert "Checksum mismatch" in str(exc_info.value)


def test_incremental_replay_after_snapshot(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    snapshot_path = tmp_path / "snapshot.json"
    create_sample_ledger(ledger_path)

    compactor = LedgerCompactor()
    compactor.create_snapshot(ledger_path, snapshot_path)

    # Append new event to ledger
    new_event = {
        "event_type": "RELEASE",
        "item_id": "P2",
        "holder": "worker-b",
        "result": "DONE",
        "timestamp": "2026-10-18T13:00:00Z"
    }
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(new_event) + "\n")

    # Fast replay: start from snapshot, process delta lines (from offset 6)
    updated_state = compactor.replay_with_delta(snapshot_path, ledger_path)
    assert updated_state["P2"].status == "DONE"
    assert updated_state["P2"].event_count == 2


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    ledger_path = tmp_path / "cli_ledger.jsonl"
    snapshot_path = tmp_path / "cli_snapshot.json"
    create_sample_ledger(ledger_path)

    # Run compact command
    cmd_compact = [
        sys.executable,
        "-m",
        "courier_core.ledger_compactor",
        "compact",
        "--ledger",
        str(ledger_path),
        "--snapshot",
        str(snapshot_path),
    ]
    proc_compact = subprocess.run(cmd_compact, capture_output=True, text=True, check=True)
    out_compact = json.loads(proc_compact.stdout)
    assert out_compact["status"] == "COMPACTED"
    assert out_compact["total_events_compacted"] == 6

    # Run verify command
    cmd_verify = [
        sys.executable,
        "-m",
        "courier_core.ledger_compactor",
        "verify",
        "--ledger",
        str(ledger_path),
        "--snapshot",
        str(snapshot_path),
    ]
    proc_verify = subprocess.run(cmd_verify, capture_output=True, text=True, check=True)
    out_verify = json.loads(proc_verify.stdout)
    assert out_verify["equivalent"] is True
