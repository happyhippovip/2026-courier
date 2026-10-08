import pytest

from courier_runtime.continuity import BLOCKED, DONE, OPEN, WAKE_PENDING, Kirby
from courier_runtime import provider_events as pe


class DummyClock:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


class DummyWorld:
    def __init__(self):
        self.alive = {}
        self.started = []
        self.terminated = []

    def identity(self, s):
        return self.alive.get(s.pid) == s.create_time

    def terminate(self, s):
        self.terminated.append(s.pid)
        self.alive.pop(s.pid, None)
        return {"result": "STOPPED"}

    def start(self, slot, gen):
        pid = 2000 + len(self.started)
        self.started.append((slot, gen))
        self.alive[pid] = float(pid)
        return f"{slot}-g{gen}", pid, float(pid)


def make_kirby(tmp_path):
    clock = DummyClock()
    world = DummyWorld()
    k = Kirby(
        tmp_path / "kirby.json",
        "mac-test",
        identity=world.identity,
        terminate=world.terminate,
        start_session=world.start,
        clock=clock,
    )
    return k, clock, world


class TestProviderEventsExtended:
    """Rigorous edge-case verification for provider-event ingress and line grammar parsing."""

    def test_parse_line_empty_and_whitespace(self):
        for raw in [None, "", "   ", "\t\n  "]:
            kind, fields, text = pe.parse_line(raw)
            assert kind is None
            assert fields == {}
            assert text == ""

    def test_parse_line_unknown_or_custom_commands(self):
        kind, fields, text = pe.parse_line("UNKNOWN_CMD arg1 arg2")
        assert kind == "UNKNOWN_CMD"
        assert fields == {}
        assert text == "arg1 arg2"

    def test_parse_line_turn_ended_with_free_text_remainder(self):
        # checkpoint= remainder captures multi-word strings
        line = "TURN_ENDED outcome=DONE checkpoint=step 3 verified /path/to/artifact"
        kind, fields, text = pe.parse_line(line)
        assert kind == "TURN_ENDED"
        assert fields["outcome"] == "DONE"
        assert fields["checkpoint"] == "step 3 verified /path/to/artifact"

        # reason= remainder captures free text
        line_blocked = "TURN_ENDED outcome=BLOCKED reason=rate limited: retry after 60s at gateway"
        kind, fields, text = pe.parse_line(line_blocked)
        assert kind == "TURN_ENDED"
        assert fields["outcome"] == "BLOCKED"
        assert fields["reason"] == "rate limited: retry after 60s at gateway"

    def test_parse_line_heartbeat_flags(self):
        line = "HEARTBEAT progress=1 checkpoint=saving intermediate weights"
        kind, fields, text = pe.parse_line(line)
        assert kind == "HEARTBEAT"
        assert fields["progress"] == "1"
        assert fields["checkpoint"] == "saving intermediate weights"

    def test_handle_unknown_slot_fail_closed(self, tmp_path):
        k, _, _ = make_kirby(tmp_path)
        # Slot not opened yet
        res = pe.handle(k, "nonexistent-slot", "IDLE")
        assert res == "IGNORED_NO_SLOT"

    def test_handle_unknown_line_types_ignored(self, tmp_path):
        k, _, _ = make_kirby(tmp_path)
        k.open_slot("slot-1", "antigravity")
        assert pe.handle(k, "slot-1", "RANDOM_GARBAGE_LINE") == "IGNORED"
        assert pe.handle(k, "slot-1", "") == "IGNORED"

    def test_handle_malformed_turn_ended_outcome_defaults_still_open(self, tmp_path):
        k, _, _ = make_kirby(tmp_path)
        k.add_workkeys(["WK-1"])
        k.open_slot("slot-1", "antigravity")
        k.wake("slot-1")
        k.deliver("slot-1")

        # Provider emits unrecognized outcome "SUCCESS" or "ABORT" instead of standard enum
        res = pe.handle(k, "slot-1", "TURN_ENDED outcome=INVALID_STATUS checkpoint=cp1")
        # Should reconcile as STILL_OPEN, not completing or blocking the workkey
        wk = k.workkeys["WK-1"]
        assert wk.state != DONE
        assert wk.state != BLOCKED

    def test_read_new_lines_incremental_file_growth(self, tmp_path):
        log_file = tmp_path / "provider.log"
        log_file.write_text("LINE 1\nLINE 2\n", encoding="utf-8")

        lines, offset = pe.read_new_lines(log_file, 0)
        assert lines == ["LINE 1", "LINE 2"]
        assert offset > 0

        # Append more data
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("LINE 3\nLINE 4\n")

        new_lines, new_offset = pe.read_new_lines(log_file, offset)
        assert new_lines == ["LINE 3", "LINE 4"]
        assert new_offset > offset

        # No new lines -> returns empty list and same offset
        empty_lines, same_offset = pe.read_new_lines(log_file, new_offset)
        assert empty_lines == []
        assert same_offset == new_offset
