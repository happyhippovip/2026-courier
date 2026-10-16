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

