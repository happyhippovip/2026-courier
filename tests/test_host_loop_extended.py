import pytest
from pathlib import Path

from courier_runtime.host_loop import emit_signal, drain_pending, run_once, _file_size
from courier_runtime.continuity import Kirby, WAKE_PENDING


class MockClock:
    def __init__(self, t=100.0):
        self.t = t

    def __call__(self):
        return self.t


def test_file_size_helper(tmp_path):
    p = tmp_path / "test.txt"
    assert _file_size(str(p)) is None

    p.write_text("hello", encoding="utf-8")
    assert _file_size(str(p)) == 5


def test_emit_signal_atomic_append(tmp_path):
    p = tmp_path / "signals" / "sig.log"
    line = emit_signal(str(p), "IDLE")
    assert line == "IDLE"
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "IDLE\n"

    # Second line
    emit_signal(str(p), "TURN_ENDED outcome=DONE")
    assert p.read_text(encoding="utf-8") == "IDLE\nTURN_ENDED outcome=DONE\n"


def test_drain_pending_empty_when_no_session_or_not_pending(tmp_path):
    clock = MockClock()
    k = Kirby(tmp_path / "kirby.json", "mac-1", clock=clock)
    # Slot doesn't exist
    assert drain_pending(k, "nonexistent-slot") is None

    # Slot exists but state is IDLE (not WAKE_PENDING)
    k.open_slot("slot-1", "muse")
    assert drain_pending(k, "slot-1") is None


def test_run_once_file_truncation_resets_offset(tmp_path):
    clock = MockClock()
    k = Kirby(tmp_path / "kirby.json", "mac-1", clock=clock)
    k.add_workkeys(["W1"])
    k.open_slot("slot-1", "muse")

    sig = tmp_path / "signals.log"
    sig.write_text("IDLE\n", encoding="utf-8")

    state = {"offset": 100, "last_tick": 0.0, "notified": {}}  # artificial offset past end
    results, actions, notices = run_once(k, "slot-1", str(sig), state)

    # Offset should have reset to 0 then advanced past "IDLE\n"
    assert state["offset"] == len("IDLE\n")
    assert results == [WAKE_PENDING]
