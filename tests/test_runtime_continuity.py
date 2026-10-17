"""Provider continuity / Kirby: the user is not the Continue button."""
import json

import pytest

from courier_runtime.continuity import (BLOCKED, DONE, RETIRED, SNAPSHOT_EVERY_S, WAITING_FOR_USER, WAKE_PENDING,
                                        WORKING, Kirby, concurrency_advice, saturation_signal)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class World:
    """Fake host: which (pid, create_time) are alive, what got terminated, sessions started."""
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
    clock, world = Clock(), World()
    k = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity, terminate=world.terminate,
              start_session=world.start, clock=clock, **kw)
    return k, clock, world


def run_turn(k, slot, outcome="DONE", checkpoint="", reason=""):
    key = k.deliver(slot)
    return key, k.on_turn_end(slot, outcome, k.sessions[slot].token, checkpoint or f"ckpt-{key}", reason)


def test_25_sequential_workkeys_without_any_manual_continue(tmp_path):
    k, clock, _ = kirby(tmp_path)
    k.add_workkeys([f"W{i:02d}" for i in range(25)])
    k.open_slot("antigravity-1", "antigravity")
    assert k.wake("antigravity-1") == WAKE_PENDING                 # the one initial start
    done = []
    while k.sessions["antigravity-1"].state == WAKE_PENDING:
        clock.t += 30
        key, _ = run_turn(k, "antigravity-1")
        done.append(key)
    assert len(done) == 25 and all(k.workkeys[w].state == DONE for w in done)
    assert k.counters["manual_continue"] == 0 and k.user_state() == "DONE"


def test_blocked_workkey_parks_and_session_moves_on(tmp_path):
    k, _, _ = kirby(tmp_path)
    k.add_workkeys(["needs-credential"], priority=1)
    k.add_workkeys(["W2", "W3"])
    k.open_slot("s1", "antigravity")
    k.wake("s1")
    key, nxt = run_turn(k, "s1", "BLOCKED", reason="missing API credential")
    assert key == "needs-credential" and nxt == WAKE_PENDING
    assert k.workkeys["needs-credential"].state == BLOCKED
    run_turn(k, "s1")
    _, last = run_turn(k, "s1")
    assert last == WAITING_FOR_USER and k.user_state() == "NEEDS YOU"   # only now, nothing else left


def test_duplicate_wakes_coalesce_to_one_pending(tmp_path):
    k, _, _ = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    k.open_slot("s1", "muse")
    results = [k.wake("s1") for _ in range(5)]
    assert results == [WAKE_PENDING] + ["COALESCED"] * 4
    assert sum(w.owner == "s1-g1" for w in k.workkeys.values()) == 1    # only W1 claimed


def test_100_continuation_intents_are_one_execution(tmp_path):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    results = [k.wake("s1", manual=True) for _ in range(100)]
    assert set(results) == {"COALESCED"} and k.counters["coalesced"] == 100
    assert len(world.started) == 1 and k.sessions["s1"].state == WORKING


def test_saturation_rotates_once_and_successor_resumes_from_checkpoint(tmp_path):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    k.heartbeat("s1", progress=True, checkpoint="W1:step-7")
    old = k.sessions["s1"]
    r1 = k.on_provider_output("s1", "context compaction failed: hard_threshold_failed", checkpoint="W1:step-8")
    r2 = k.rotate("s1", "repeated signal")                    # second signal on the new session's slot...
    assert r1["kind"] == "ROTATE" and len(world.started) == 3 and r2["kind"] == "ROTATE"
    # ...is a real second rotation of the NEW session; the OLD one can never be replaced twice:
    k2 = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity, start_session=world.start)
    assert old.session_id in [json.loads(l)["session_id"] for l in (tmp_path / "retired.jsonl").read_text().splitlines()]
    new = k2.sessions["s1"]
    assert new.workkey == "W1" and k2.workkeys["W1"].checkpoint == "W1:step-8"   # resumed, not restarted
    assert new.state == WAKE_PENDING and k2.workkeys["W2"].state == "OPEN"


def test_old_session_cannot_be_replaced_twice(tmp_path):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    first = k.recover("s1", "stall")
    retired = json.loads((tmp_path / "retired.jsonl").read_text().splitlines()[0])
    assert retired["state"] == RETIRED and retired["successor"] == first["new_session"]
    assert len(world.started) == 2


