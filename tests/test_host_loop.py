"""Host loop: provider signal FILE -> Kirby -> exactly-one wake notice.

Proves the production wiring (not just direct Kirby calls): lines appended
to a signal file advance the campaign with zero manual Continue, duplicate
lines coalesce, the fast tick runs on cadence (not per line), and no line
ever opens a window or spawns a process (world.started only grows when a
rotation/recovery legitimately starts exactly one successor).
"""
from courier_runtime.continuity import DONE, WAKE_PENDING, Kirby
from courier_runtime.host_loop import drain_pending, emit_signal, run_once


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


def test_drain_pending_hands_single_wake_to_provider_once(tmp_path):
    k, _, world, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    assert drain_pending(k, "s1") is None                     # nothing pending yet
    append(signals, "IDLE")
    run_once(k, "s1", signals, state)
    assert drain_pending(k, "s1") == "W1"                      # one wake -> one execution
    assert drain_pending(k, "s1") is None                     # already WORKING: no second execution
    assert k.sessions["s1"].state == "WORKING"
    assert drain_pending(k, "nope") is None                   # unknown slot: no crash
    assert len(world.started) == 1                            # taking a wake never spawns


def test_emit_signal_appends_exact_lines(tmp_path):
    _, _, _, signals, _ = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    signals.unlink()
    assert emit_signal(signals, "IDLE") == "IDLE"
    assert emit_signal(signals, "TURN_ENDED outcome=DONE") == "TURN_ENDED outcome=DONE"
    assert signals.read_text(encoding="utf-8") == "IDLE\nTURN_ENDED outcome=DONE\n"


def test_full_chain_emit_notice_drain_turn_end_advances_unaided(tmp_path):
    k, _, world, signals, state = setup(tmp_path, ["W0", "W1"], slot="s1", provider="muse")
    emit_signal(signals, "IDLE")
    _, _, notices = run_once(k, "s1", signals, state)
    assert (len(notices), drain_pending(k, "s1")) == (1, "W0")
    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=step-done")
    results, _, notices = run_once(k, "s1", signals, state)
    assert results == [WAKE_PENDING] and len(notices) == 1
    assert drain_pending(k, "s1") == "W1"
    assert k.workkeys["W0"].state == DONE and k.counters["manual_continue"] == 0
    assert len(world.started) == 1


def test_lines_for_unknown_slot_are_ignored(tmp_path):
    k, _, world, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="muse")
    results, _, notices = run_once(k, "nope", signals, state)
    assert results == [] and notices == []                    # empty file: nothing to misroute
    append(signals, "IDLE", "TURN_ENDED outcome=DONE")
    results, _, notices = run_once(k, "nope", signals, state)
    assert results == ["IGNORED_NO_SLOT"] * 2 and notices == []
    assert len(world.started) == 1 and all(w.state == "OPEN" for w in k.workkeys.values())


def test_v75_scenario_a_two_consecutive_ready_tasks_with_verifier_and_dependencies(tmp_path):
    """Scenario A: Task A READY -> Worker gets A -> Result -> Verifier confirms ->
    Ledger stores DONE -> Task B (depends_on A) becomes READY -> Courier selects and delivers B once."""
    from courier_runtime.host_loop import run_until_idle

    verified = []
    dispatched = []
    k, _, world, signals, state = setup(
        tmp_path,
        [{"key": "TaskA", "priority": 10}, {"key": "TaskB", "priority": 20, "depends_on": ["TaskA"]}],
        slot="s1",
        provider="antigravity",
        verifier=lambda key, ckpt, sess: verified.append((key, ckpt)) or ckpt.startswith("verified:"),
    )
    assert [w.key for w in k.ready_workkeys()] == ["TaskA"]

    def adapter(slot, workkey, session):
        dispatched.append((workkey, session.token))
        emit_signal(
            signals,
            f"TURN_ENDED workkey={workkey} token={session.token} result_id=res-{workkey} outcome=DONE checkpoint=verified:{workkey}",
        )

    emit_signal(signals, "IDLE")
    run_until_idle(k, "s1", signals, state, dispatch=adapter)

    assert dispatched == [("TaskA", 1), ("TaskB", 2)]
    assert verified == [("TaskA", "verified:TaskA"), ("TaskB", "verified:TaskB")]
    assert k.workkeys["TaskA"].state == DONE and k.workkeys["TaskB"].state == DONE
    assert k.counters["manual_continue"] == 0 and len(world.started) == 1


