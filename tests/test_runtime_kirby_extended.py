import time
import json
import threading
from courier_runtime.kirby import KirbySupervisor, CriticalSnapshot, WakeCoalescer, SessionRotator


def test_wake_coalescer_concurrency():
    w = WakeCoalescer()
    results = []

    def try_request():
        results.append(w.request_wake())

    threads = [threading.Thread(target=try_request) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread succeeds in requesting a wake
    assert results.count(True) == 1
    assert results.count(False) == 9

    # Consume it
    assert w.consume_wake() is True
    assert w.consume_wake() is False


def test_kirby_supervisor_lifecycle(tmp_path):
    k = KirbySupervisor(provider="gemini", host="mac-2", session_id="sess-99", state_dir=str(tmp_path))
    assert k.provider == "gemini"
    assert k.host == "mac-2"
    assert k.session_id == "sess-99"

    state_calls = []

    def get_state():
        state_calls.append(1)
        return {
            "workkey": "WK-KIRBY",
            "process_identity": "proc-99",
            "state": "ACTIVE",
            "checkpoint": "chk-001",
            "writer_ownership": "L4-writer",
            "pending_action": "test",
        }

    k.start(get_state)
    time.sleep(0.1)
    k.stop()

    assert len(state_calls) >= 1
    # Check manual snapshot execution
    k._take_snapshot(get_state())
    snap_path = tmp_path / "snapshot_sess-99.json"
    assert snap_path.exists()
    data = json.loads(snap_path.read_text(encoding="utf-8"))
    assert data["workkey"] == "WK-KIRBY"
    assert data["process_identity"] == "proc-99"
    assert data["current_state"] == "ACTIVE"


def test_session_rotator_instantiation():
    rotator = SessionRotator()
    assert rotator is not None
    # Method invocation doesn't raise
    rotator.prepare_rotation("sess-1", "chk-1")
