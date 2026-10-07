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


def test_20_turn_ended_lines_complete_campaign_without_manual_continue(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    k.add_workkeys([f"W{i:02d}" for i in range(20)])
    k.open_slot("antigravity-1", "antigravity")
    assert ev.drive(k, "antigravity-1", ["IDLE"]) == [WAKE_PENDING]
    for _ in range(20):
        assert k.deliver("antigravity-1") is not None
        ev.drive(k, "antigravity-1", ["TURN_ENDED outcome=DONE checkpoint=step-done"])
    assert all(w.state == DONE for w in k.workkeys.values())
    assert k.counters["manual_continue"] == 0 and k.user_state() == "DONE"


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
    ev.drive(k, "s1", ["TURN_ENDED outcome=DONE"])
    assert k.workkeys["W2"].state == DONE


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
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=DONE"]) == ["IDLE"]          # claim held: completed, nothing left
    assert k.workkeys["W1"].state == DONE and k.counters["completions"] == 1
    assert ev.drive(k, "s1", ["TURN_ENDED outcome=DONE"]) == ["IDLE"]          # nothing claimed: reconcile only


def test_ingress_to_unknown_slot_is_ignored(tmp_path):
    k, _, _, ev = kirby(tmp_path)
    assert ev.drive(k, "nope", ["IDLE", "TURN_ENDED outcome=DONE"]) == ["IGNORED_NO_SLOT"] * 2


def test_read_new_lines_is_incremental(tmp_path):
    from courier_runtime import provider_events

    p = tmp_path / "provider.log"
    p.write_text("IDLE\nTURN_ENDED outcome=DONE\n", encoding="utf-8")
    lines, off = provider_events.read_new_lines(p, 0)
    assert lines == ["IDLE", "TURN_ENDED outcome=DONE"]
    p.write_text("IDLE\nTURN_ENDED outcome=DONE\nOUTPUT x\n", encoding="utf-8")
    lines, _ = provider_events.read_new_lines(p, off)
    assert lines == ["OUTPUT x"]