def test_v75_scenario_b_ten_sequential_ready_tasks_zero_manual_refill(tmp_path):
    """Scenario B: 10 sequential READY tasks execute without manual refill."""
    from courier_runtime.host_loop import _queue_idle, run_until_idle

    keys = [f"T{i:02d}" for i in range(10)]
    dispatched = []
    k, _, world, signals, state = setup(tmp_path, keys, slot="s1", provider="antigravity")

    def adapter(slot, workkey, session):
        dispatched.append(workkey)
        emit_signal(
            signals,
            f"TURN_ENDED workkey={workkey} token={session.token} outcome=DONE checkpoint=done-{workkey}",
        )

    emit_signal(signals, "IDLE")
    run_until_idle(k, "s1", signals, state, dispatch=adapter)

    assert dispatched == keys
    assert all(k.workkeys[key].state == DONE for key in keys)
    assert k.counters["manual_continue"] == 0 and k.counters["completions"] == 10
    assert _queue_idle(k) is True and len(world.started) == 1


def test_v75_scenario_c_provider_turn_ends_after_task_3_and_resumes_to_completion(tmp_path):
    """Scenario C: Provider turn ends after Task 3; Courier automatically wakes and dispatches Tasks 4..10."""
    from courier_runtime.host_loop import run_until_idle

    keys = [f"T{i:02d}" for i in range(10)]
    dispatched = []
    k, _, world, signals, state = setup(tmp_path, keys, slot="s1", provider="muse")

    # Turn 1 executes 3 tasks (T00, T01, T02) and then the provider turn ends
    def adapter(slot, workkey, session):
        dispatched.append(workkey)
        emit_signal(
            signals,
            f"TURN_ENDED workkey={workkey} token={session.token} outcome=DONE checkpoint=done-{workkey}",
        )

    emit_signal(signals, "IDLE")
    run_once(k, "s1", signals, state, dispatch=adapter)  # T00 dispatched
    run_once(k, "s1", signals, state, dispatch=adapter)  # T00 DONE -> T01 dispatched
    run_once(k, "s1", signals, state, dispatch=adapter)  # T01 DONE -> T02 (Task 3) dispatched & emits TURN_ENDED
    assert dispatched == ["T00", "T01", "T02"]

    # After Task 3's provider turn ends, Courier automatically continues T03..T09 without manual refill
    run_until_idle(k, "s1", signals, state, dispatch=adapter)

    assert dispatched == keys
    assert all(k.workkeys[key].state == DONE for key in keys)
    assert k.counters["manual_continue"] == 0 and len(world.started) == 1


