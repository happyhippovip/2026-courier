import os
import json
import time
import threading
import pytest
from courier_runtime.kirby import KirbySupervisor, CriticalSnapshot, WakeCoalescer, SessionRotator


def test_wake_coalescer_concurrency():
    w = WakeCoalescer()
    results = []

    def try_request():
        results.append(w.request_wake())

    threads = [threading.Thread(target=try_request) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread must have succeeded in requesting the wake
    assert results.count(True) == 1
    assert results.count(False) == 19

    # Now consume it
    assert w.consume_wake() is True
    assert w.consume_wake() is False


def test_supervisor_start_and_stop_lifecycle(tmp_path):
    state = {
        "workkey": "WK-LIFE",
        "process_identity": "proc:456",
        "state": "IDLE",
        "checkpoint": "chk-0",
        "writer_ownership": "lane4",
        "pending_action": "none"
    }

    k = KirbySupervisor(provider="antigravity", host="test-mac", session_id="sess-life", state_dir=str(tmp_path))
    k.start(lambda: state)
    assert k._thread is not None
    assert k._thread.is_alive()
    k.stop()
    assert not k._thread.is_alive()


def test_supervisor_snapshot_file_structure(tmp_path):
    state = {
        "workkey": "WK-CORRECTNESS",
        "process_identity": "runner:77",
        "state": "COMMITTED",
        "checkpoint": "chk-verified",
        "writer_ownership": "chief",
        "pending_action": "verify_receipt"
    }
    k = KirbySupervisor(provider="codex", host="darwin-arm64", session_id="sess-99", state_dir=str(tmp_path))
    k._take_snapshot(state)

    target_file = tmp_path / "snapshot_sess-99.json"
    assert target_file.exists()

    with open(target_file, "r") as f:
        payload = json.load(f)

    assert payload["provider"] == "codex"
    assert payload["host"] == "darwin-arm64"
    assert payload["session_id"] == "sess-99"
    assert payload["workkey"] == "WK-CORRECTNESS"
    assert payload["current_state"] == "COMMITTED"
    assert payload["checkpoint_reference"] == "chk-verified"
    assert payload["writer_ownership"] == "chief"
    assert payload["pending_action"] == "verify_receipt"
    assert isinstance(payload["last_useful_progress"], float)


def test_session_rotator_interface():
    rotator = SessionRotator()
    # Ensure method exists and can be safely called without exceptions
    rotator.prepare_rotation("sess-1", "chk-1")
