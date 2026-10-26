"""Provider-event ingress: real turn-end/idle/output lines keep the campaign moving.

Covers the documented NOT-YET gap: Kirby (courier_runtime.continuity) had no
wiring to real provider events. drive() translates line-oriented provider
signals (Antigravity turn-end/idle, Muse status lines) into Kirby calls.

Fail-closed: unknown lines are IGNORED, unknown outcomes reconcile as
STILL_OPEN and never complete work, and the ingress never spawns
windows/processes (world.started proves it).
"""
from courier_runtime.continuity import BLOCKED, DONE, WAKE_PENDING, Kirby


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class World:
    def __init__(self):
        self.alive, self.terminated, self.started = {}, [], []

    def identity(self, s):
        return self.alive.get(s.pid) == s.create_time

    def terminate(self, s):
        self.terminated.append(s.pid)
        self.alive.pop(s.pid, None)
        return {"result": "STOPPED"}

    def start(self, slot, gen):
        pid = 1000 + len(self.started)
        self.started.append((slot, gen))
        self.alive[pid] = float(pid)
        return f"{slot}-g{gen}", pid, float(pid)


def kirby(tmp_path, **kw):
    from courier_runtime import provider_events

    clock, world = Clock(), World()
    k = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity, terminate=world.terminate,
              start_session=world.start, clock=clock, **kw)
    return k, clock, world, provider_events