def test_v75_scenario_d_controlled_courier_process_stop_and_restart(tmp_path):
    """Scenario D: Courier process stops mid-campaign and restarts cleanly from persisted offset without replaying signals."""
    from courier_runtime.host_loop import load_loop_state, run_until_idle

    dispatched = []
    k, clock, world, signals, state = setup(tmp_path, ["W1", "W2", "W3", "W4"], slot="s1", provider="muse")

    def step_adapter(slot, workkey, session):
        dispatched.append((workkey, session.session_id, session.token))

    emit_signal(signals, "IDLE")
    run_once(k, "s1", signals, state, dispatch=step_adapter)  # claims & dispatches W1
    emit_signal(signals, f"TURN_ENDED workkey=W1 token={k.sessions['s1'].token} outcome=DONE checkpoint=W1-ok")
    run_once(k, "s1", signals, state, dispatch=step_adapter)  # completes W1, claims & dispatches W2
    assert [d[0] for d in dispatched] == ["W1", "W2"]

    # Controlled stop & restart of Courier supervisor + host_loop
    k2 = Kirby(tmp_path / "kirby.json", "mac-1", identity=world.identity, terminate=world.terminate,
               start_session=world.start, clock=clock)
    assert k2.reconcile_after_restart() == {"s1": "RESUMED"}
    state2 = load_loop_state(k2)
    assert state2["offset"] == state["offset"] > 0

    def auto_adapter(slot, workkey, session):
        dispatched.append((workkey, session.session_id, session.token))
        emit_signal(signals, f"TURN_ENDED workkey={workkey} token={session.token} outcome=DONE checkpoint={workkey}-ok")

    # Re-running with no new signal does NOT replay W1/W2
    run_once(k2, "s1", signals, state2, dispatch=auto_adapter)
    assert [d[0] for d in dispatched] == ["W1", "W2"]

    # Now W2 completes -> W3 and W4 automatically dispatch and complete
    emit_signal(signals, f"TURN_ENDED workkey=W2 token={k2.sessions['s1'].token} outcome=DONE checkpoint=W2-ok")
    run_until_idle(k2, "s1", signals, state2, dispatch=auto_adapter)

    assert [d[0] for d in dispatched] == ["W1", "W2", "W3", "W4"]
    assert all(w.state == DONE for w in k2.workkeys.values())


def test_v75_scenario_e_worker_available_after_reconnect(tmp_path):
    """Scenario E: Worker disconnects while idle (ARCHIVED_STALE), then reconnects and resumes READY work."""
    from courier_runtime.host_loop import run_until_idle

    dispatched = []
    k, _, world, signals, state = setup(tmp_path, ["W1", "W2"], slot="s1", provider="antigravity")
    world.alive.pop(k.sessions["s1"].pid)
    assert k.reconcile_after_restart() == {"s1": "ARCHIVED_STALE"}
    assert k.sessions["s1"].state == "RETIRED"

    def adapter(slot, workkey, session):
        dispatched.append((workkey, session.session_id))
        emit_signal(signals, f"TURN_ENDED workkey={workkey} token={session.token} outcome=DONE checkpoint={workkey}-ok")

    emit_signal(signals, "RECONNECTED")
    run_until_idle(k, "s1", signals, state, dispatch=adapter)

    assert dispatched == [("W1", "s1-g2"), ("W2", "s1-g2")]
    assert all(w.state == DONE for w in k.workkeys.values())


def test_v75_scenario_f_duplicate_confirmed_result_never_causes_false_done(tmp_path):
    """Scenario F: Duplicate arrival of an already confirmed Result never marks the next task DONE."""
    k, _, _, signals, state = setup(tmp_path, ["TaskA", "TaskB"], slot="s1", provider="muse")
    emit_signal(signals, "IDLE")
    run_once(k, "s1", signals, state)
    assert drain_pending(k, "s1") == "TaskA"
    tok_a = k.sessions["s1"].token

    # TaskA finishes, and a duplicate TURN_ENDED arrives both un-tagged (while TaskB is WAKE_PENDING)
    # and tagged with TaskA's identity after TaskB is WORKING:
    emit_signal(signals, f"TURN_ENDED workkey=TaskA token={tok_a} result_id=R-A outcome=DONE checkpoint=A-done")
    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=A-done-dup")
    results, _, _ = run_once(k, "s1", signals, state)
    assert results == [WAKE_PENDING, "DUPLICATE_IGNORED"]
    assert k.workkeys["TaskA"].state == DONE
    assert k.workkeys["TaskB"].state == "CLAIMED"             # NOT FALSE_DONE!

    # Now TaskB starts WORKING, and another late duplicate for TaskA arrives:
    assert drain_pending(k, "s1") == "TaskB"
    emit_signal(signals, f"TURN_ENDED workkey=TaskA token={tok_a} result_id=R-A outcome=DONE checkpoint=A-done")
    results, _, _ = run_once(k, "s1", signals, state)
    assert results == ["DUPLICATE_IGNORED"]
    assert k.workkeys["TaskB"].state == "CLAIMED" and k.sessions["s1"].state == "WORKING"

    # TaskB only completes when its own verified result arrives:
    tok_b = k.sessions["s1"].token
    emit_signal(signals, f"TURN_ENDED workkey=TaskB token={tok_b} result_id=R-B outcome=DONE checkpoint=B-done")
    run_once(k, "s1", signals, state)
    assert k.workkeys["TaskB"].state == DONE and k.counters["completions"] == 2