@pytest.mark.parametrize("receipt", [
    {"result": "ORPHANS_REMAIN", "still_alive": [2000]},
    {"result": "STOPPED", "still_alive": [2000]},
    {"result": "NOT_RUNNING"},
    {"result": "NONE"},
    {},
])
def test_unproven_cleanup_never_launches_successor(tmp_path, receipt):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    old = k.sessions["s1"]
    k.terminate = lambda s: receipt

    result = k.rotate("s1", "context pressure", checkpoint="W1:step-8")

    assert result["action"] == "RECOVERY_BLOCKED"
    assert world.started == [("s1", 1)]
    assert k.sessions["s1"].session_id == old.session_id
    assert k.workkeys["W1"].owner == old.session_id
    assert k.workkeys["W1"].checkpoint == "W1:step-8"
    assert k.workkeys["W2"].state == "OPEN"
    assert k.on_turn_end("s1", "DONE", old.token) == "REJECTED_STALE_WRITER"
    assert k.deliver("s1") is None
    assert k.recover("s1", "repeat")["action"] == "RECOVERY_BLOCKED"

    restored = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity,
                     terminate=world.terminate, start_session=world.start)
    assert restored.reconcile_after_restart() == {"s1": "RECOVERY_BLOCKED"}
    assert restored.wake("s1") == "COALESCED"
    assert restored.deliver("s1") is None
    assert restored.user_state() == "NEEDS YOU"
    assert len(world.started) == 1


@pytest.mark.parametrize("failing_hook", ["terminate", "start_session"])
def test_recovery_checkpoint_precedes_external_effects(tmp_path, failing_hook):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")

    def crash(*args):
        state = json.loads((tmp_path / "kirby.json").read_text())
        assert state["sessions"]["s1"]["state"] == "RECOVERING"
        assert state["sessions"]["s1"]["accepting"] is False
        assert state["workkeys"]["W1"]["checkpoint"] == "accepted-step-8"
        if failing_hook == "start_session":
            world.start(*args)  # the launch happened, but its response was lost
        raise RuntimeError("injected uncertain recovery")

    setattr(k, failing_hook, crash)
    with pytest.raises(RuntimeError, match="injected uncertain recovery"):
        k.rotate("s1", "context pressure", checkpoint="accepted-step-8")
    restored = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity,
                     terminate=world.terminate, start_session=world.start)
    assert restored.reconcile_after_restart() == {"s1": "RECOVERY_BLOCKED"}
    assert len(world.started) == (2 if failing_hook == "start_session" else 1)


def test_checkpoint_sync_failure_prevents_cleanup_and_launch(tmp_path, monkeypatch):
    from courier_runtime import continuity

    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")

    def fail_sync(fd):
        raise OSError("checkpoint storage unavailable")

    monkeypatch.setattr(continuity.os, "fsync", fail_sync)
    with pytest.raises(OSError, match="checkpoint storage unavailable"):
        k.rotate("s1", "context pressure", checkpoint="accepted-step-8")
    assert world.terminated == []
    assert len(world.started) == 1
    assert list(tmp_path.glob(".kirby.*")) == []


def fenced_kirby(tmp_path):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    k.terminate = lambda s: {"result": "ORPHANS_REMAIN", "still_alive": [2000]}
    k.rotate("s1", "context pressure", checkpoint="accepted-step-8")
    return k, world


def recovery_proof(context):
    return {"session_id": context["session"]["session_id"], "token": context["session"]["token"],
            "workkey": context["workkey"]["key"] if context["workkey"] else "",
            "cleanup": "STOPPED", "still_alive": [],
            "resume_safe": True, "evidence": ["accepted-reconciliation-8"]}


def test_fenced_slot_repeat_blocks_have_complete_audit_receipts(tmp_path):
    k, world = fenced_kirby(tmp_path)
    k.rotate("s1", "repeat one")
    k.recover("s1", "repeat two")
    receipts = [json.loads(line) for line in (tmp_path / "recovery_receipts.jsonl").read_text().splitlines()]
    assert len(receipts) == 3
    assert all(set(r) == set(receipts[0]) for r in receipts)
    assert [r["cleanup"] for r in receipts] == ["ORPHANS_REMAIN", "ALREADY_FENCED", "ALREADY_FENCED"]
    assert len(world.started) == 1


