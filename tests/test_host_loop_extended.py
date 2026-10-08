import json
import os
import pytest

from courier_runtime.continuity import HEALTH_TICK_S, WAKE_PENDING, WORKING, Kirby
from courier_runtime.host_loop import (
    _file_size,
    drain_pending,
    emit_signal,
    main,
    run_once,
)


class DummyClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


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
        pid = 3000 + len(self.started)
        self.started.append((slot, gen))
        self.alive[pid] = float(pid)
        return f"{slot}-g{gen}", pid, float(pid)


def make_hloop_setup(tmp_path, workkeys=None, slot="test-slot"):
    clock = DummyClock()
    world = DummyWorld()
    k = Kirby(
        tmp_path / "kirby.json",
        "mac-host",
        identity=world.identity,
        terminate=world.terminate,
        start_session=world.start,
        clock=clock,
    )
    if workkeys:
        k.add_workkeys(workkeys)
    k.open_slot(slot, "antigravity")
    sig_file = tmp_path / "signals" / "provider.signals"
    state = {"offset": 0, "last_tick": 0.0, "notified": {}}
    return k, clock, world, sig_file, state


class TestHostLoopExtended:
    """Rigorous edge-case coverage for host loop signal tailing and wake contracts."""

    def test_file_size_helper_missing_file_returns_none(self, tmp_path):
        assert _file_size(tmp_path / "nonexistent.file") is None

    def test_emit_signal_creates_directories_and_writes_fsynced(self, tmp_path):
        sig_path = tmp_path / "nested" / "dir" / "provider.signals"
        assert not sig_path.exists()

        line = "TURN_ENDED outcome=DONE checkpoint=cp-alpha"
        ret = emit_signal(sig_path, line)
        assert ret == line
        assert sig_path.exists()
        assert sig_path.read_text(encoding="utf-8") == line + "\n"

    def test_run_once_missing_signal_file_still_ticks_cadence(self, tmp_path):
        k, clock, _, sig_file, state = make_hloop_setup(tmp_path)
        # Ensure signal file does not exist
        assert not sig_file.exists()

        # Initial run: clock is 1000.0, last_tick is 0.0 -> elapsed >= HEALTH_TICK_S
        results, actions, notices = run_once(k, "test-slot", sig_file, state)
        assert results == []
        assert notices == []
        assert state["last_tick"] == 1000.0

        # Run immediately again before HEALTH_TICK_S passes: actions should be empty dict
        clock.advance(5.0)
        results2, actions2, notices2 = run_once(k, "test-slot", sig_file, state)
        assert results2 == []
        assert actions2 == {}
        assert notices2 == []

    def test_run_once_file_truncation_resets_offset(self, tmp_path):
        k, clock, _, sig_file, state = make_hloop_setup(tmp_path, workkeys=["WK-1"])
        emit_signal(sig_file, "IDLE")

        # First run consumes the file
        run_once(k, "test-slot", sig_file, state)
        initial_offset = state["offset"]
        assert initial_offset > 0

        # Truncate file (e.g. log rotation) to 0 bytes
        sig_file.write_text("", encoding="utf-8")
        assert _file_size(sig_file) < initial_offset

        # Next run detects offset > size and resets offset to 0
        run_once(k, "test-slot", sig_file, state)
        assert state["offset"] == 0

    def test_drain_pending_fencing_and_idempotence(self, tmp_path):
        k, clock, _, sig_file, state = make_hloop_setup(tmp_path, workkeys=["WK-A", "WK-B"])

        # Unknown slot returns None
        assert drain_pending(k, "nonexistent-slot") is None

        # Slot open but no wake pending -> returns None
        assert drain_pending(k, "test-slot") is None

        # Emit IDLE signal -> triggers WAKE_PENDING
        emit_signal(sig_file, "IDLE")
        run_once(k, "test-slot", sig_file, state)
        session = k.sessions["test-slot"]
        assert session.state == WAKE_PENDING

        # First drain_pending delivers workkey and marks session WORKING
        wk = drain_pending(k, "test-slot")
        assert wk == "WK-A"
        assert session.state == WORKING

        # Immediate second drain_pending returns None (one wake = one execution)
        assert drain_pending(k, "test-slot") is None

    def test_notices_file_generation_and_duplicate_suppression(self, tmp_path):
        k, clock, _, sig_file, state = make_hloop_setup(tmp_path, workkeys=["WK-1"])
        emit_signal(sig_file, "IDLE")

        # First run generates exactly one notice in notices.jsonl
        _, _, notices = run_once(k, "test-slot", sig_file, state)
        assert len(notices) == 1

        notices_path = tmp_path / "wakeups.jsonl"
        assert notices_path.exists()
        lines = notices_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["slot"] == "test-slot"
        assert record["workkey"] == "WK-1"

        # Subsequent run without session change produces NO duplicate notices
        _, _, notices_repeat = run_once(k, "test-slot", sig_file, state)
        assert len(notices_repeat) == 0

    def test_main_cli_once_flag(self, tmp_path):
        k, _, _, sig_file, _ = make_hloop_setup(tmp_path)
        emit_signal(sig_file, "IDLE")

        exit_code = main([
            "--state", str(tmp_path / "kirby.json"),
            "--slot", "test-slot",
            "--signals", str(sig_file),
            "--host", "mac-host",
            "--once"
        ])
        assert exit_code == 0
