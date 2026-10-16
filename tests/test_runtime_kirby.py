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


def test_kirby_on_turn_end(tmp_path):
    k = KirbySupervisor(provider="muse", host="mac-1", session_id="sess-1", state_dir=str(tmp_path))
    assert k.on_turn_end("WK1", "COMPLETE") == {"action": "NEXT", "workkey": "WK1", "status": "COMPLETE"}
    assert k.on_turn_end("WK1", "BLOCKED") == {"action": "PAUSE", "workkey": "WK1", "reason": "blocked"}
    assert k.on_turn_end("WK1", "STILL_OPEN") == {"action": "CONTINUE", "workkey": "WK1", "status": "STILL_OPEN"}
    assert k.on_turn_end("WK1", "RUNNING") == {"action": "CONTINUE", "workkey": "WK1", "status": "STILL_OPEN"}
    assert k.on_turn_end("", "COMPLETE") == {"action": "PAUSE", "reason": "invalid_workkey"}


def test_session_rotator_prepare_rotation(tmp_path):
    from courier_runtime.kirby import SessionRotator
    rotator = SessionRotator(state_dir=str(tmp_path))
    manifest = rotator.prepare_rotation(session_id="sess-xyz", checkpoint="chk-999", workkey="WK-ROT")
    assert manifest["session_id"] == "sess-xyz"
    assert manifest["status"] == "READY_FOR_ROTATION"
    rot_path = tmp_path / "rotation_sess-xyz.json"
    assert rot_path.exists()
    with open(rot_path) as f:
        saved = json.load(f)
        assert saved["checkpoint"] == "chk-999"
        assert saved["workkey"] == "WK-ROT"