@pytest.mark.parametrize("invalid", [
    {"cleanup": "ORPHANS_REMAIN"}, {"still_alive": [2000]}, {"resume_safe": False},
    {"token": 999}, {"token": True}, {"session_id": "foreign"},
    {"workkey": "other"}, {"evidence": []}, {"evidence": [""]},
])
def test_recovery_resolution_rejects_unbound_or_uncertain_proof(tmp_path, invalid):
    k, world = fenced_kirby(tmp_path)
    old = k.sessions["s1"]
    k.authorize_recovery = lambda context: True
    k.reconcile_recovery = lambda context: {**recovery_proof(context), **invalid}
    result = k.resolve_recovery("s1", session_id=old.session_id, token=old.token, actor="operator")
    assert result["action"] == "RECOVERY_BLOCKED"
    assert len(world.started) == 1
    assert k.deliver("s1") is None


def test_recovery_resolution_requires_current_authority(tmp_path):
    k, world = fenced_kirby(tmp_path)
    old = k.sessions["s1"]
    k.reconcile_recovery = lambda context: pytest.fail("no reconciliation without authority")
    result = k.resolve_recovery("s1", session_id=old.session_id, token=old.token, actor="operator")
    assert result["cleanup"] == "UNAUTHORIZED"
    assert len(world.started) == 1


def test_recovery_resolution_resumes_once_from_verified_checkpoint(tmp_path):
    k, world = fenced_kirby(tmp_path)
    old = k.sessions["s1"]
    k.authorize_recovery = lambda context: context["actor"] == "operator"

    def reconcile(context):
        world.alive.clear()  # independently confirmed no owned predecessor/successor survives
        return recovery_proof(context)

    k.reconcile_recovery = reconcile
    result = k.resolve_recovery("s1", session_id=old.session_id, token=old.token, actor="operator")
    assert result["cleanup"] == "RECONCILED"
    assert result["actor"] == "operator" and result["evidence"] == ["accepted-reconciliation-8"]
    assert len(world.started) == 2
    assert k.sessions["s1"].state == WAKE_PENDING
    assert k.workkeys["W1"].owner == k.sessions["s1"].session_id
    assert k.workkeys["W1"].checkpoint == "accepted-step-8"
    assert k.resolve_recovery("s1", session_id=old.session_id, token=old.token,
                              actor="operator") == "REJECTED_STALE_WRITER"
    assert len(world.started) == 2


def test_recovery_resolution_rechecks_fence_after_hooks(tmp_path):
    k, world = fenced_kirby(tmp_path)
    old = k.sessions["s1"]
    k.authorize_recovery = lambda context: True

    def reconcile(context):
        k.workkeys["W1"].token += 1  # ownership changed while reconciliation was in progress
        return recovery_proof(context)

    k.reconcile_recovery = reconcile
    assert k.resolve_recovery("s1", session_id=old.session_id, token=old.token,
                              actor="operator") == "REJECTED_STALE_WRITER"
    assert len(world.started) == 1


def test_recovery_authority_uses_existing_broker_and_revocation(tmp_path):
    from courier_runtime.grants import Broker, Request

    k, world = fenced_kirby(tmp_path)
    old = k.sessions["s1"]
    broker = Broker(k.clock)
    request = Request("reconcile-s1", "courier", "reconcile_recovery",
                      frozenset({"session:" + old.session_id, "workkey:W1"}),
                      k.host, old.provider, "project", "control", "non_idempotent")
    broker.authorize(request)
    broker.grant(request, "recovery-grant", expires_at=k.clock() + 60, granted_by="operator")

    def authorize(context):
        grant, _, _ = broker.authorize(request)
        return grant is not None and grant.granted_by == context["actor"]

    k.authorize_recovery = authorize
    k.reconcile_recovery = lambda context: pytest.fail("revoked grants must prevent reconciliation")
    broker.revoke("recovery-grant")
    result = k.resolve_recovery("s1", session_id=old.session_id, token=old.token, actor="operator")
    assert result["cleanup"] == "UNAUTHORIZED"
    assert len(world.started) == 1


def test_recovery_authority_is_not_restored_from_checkpoint(tmp_path):
    k, world = fenced_kirby(tmp_path)
    k.authorize_recovery = lambda context: True
    k.reconcile_recovery = recovery_proof
    old = k.sessions["s1"]
    restored = Kirby(tmp_path / "kirby.json", "mac-1", start_session=world.start)
    result = restored.resolve_recovery("s1", session_id=old.session_id, token=old.token, actor="operator")
    assert result["cleanup"] == "UNAUTHORIZED"
    assert len(world.started) == 1