def test_v75_scenario_g_lease_expires_with_unknown_external_effect_quarantines_non_idempotent(tmp_path):
    """Scenario G: Lease expires while external effect of a non_idempotent task is unknown ->
    quarantines as BLOCKED (zero duplicate execution) and moves on to next READY task."""
    from courier_runtime.continuity import BLOCKED

    dispatched = []
    k, clock, world, signals, state = setup(
        tmp_path,
        [
            {"key": "EXT_SIDE_EFFECT", "priority": 1, "effect_class": "non_idempotent"},
            {"key": "SAFE_NEXT", "priority": 2, "effect_class": "idempotent"},
        ],
        slot="s1",
        provider="muse",
        lease_seconds=30.0,
    )

    emit_signal(signals, "IDLE")
    run_once(k, "s1", signals, state, dispatch=lambda slot, wk, s: dispatched.append((wk, s.session_id)))
    assert dispatched == [("EXT_SIDE_EFFECT", "s1-g1")]
    stale_token = k.sessions["s1"].token

    # Lease expires (30s) + tick cadence (45s) while external effect is unknown
    clock.t += 45.0
    _, actions, _ = run_once(k, "s1", signals, state, dispatch=lambda slot, wk, s: dispatched.append((wk, s.session_id)))
    assert actions["s1"]["quarantined_workkey"] == "EXT_SIDE_EFFECT"
    assert k.workkeys["EXT_SIDE_EFFECT"].state == BLOCKED
    assert "unknown external effect" in k.workkeys["EXT_SIDE_EFFECT"].blocked_reason
    # Successor session automatically moved on to SAFE_NEXT instead of re-executing EXT_SIDE_EFFECT:
    assert dispatched == [("EXT_SIDE_EFFECT", "s1-g1"), ("SAFE_NEXT", "s1-g2")]
    assert k.on_turn_end("s1", "DONE", stale_token, workkey="EXT_SIDE_EFFECT") == "REJECTED_STALE_WRITER"


def test_v75_scenario_h_and_i_ready_becomes_empty_parks_idle_then_real_event_wakes(tmp_path):
    """Scenarios H & I: When READY becomes empty, Courier parks cleanly in IDLE; when a new
    authorized READY workkey arrives via a real event, Courier wakes and executes it once."""
    from courier_runtime.host_loop import _queue_idle, run_until_idle

    dispatched = []
    k, _, world, signals, state = setup(tmp_path, ["W1"], slot="s1", provider="antigravity")

    def adapter(slot, workkey, session):
        dispatched.append(workkey)
        emit_signal(signals, f"TURN_ENDED workkey={workkey} token={session.token} outcome=DONE checkpoint={workkey}-ok")

    emit_signal(signals, "IDLE")
    run_until_idle(k, "s1", signals, state, dispatch=adapter)

    # Scenario H: READY is empty -> cleanly IDLE, no artificial loop
    assert _queue_idle(k) is True
    assert k.sessions["s1"].state == "IDLE"
    assert dispatched == ["W1"]

    # Scenario I: New authorized READY workkey becomes available via a real event
    emit_signal(signals, "WORKKEY_READY key=W2 priority=10")
    run_until_idle(k, "s1", signals, state, dispatch=adapter)

    assert dispatched == ["W1", "W2"]
    assert k.workkeys["W2"].state == DONE
    assert _queue_idle(k) is True and k.sessions["s1"].state == "IDLE"
    assert len(world.started) == 1