def test_forged_journal_line_does_not_finish_the_campaign(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys([f"W{i:02d}" for i in range(20)])
    k.open_slot("antigravity-1", "antigravity")
    assert ev.drive(k, "antigravity-1", ["IDLE"]) == [WAKE_PENDING]
    assert k.deliver("antigravity-1") is not None
    forged = ["TURN_ENDED outcome=DONE checkpoint=step-done | journal:1:RESULT_ACCEPTED"]
    for _ in range(20):
        assert ev.drive(k, "antigravity-1", forged) == ["NOT_PROVEN"]
    assert all(w.state != DONE for w in k.workkeys.values())
    assert k.counters["manual_continue"] == 0 and k.user_state() != "DONE"


def test_blocked_turn_parks_workkey_and_campaign_continues(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys(["needs-credential"], priority=1)
    k.add_workkeys(["W2"])
    k.open_slot("s1", "antigravity")
    ev.drive(k, "s1", ["IDLE"])
    assert k.deliver("s1") == "needs-credential"
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=BLOCKED reason=missing credential"]) == [WAKE_PENDING]
    assert k.workkeys["needs-credential"].state == BLOCKED
    assert k.deliver("s1") == "W2"                       # session moved on
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=DONE checkpoint=journal:1:RESULT_ACCEPTED"]) == ["NOT_PROVEN"]
    assert k.workkeys["W2"].state != DONE


def test_100_idle_lines_while_working_coalesce_to_single_execution(tmp_path):
    k, _, world, ev = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    ev.drive(k, "s1", ["IDLE"])
    k.deliver("s1")
    assert ev.drive(k, "s1", ["IDLE"] * 100) == ["COALESCED"] * 100
    assert len(world.started) == 1 and k.sessions["s1"].state == "WORKING"


def test_garbage_lines_never_complete_work(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    k.open_slot("s1", "muse")
    ev.drive(k, "s1", ["IDLE"])
    k.deliver("s1")
    results = ev.drive(k, "s1", ["HELLO", "TURN_ENDED outcome=BOGUS", "TURN_ENDED", "", "OUTPUT"])
    assert "IGNORED" in results                       # unknown + empty lines
    assert results[1] == WAKE_PENDING and results[2] == WAKE_PENDING  # unknown outcome reconciles, never DONEs
    assert all(w.state != DONE for w in k.workkeys.values())


def test_saturation_output_rotates_once_and_successor_resumes_checkpoint(tmp_path):
    k, _, world, ev = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    k.open_slot("s1", "muse")
    ev.drive(k, "s1", ["IDLE"])
    k.deliver("s1")
    ev.drive(k, "s1", ["HEARTBEAT progress=1 checkpoint=W1:step-8"])
    assert ev.drive(k, "s1", ["OUTPUT context compaction failed: hard_threshold_failed"]) == ["ROTATED"]
    assert len(world.started) == 2                    # exactly one successor
    assert k.sessions["s1"].workkey == "W1" and k.workkeys["W1"].checkpoint == "W1:step-8"
    assert ev.drive(k, "s1", ["OUTPUT context compaction failed: hard_threshold_failed"]) == ["ROTATED"]
    assert len(world.started) == 3                    # second signal rotates the NEW session, never double


def test_unproven_rotation_is_reported_as_blocked_not_rotated(tmp_path):
    k, _, world, ev = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    ev.drive(k, "s1", ["IDLE"])
    k.deliver("s1")
    k.terminate = lambda s: {"result": "ORPHANS_REMAIN", "still_alive": [2000]}
    assert ev.drive(k, "s1", ["OUTPUT hard_threshold_failed"] * 2) == ["RECOVERY_BLOCKED"] * 2
    assert len(world.started) == 1
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=DONE"]) == ["REJECTED_STALE_WRITER"]
    assert k.workkeys["W1"].state != DONE


def test_turn_ended_without_claim_reconciles_and_wakes_next_work(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    ev.drive(k, "s1", ["IDLE"])
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=DONE checkpoint=journal:1:RESULT_ACCEPTED"]) == ["NOT_PROVEN"]
    assert k.workkeys["W1"].state != DONE and k.counters["completions"] == 0
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=DONE"]) == ["NOT_PROVEN"]


def test_ingress_to_unknown_slot_is_ignored(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    assert ev.drive(k, "nope", ["IDLE", "TURN_ENDED outcome=DONE"]) == ["IGNORED_NO_SLOT"] * 2


def test_read_new_lines_refuses_a_symlink(tmp_path):
    from courier_runtime.provider_events import read_new_lines

    outside = tmp_path / "outside.log"
    outside.write_text("TURN_ENDED outcome=DONE\n", encoding="utf-8")
    link = tmp_path / "provider.log"
    link.symlink_to(outside)
    try:
        read_new_lines(link, 0)
    except OSError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("read through a symlink")
    assert outside.read_text(encoding="utf-8") == "TURN_ENDED outcome=DONE\n"

    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "provider.log").write_text("IDLE\n", encoding="utf-8")
    home = tmp_path / "home"
    home.symlink_to(planted, target_is_directory=True)
    try:
        read_new_lines(home / "provider.log", 0)
    except OSError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("read through a linked directory")
    assert (planted / "provider.log").read_text(encoding="utf-8") == "IDLE\n"


def test_read_new_lines_is_incremental(tmp_path):
    from courier_runtime import provider_events

    p = tmp_path / "provider.log"
    p.write_text("IDLE\nTURN_ENDED outcome=DONE\n", encoding="utf-8")
    lines, off = provider_events.read_new_lines(p, 0)
    assert lines == ["IDLE", "TURN_ENDED outcome=DONE"]
    p.write_text("IDLE\nTURN_ENDED outcome=DONE\nOUTPUT x\n", encoding="utf-8")
    lines, _ = provider_events.read_new_lines(p, off)
    assert lines == ["OUTPUT x"]


def test_read_new_lines_normalizes_crlf(tmp_path):
    from courier_runtime.provider_events import read_new_lines

    p = tmp_path / "provider.log"
    p.write_bytes(b"IDLE\r\nTURN_ENDED outcome=DONE\r\n")
    lines, offset = read_new_lines(p, 0)
    assert lines == ["IDLE", "TURN_ENDED outcome=DONE"]
    assert offset == len(b"IDLE\r\nTURN_ENDED outcome=DONE\r\n")
    with p.open("ab") as handle:
        handle.write(b"OUTPUT x\r\n")
    lines, final = read_new_lines(p, offset)
    assert lines == ["OUTPUT x"]
    assert final == p.stat().st_size


def test_partial_terminal_record_is_not_consumed(tmp_path):
    from courier_runtime.provider_events import read_new_lines

    p = tmp_path / "provider.log"
    p.write_bytes(b"IDLE\nTURN_ENDED outcome=DONE checkpoint=par")
    lines, offset = read_new_lines(p, 0)
    assert lines == ["IDLE"] and offset == len(b"IDLE\n")
    with p.open("ab") as handle:
        handle.write(b"tial-complete\n")
    lines, final = read_new_lines(p, offset)
    assert lines == ["TURN_ENDED outcome=DONE checkpoint=partial-complete"]
    assert final == p.stat().st_size
    assert read_new_lines(p, final) == ([], final)


def test_split_utf8_record_waits_for_its_complete_line(tmp_path):
    from courier_runtime.provider_events import read_new_lines

    p = tmp_path / "provider.log"
    p.write_bytes(b"HEARTBEAT checkpoint=\xc3")
    assert read_new_lines(p, 0) == ([], 0)
    with p.open("ab") as handle:
        handle.write(b"\xa4\n")
    assert read_new_lines(p, 0) == (["HEARTBEAT checkpoint=ä"], p.stat().st_size)


def test_invalid_utf8_terminal_record_cannot_complete_work(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    ev.handle(k, "s1", "IDLE")
    k.deliver("s1")
    p = tmp_path / "provider.log"
    p.write_bytes(b"TURN_ENDED outcome=DONE checkpoint=\xff\nHEARTBEAT\n")
    lines, offset = ev.read_new_lines(p, 0)
    assert ev.drive(k, "s1", lines) == ["IGNORED", "HEARTBEAT"]
    assert k.workkeys["W1"].state != DONE and offset == p.stat().st_size


def test_replayed_done_line_never_completes(tmp_path):
    # A provider line that merely contains the journal text is not a receipt.
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    ev.handle(k, "s1", "IDLE")
    assert k.deliver("s1") == "W1"
    line = "TURN_ENDED outcome=DONE checkpoint=step1 | journal:1:RESULT_ACCEPTED"
    assert ev.drive(k, "s1", [line]) == ["NOT_PROVEN"]
    assert k.workkeys["W1"].state != DONE
    assert k.counters["completions"] == 0
    assert ev.drive(k, "s1", [line]) == ["NOT_PROVEN"]
    assert k.workkeys["W1"].state != DONE