def test_recovery_resolution_of_idle_slot_does_not_invent_work(tmp_path):
    k, _, world = kirby(tmp_path)
    old = k.open_slot("s1", "muse")
    k.terminate = lambda s: {"result": "ORPHANS_REMAIN", "still_alive": [2000]}
    k.rotate("s1", "idle context pressure")
    k.authorize_recovery = lambda context: True

    def reconcile(context):
        assert context["workkey"] is None
        world.alive.clear()
        return recovery_proof(context)

    k.reconcile_recovery = reconcile
    result = k.resolve_recovery("s1", session_id=old.session_id, token=old.token, actor="operator")
    assert result["cleanup"] == "RECONCILED"
    assert len(world.started) == 2
    assert k.sessions["s1"].workkey == "" and k.deliver("s1") is None
    assert k.workkeys == {}


def test_no_duplicate_writer_after_rotation(tmp_path):
    k, _, _ = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    stale_token = k.sessions["s1"].token
    k.rotate("s1", "hard_threshold_failed")
    assert k.workkeys["W1"].owner == k.sessions["s1"].session_id
    # the old session's late turn-end carries the old token and is refused
    assert k.on_turn_end("s1", "DONE", stale_token) == "REJECTED_STALE_WRITER"
    assert k.workkeys["W1"].state == "CLAIMED"


def test_reopened_archived_slot_never_reuses_retired_session_identity(tmp_path):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    first = k.open_slot("s1", "muse")
    world.alive.pop(first.pid)                              # executor died idle
    assert k.reconcile_after_restart() == {"s1": "ARCHIVED_STALE"}
    second = k.open_slot("s1", "muse")                      # same slot, later
    assert second.session_id != first.session_id
    assert second.generation == first.generation + 1
    assert len(world.started) == 2
    # the retired identity can never own new work: a stale owner string matches nothing live
    assert all(w.owner != first.session_id for w in k.workkeys.values())


def test_stalled_provider_detected_by_fast_tick_not_after_15_minutes(tmp_path):
    k, clock, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "antigravity")
    k.wake("s1")
    k.deliver("s1")
    old_pid = k.sessions["s1"].pid
    world.alive.pop(old_pid)                                  # provider process died
    clock.t += 60                                             # one fast tick later
    actions = k.tick()
    assert actions["s1"]["kind"] == "RECOVER" and k.sessions["s1"].workkey == "W1"
    assert old_pid not in world.terminated                    # it was already gone: nothing signalled


def test_long_quiet_task_is_not_killed_and_one_weak_signal_only_investigates(tmp_path):
    k, clock, world = kirby(tmp_path)
    k.add_workkeys(["build"])
    k.open_slot("s1", "muse", activity="build")
    k.wake("s1")
    k.deliver("s1")
    clock.t += 170                                            # quiet, but within the build grace
    assert k.tick() == {}
    clock.t += 30                                             # heartbeat now missed, process alive, progress ok
    assert k.tick()["s1"]["action"] == "INVESTIGATE" and world.terminated == []


def test_hung_but_alive_executor_is_terminated_by_identity_and_replaced_once(tmp_path):
    k, clock, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    pid = k.sessions["s1"].pid
    clock.t += 1000                                           # no heartbeat, no progress, process alive
    k.tick()
    k.tick()                                                  # repeated recovery signal
    assert world.terminated == [pid] and len(world.started) == 2


def test_pid_reuse_is_never_terminated(tmp_path):
    k, clock, world = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    pid = k.sessions["s1"].pid
    world.alive[pid] = 99999.0                                # same pid, different (foreign) process
    clock.t += 60
    r = k.tick()["s1"]
    assert r["cleanup"] == "NOT_OWNED_OR_GONE" and world.terminated == [] and r["foreign_process_touched"] is False


def test_critical_snapshot_is_structured_evidence_every_15_minutes(tmp_path):
    k, clock, _ = kirby(tmp_path)
    k.add_workkeys(["W1"])
    k.open_slot("s1", "antigravity")
    k.wake("s1")
    k.deliver("s1")
    clock.t += SNAPSHOT_EVERY_S
    k.heartbeat("s1", progress=True)
    k.tick()
    snaps = (tmp_path / "snapshots.jsonl").read_text().splitlines()
    snap = json.loads(snaps[-1])
    assert len(snaps) == 1 and snap["evidence_only"] is True
    assert {"provider", "session_id", "pid", "state", "workkey", "checkpoint", "writer_token"} <= set(snap["sessions"][0])
    clock.t += 60
    k.tick()
    assert len((tmp_path / "snapshots.jsonl").read_text().splitlines()) == 1   # not before the next 15 min


