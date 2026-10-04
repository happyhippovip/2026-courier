"""Host loop: provider signal FILE -> Kirby -> exactly-one wake notice.

Proves the production wiring (not just direct Kirby calls): lines appended
to a signal file advance the campaign with zero manual Continue, duplicate
lines coalesce, the fast tick runs on cadence (not per line), and no line
ever opens a window or spawns a process (world.started only grows when a
rotation/recovery legitimately starts exactly one successor).
"""
from courier_runtime.continuity import DONE, WAKE_PENDING, Kirby
from courier_runtime.host_loop import run_once


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


def setup(tmp_path, keys, slot="antigravity-1", provider="antigravity", **kw):
    clock, world = Clock(), World()
    k = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity, terminate=world.terminate,
              start_session=world.start, clock=clock, **kw)
    k.add_workkeys(keys)
    k.open_slot(slot, provider)
    signals = tmp_path / "provider.signals"
    signals.write_text("", encoding="utf-8")
    return k, clock, world, signals, {"offset": 0, "last_tick": 0.0, "notified": {}}


def append(signals, *lines):
    with open(signals, "a", encoding="utf-8") as f:
        f.write("".join(l + "\n" for l in lines))


def test_20_turn_ends_through_file_complete_campaign_unaided(tmp_path):
    k, _, world, signals, state = setup(tmp_path, [f"W{i:02d}" for i in range(20)])
    append(signals, "IDLE")
    results, _, notices = run_once(k, "antigravity-1", signals, state)
    assert results == [WAKE_PENDING] and len(notices) == 1
    for _ in range(20):
        assert k.deliver("antigravity-1") is not None        # provider lane turns the wake into work
        append(signals, "TURN_ENDED outcome=DONE checkpoint=step-done")
        run_once(k, "antigravity-1", signals, state)
    assert all(w.state == DONE for w in k.workkeys.values())
    assert k.counters["manual_continue"] == 0 and k.user_state() == "DONE"
    assert len(world.started) == 1                            # zero new sessions: work != window
    assert len((tmp_path / "wakeups.jsonl").read_text().splitlines()) == 20


def test_100_idle_lines_through_file_are_one_execution(tmp_path):
    k, _, world, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    append(signals, "IDLE")
    _, _, notices = run_once(k, "s1", signals, state)
    assert len(notices) == 1
    k.deliver("s1")
    append(signals, *["IDLE"] * 100)
    results, _, notices = run_once(k, "s1", signals, state)
    assert results == ["COALESCED"] * 100 and notices == []
    assert len(world.started) == 1 and k.sessions["s1"].state == "WORKING"
    assert len((tmp_path / "wakeups.jsonl").read_text().splitlines()) == 1


def test_blocked_line_parks_workkey_and_next_wake_is_noticed_once(tmp_path):
    k, _, _, signals, state = setup(tmp_path, ["W2"], slot="s1", provider="muse")
    k.add_workkeys(["needs-credential"], priority=1)
    append(signals, "IDLE")
    run_once(k, "s1", signals, state)
    assert k.deliver("s1") == "needs-credential"
    append(signals, "TURN_ENDED outcome=BLOCKED reason=missing credential")
    results, _, notices = run_once(k, "s1", signals, state)
    assert results == [WAKE_PENDING] and len(notices) == 1   # the W2 continuation, not a repeat
    assert k.workkeys["needs-credential"].state == "BLOCKED"
    assert k.deliver("s1") == "W2"


def test_saturation_line_through_file_rotates_exactly_one_successor(tmp_path):
    k, _, world, signals, state = setup(tmp_path, ["W1", "W2"], slot="s1", provider="muse")
    append(signals, "IDLE")
    run_once(k, "s1", signals, state)
    k.deliver("s1")
    append(signals, "HEARTBEAT progress=1 checkpoint=W1:step-8")
    run_once(k, "s1", signals, state)
    append(signals, "OUTPUT context compaction failed: hard_threshold_failed")
    results, _, notices = run_once(k, "s1", signals, state)
    assert results == ["ROTATED"] and len(world.started) == 2
    assert k.sessions["s1"].workkey == "W1" and k.workkeys["W1"].checkpoint == "W1:step-8"
    assert len(notices) == 1                                  # successor's pending wake noticed once
    stale = k.sessions["s1"].token - 1
    assert k.on_turn_end("s1", "DONE", stale) == "REJECTED_STALE_WRITER"   # old writer stays fenced


def test_tick_runs_on_cadence_not_per_line(tmp_path):
    k, clock, _, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    append(signals, "IDLE")
    run_once(k, "s1", signals, state)
    first_tick = state["last_tick"]
    append(signals, "HEARTBEAT")
    _, actions, _ = run_once(k, "s1", signals, state)
    assert actions == {} and state["last_tick"] == first_tick   # 0 s later: no tick
    clock.t += 30
    run_once(k, "s1", signals, state)
    assert state["last_tick"] == first_tick                     # 30 s: still no tick
    clock.t += 15
    run_once(k, "s1", signals, state)
    assert state["last_tick"] > first_tick                      # 45 s: fast fallback ran


def test_16_quiet_minutes_produce_exactly_one_evidence_snapshot(tmp_path):
    import json

    k, clock, _, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    for _ in range(20):                                       # 20 x 45 s = 15 quiet minutes
        clock.t += 45
        run_once(k, "s1", signals, state)
    snaps = (tmp_path / "snapshots.jsonl").read_text().splitlines()
    assert len(snaps) == 1 and json.loads(snaps[0])["evidence_only"] is True


def test_missing_and_truncated_signal_file_are_fail_closed(tmp_path):
    k, clock, _, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    signals.unlink()
    results, _, _ = run_once(k, "s1", signals, state)         # no file: no crash, tick still runs
    assert results == [] and state["last_tick"] == clock.t
    signals.write_text("IDLE\n", encoding="utf-8")
    results, _, _ = run_once(k, "s1", signals, state)
    assert results == [WAKE_PENDING]
    signals.write_text("", encoding="utf-8")                  # rotation to empty: offset resets
    results, _, _ = run_once(k, "s1", signals, state)
    assert results == []
    append(signals, "HEARTBEAT")
    results, _, _ = run_once(k, "s1", signals, state)
    assert results == ["HEARTBEAT"]


def test_lines_for_unknown_slot_are_ignored(tmp_path):
    k, _, world, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    results, _, notices = run_once(k, "nope", signals, state)
    assert results == [] and notices == []                    # empty file: nothing to misroute
    append(signals, "IDLE", "TURN_ENDED outcome=DONE")
    results, _, notices = run_once(k, "nope", signals, state)
    assert results == ["IGNORED_NO_SLOT"] * 2 and notices == []
    assert len(world.started) == 1 and all(w.state == "OPEN" for w in k.workkeys.values())
