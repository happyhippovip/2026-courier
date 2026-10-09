import os
import json
import time
from courier_runtime.kirby import KirbySupervisor, CriticalSnapshot, WakeCoalescer

def test_wake_coalescer():
    w = WakeCoalescer()
    assert w.request_wake() is True
    assert w.request_wake() is False
    assert w.consume_wake() is True
    assert w.consume_wake() is False

def test_critical_snapshot(tmp_path):
    state = {
        "workkey": "WK1",
        "process_identity": "pid:123",
        "state": "RUNNING",
        "checkpoint": "chk1",
        "writer_ownership": "user1",
        "pending_action": "none"
    }
    
    k = KirbySupervisor(provider="muse", host="mac-1", session_id="sess-1", state_dir=str(tmp_path))
    k._take_snapshot(state)
    
    snap_path = tmp_path / "snapshot_sess-1.json"
    assert snap_path.exists()
    
    with open(snap_path) as f:
        data = json.load(f)
        assert data["provider"] == "muse"
        assert data["workkey"] == "WK1"


def test_kirby_on_turn_end_validates_and_records_receipt(tmp_path):
    from courier_runtime.receipt import RecoveryReceipt
    
    k = KirbySupervisor(provider="muse", host="win-1", session_id="sess-turn-1", state_dir=str(tmp_path))
    receipt = RecoveryReceipt(
        workkey="WIN-V25-AG-TEST",
        session_id="sess-turn-1",
        incident_fingerprint="fp-001",
        detected_state="IDLE",
        detected_at=time.time(),
        what_failed="none",
        positive_evidence=None,
        survived={"state": "clean"},
        action="NONE",
        outcome="WAITING",
    )
    
    summary = k.on_turn_end("WIN-V25-AG-TEST", "COMPLETE", receipt=receipt, owned_identities=set())
    assert summary["state"] == "COMPLETED"
    assert summary["workkey"] == "WIN-V25-AG-TEST"
    assert summary["receipt_id"] == receipt.receipt_id

    receipt_file = tmp_path / f"receipt_{receipt.receipt_id}.json"
    assert receipt_file.exists()
    
    ledger_file = tmp_path / "ledger_summary_sess-turn-1.json"
    assert ledger_file.exists()
    with open(ledger_file) as f:
        ledger_data = json.load(f)
        assert ledger_data["receipt_id"] == receipt.receipt_id
        assert ledger_data["state"] == "COMPLETED"


def test_kirby_on_turn_end_rejects_invalid_receipt(tmp_path):
    import pytest
    from courier_runtime.receipt import RecoveryReceipt, ReceiptError

    k = KirbySupervisor(provider="muse", host="win-1", session_id="sess-turn-2", state_dir=str(tmp_path))
    bad_receipt = RecoveryReceipt(
        workkey="WIN-V25-AG-BAD",
        session_id="sess-turn-2",
        incident_fingerprint="fp-002",
        detected_state="UNKNOWN",
        detected_at=time.time(),
        what_failed="task",
        positive_evidence=None,
        survived={},
        action="INVALID_ACTION",  # invalid action
        outcome="WAITING",
    )

    with pytest.raises(ReceiptError, match="unknown action INVALID_ACTION"):
        k.on_turn_end("WIN-V25-AG-BAD", "COMPLETE", receipt=bad_receipt, owned_identities=set())

    ledger_file = tmp_path / "ledger_summary_sess-turn-2.json"
    assert not ledger_file.exists()


def test_kirby_on_turn_end_rejects_unowned_process_retirement(tmp_path):
    import pytest
    from courier_runtime.receipt import RecoveryReceipt, ReceiptError

    k = KirbySupervisor(provider="muse", host="win-1", session_id="sess-turn-3", state_dir=str(tmp_path))
    receipt = RecoveryReceipt(
        workkey="WIN-V25-AG-UNOWNED",
        session_id="sess-turn-3",
        incident_fingerprint="fp-003",
        detected_state="CRASH",
        detected_at=time.time(),
        what_failed="process",
        positive_evidence=None,
        survived={},
        action="RETIRE_OWNED_TREE",
        outcome="WAITING",
        retired=[{"pid": 9999, "create_time": 12345.0}],
    )

    with pytest.raises(ReceiptError, match="retired pid 9999 was not owned"):
        k.on_turn_end("WIN-V25-AG-UNOWNED", "FAILED", receipt=receipt, owned_identities=set())


def test_kirby_on_turn_end_without_receipt(tmp_path):
    k = KirbySupervisor(provider="muse", host="win-1", session_id="sess-turn-4", state_dir=str(tmp_path))
    summary = k.on_turn_end("WIN-V25-AG-NO-RECEIPT", "STILL_OPEN")
    assert summary["state"] == "STILL_OPEN"
    assert summary["receipt_id"] is None
    ledger_file = tmp_path / "ledger_summary_sess-turn-4.json"
    assert ledger_file.exists()