def test_restart_leaves_no_ghost_sessions(tmp_path):
    k, _, world = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    for slot in ("a", "b", "c"):
        k.open_slot(slot, "muse")
    k.wake("a")
    k.deliver("a")
    k.wake("b")
    k.deliver("b")
    world.alive.pop(k.sessions["b"].pid)                       # b died with work
    world.alive.pop(k.sessions["c"].pid)                       # c died idle
    k2 = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity, terminate=world.terminate,
               start_session=world.start)
    assert k2.reconcile_after_restart() == {"a": "RESUMED", "b": "RECOVERED", "c": "ARCHIVED_STALE"}
    assert k2.sessions["b"].workkey == "W2" and k2.sessions["c"].state == RETIRED


def test_power_pool_distinct_slots_one_writer_each_and_bounded(tmp_path):
    k, _, _ = kirby(tmp_path, max_slots=12)
    k.add_workkeys([f"W{i}" for i in range(30)])
    for i in range(12):
        k.open_slot(f"muse-{i}", "muse")
        k.wake(f"muse-{i}")
    owners = [w.owner for w in k.workkeys.values() if w.owner]
    assert len(owners) == 12 == len(set(owners))
    claimed = [s.workkey for s in k.sessions.values()]
    assert len(set(claimed)) == 12
    with pytest.raises(RuntimeError):
        k.open_slot("muse-12", "muse")


def test_user_sees_recovering_then_working(tmp_path):
    k, clock, world = kirby(tmp_path)
    k.add_workkeys(["W1", "W2"])
    k.open_slot("s1", "muse")
    k.wake("s1")
    k.deliver("s1")
    assert k.user_state() == "WORKING"
    world.alive.pop(k.sessions["s1"].pid)
    clock.t += 60
    k.tick()
    k.deliver("s1")
    assert k.user_state() == "WORKING"                         # recovery was invisible


@pytest.mark.parametrize("text, pct, expected", [
    ("context compaction failed: hard_threshold_failed", None, "hard_threshold_failed"),
    ("Turn-submit backlog full (4)", None, "turn-submit backlog full"),
    ("all good", 95.0, "context pressure 95%"),
    ("all good", None, None),
])
def test_saturation_needs_a_real_signal_not_a_prompt_count(text, pct, expected):
    assert saturation_signal(text, pct) == expected


def test_concurrency_advice_scales_down_when_more_slots_stop_helping():
    windows = [{"slots": 8, "completions_per_h": 20, "errors": 0, "ram_pct": 60},
               {"slots": 12, "completions_per_h": 22, "errors": 1, "ram_pct": 78},
               {"slots": 16, "completions_per_h": 18, "errors": 5, "ram_pct": 92}]
    assert concurrency_advice(windows)["slots"] == 12
    assert concurrency_advice([{"slots": 12, "completions_per_h": 5, "errors": 9, "ram_pct": 95}])["slots"] == 6


def test_real_hung_child_is_recovered_with_ownership_identity(tmp_path):
    """End to end with a real process and the real ownership module."""
    import subprocess
    import sys

    import psutil

    from courier_runtime.ownership import OwnedProcess, is_same_process, terminate_owned
    procs = []

    def start(slot, gen):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        procs.append(p)
        return f"{slot}-g{gen}", p.pid, psutil.Process(p.pid).create_time()

    def ident(s):
        return is_same_process(OwnedProcess(s.pid, s.create_time, s.workkey, "courier", 0.0))

    clock = Clock()
    k = Kirby(tmp_path / "k.json", "host", identity=ident,
              terminate=lambda s: terminate_owned(OwnedProcess(s.pid, s.create_time, s.workkey, "courier", 0.0)),
              start_session=start, clock=clock)
    try:
        k.add_workkeys(["W1"])
        k.open_slot("s1", "muse")
        k.wake("s1")
        k.deliver("s1")
        clock.t += 2000
        receipt = k.tick()["s1"]
        procs[0].wait(timeout=10)
        assert receipt["cleanup"] == "STOPPED" and procs[0].returncode is not None
        assert procs[1].poll() is None and k.sessions["s1"].workkey == "W1"
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.wait()
