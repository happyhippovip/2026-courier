"""Ledger engine: cost gate before the task, FINAL only with journal proof, one campaign writer."""
import hashlib
import json
import multiprocessing

import pytest

from courier_core.controller import Controller
from courier_core.events import EventType
from courier_core.verification import Verdict
from courier_runtime.continuity import BLOCKED, CLAIMED, DONE, FAILED_FINAL
from courier_runtime.ledger_engine import NOT_PROVEN, CostBlocked, LedgerEngine, TaskConflict, cost_admission

GOLD = b"LEDGER-ENGINE"
GOLD_SHA = hashlib.sha256(GOLD).hexdigest()


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def gold_verifier(task, result, home):
    arts = result.payload.get("artifacts") or []
    ok = len(arts) == 1 and arts[0].get("sha256") == GOLD_SHA and (home / arts[0]["path"]).read_bytes() == GOLD
    return Verdict(ok, "bytes match" if ok else "bytes differ")


def body(cost=0.0, effect="idempotent", attempts=1, **extra):
    params = {"estimated_cost_eur": cost, **extra}
    return {"adapter": "synthetic", "params": params, "effect_class": effect,
            "max_attempts": attempts, "lease_ttl_s": 10}


@pytest.fixture
def setup(tmp_path):
    clock = Clock()
    ctrl = Controller(tmp_path / "home", verifier=lambda adapter: gold_verifier, clock=clock).boot()
    engine = LedgerEngine(ctrl, tmp_path / "campaign" / "kirby.json", "host-a")
    yield engine, ctrl, tmp_path / "home", clock
    ctrl.stop()


def work(ctrl, home, payload=GOLD, outcome="success"):
    """A worker: claim, start, write the artifact, report, then the verifier runs."""
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    (home / "out.bin").write_bytes(payload)
    ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": outcome,
                 "artifacts": [{"path": "out.bin", "sha256": hashlib.sha256(payload).hexdigest()}]})
    ctrl.drain()
    return c


def kirby_state(path):
    return json.loads(path.read_text())


# -- cost gate -------------------------------------------------------------------------------

@pytest.mark.parametrize("params, blocked", [
    ({"estimated_cost_eur": 0.0}, False),
    ({"estimated_cost_eur": 0}, False),
    ({}, True),
    ({"estimated_cost_eur": None}, True),
    ({"estimated_cost_eur": float("nan")}, True),
    ({"estimated_cost_eur": float("inf")}, True),
    ({"estimated_cost_eur": True}, True),
    ({"estimated_cost_eur": "0"}, True),
    ({"estimated_cost_eur": -1.0}, True),
    ({"estimated_cost_eur": 0.01}, True),
    ({"estimated_cost_eur": 0.0, "unknown_cost": True}, True),
    ({"estimated_cost_eur": 0.0, "cost_class": "unknown"}, True),
    (None, True),
    ([], True),
    ({"estimated_cost_eur": "nan"}, True),
    ({"estimated_cost_eur": 10**9}, True),
    ({"estimated_cost_eur": -0.0}, False),
    ({"estimated_cost_eur": 0.0, "unknown_cost": False}, False),
    ({"estimated_cost_eur": 0.0, "unknown_cost": "yes"}, False),
])
def test_cost_admission_allows_only_an_explicit_estimate_within_the_limit(params, blocked):
    assert (cost_admission(params) is not None) is blocked


def test_unknown_cost_blocks_before_the_task_exists(setup):
    engine, ctrl, _, _ = setup
    with pytest.raises(CostBlocked):
        engine.submit("WK-1", body(cost=None))
    assert [e for e in ctrl.journal.events() if e.type is EventType.TASK_CREATED] == []
    assert ctrl.claim({"worker_id": "w1"}) is None


def test_a_raised_limit_admits_up_to_the_limit_only():
    assert cost_admission({"estimated_cost_eur": 2.0}, spend_limit_eur=2.0) is None
    assert cost_admission({"estimated_cost_eur": 2.01}, spend_limit_eur=2.0) is not None


# -- final only with proof -------------------------------------------------------------------

def test_verified_task_makes_the_workkey_done_with_its_journal_proof(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    engine.finish_turn("S1", workkey, token, task_id, checkpoint="cp")
    state = kirby_state(engine.campaign_path)["workkeys"]["WK-1"]
    proof = engine.proof(task_id)
    assert state["state"] == DONE and proof.startswith("journal:") and proof.endswith(":RESULT_ACCEPTED")
    assert state["checkpoint"] == f"cp | {proof}"
    receipt = json.loads((engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()[-1])
    assert proof in receipt["checkpoint"]


def test_provider_says_done_but_nothing_is_verified_stays_claimed(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    assert engine.finish_turn("S1", workkey, token, task_id, checkpoint="claims done") == NOT_PROVEN
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    assert engine.finish_turn("S1", workkey, token, task_id) == NOT_PROVEN     # running is not done
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == CLAIMED
    assert engine.next("S1") == (workkey, token)                               # resumes, no new claim


def test_wrong_bytes_end_failed_final_not_done(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body(attempts=1))
    work(ctrl, home, payload=b"tampered")
    engine.finish_turn("S1", workkey, token, task_id)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == FAILED_FINAL


def test_blocked_task_parks_the_workkey(setup):
    engine, ctrl, _, clock = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body(effect="non_idempotent"))
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    clock.t += 11
    ctrl.tick()
    engine.finish_turn("S1", workkey, token, task_id)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == BLOCKED


def test_stale_token_cannot_finish_a_workkey(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    assert engine.finish_turn("S1", workkey, token - 1, task_id) == "REJECTED_STALE_WRITER"
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == CLAIMED


def test_stale_token_cannot_overwrite_the_checkpoint_of_an_unproven_workkey(setup):
    engine, _, _, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    engine.finish_turn("S1", workkey, token, task_id, checkpoint="real step 2")
    assert engine.finish_turn("S1", workkey, token - 1, task_id, checkpoint="forged") == "REJECTED_STALE_WRITER"
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["checkpoint"] == "real step 2"


# -- restart and replay ----------------------------------------------------------------------

def test_restart_finds_the_same_task_and_does_not_run_it_again(setup, tmp_path):
    engine, ctrl, home, clock = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    ctrl.stop()
    ctrl2 = Controller(home, verifier=lambda adapter: gold_verifier, clock=clock).boot()
    engine2 = LedgerEngine(ctrl2, engine.campaign_path, "host-a")
    assert engine2.next("S1") == (workkey, token)                              # same claim resumed
    assert engine2.submit(workkey, body()) == task_id                          # replay: same task
    assert ctrl2.claim({"worker_id": "w2"}) is None                            # nothing to run again
    engine2.finish_turn("S1", workkey, token, task_id)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE
    created = [e for e in ctrl2.journal.events() if e.type is EventType.TASK_CREATED]
    accepted = [e for e in ctrl2.journal.events() if e.type is EventType.RESULT_ACCEPTED]
    assert len(created) == 1 and len(accepted) == 1
    ctrl2.stop()


# -- one writer for the campaign -------------------------------------------------------------

def _claim_in_process(path, slot, out):
    from courier_runtime.ledger_engine import LedgerEngine as Engine
    engine = Engine(controller=None, campaign_path=path, host="host-a")
    got = engine.next(slot)
    out.put((slot, got[0] if got else None))


def _tick_in_process(path, signals, out):
    """A second host's loop tick. It must wait for the campaign lock, then adopt disk."""
    from courier_runtime.continuity import Kirby
    from courier_runtime.host_loop import run_once
    kirby = Kirby(path, "host-b")
    run_once(kirby, "S1", signals, {"offset": 0, "last_tick": 0.0, "notified": {}})
    out.put(json.loads(path.read_text(encoding="utf-8"))["workkeys"]["WK-1"]["state"])


def _heartbeat_in_process(path, signals, out):
    """A second host's heartbeat. It must not write until it holds the campaign lock."""
    from courier_runtime.continuity import Kirby
    from courier_runtime.host_loop import run_once
    kirby = Kirby(path, "host-b")
    run_once(kirby, "S1", signals, {"offset": 0, "last_tick": kirby.clock(), "notified": {}})
    disk = json.loads(path.read_text(encoding="utf-8"))["workkeys"]["WK-1"]
    out.put((disk["state"], disk["checkpoint"]))


def test_two_processes_never_claim_the_same_workkey(tmp_path):
    path = tmp_path / "campaign" / "kirby.json"
    seed = LedgerEngine(None, path, "host-a")
    seed.add_workkeys(["WK-1", "WK-2"])
    for slot in ("S1", "S2", "S3", "S4"):
        seed.open_slot(slot, "local")
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    procs = [ctx.Process(target=_claim_in_process, args=(path, s, out)) for s in ("S1", "S2", "S3", "S4")]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
        assert p.exitcode == 0
    claims = [out.get(timeout=5) for _ in procs]
    won = sorted(wk for _, wk in claims if wk)
    assert won == ["WK-1", "WK-2"]                                             # each exactly once
    state = kirby_state(path)
    owners = {k: v["owner"] for k, v in state["workkeys"].items()}
    holders = {s["workkey"]: s["session_id"] for s in state["sessions"].values() if s["workkey"]}
    assert owners == holders                                                   # file agrees with every winner


def test_host_tick_on_another_host_waits_and_keeps_done(tmp_path):
    """A second host's tick shares the campaign lock. It must not snapshot a
    CLAIMED image over a DONE the lock holder has already published."""
    from courier_runtime.ledger_engine import LedgerEngine, _exclusive

    path = tmp_path / "campaign" / "kirby.json"
    seed = LedgerEngine(None, path, "host-a")
    seed.add_workkeys(["WK-1"])
    seed.open_slot("S1", "local")
    seed.next("S1")
    signals = tmp_path / "campaign" / "signals.log"
    signals.write_text("", encoding="utf-8")
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    with _exclusive(seed.lock_path):
        proc = ctx.Process(target=_tick_in_process, args=(path, signals, out))
        proc.start()
        proc.join(3)
        assert proc.is_alive()
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["workkeys"]["WK-1"]["state"] = DONE
        saved["workkeys"]["WK-1"]["owner"] = ""
        saved["workkeys"]["WK-1"]["checkpoint"] = "step | journal:7:RESULT_ACCEPTED"
        path.write_text(json.dumps(saved), encoding="utf-8")
    proc.join(30)
    assert proc.exitcode == 0
    assert out.get(timeout=5) == DONE
    assert kirby_state(path)["workkeys"]["WK-1"]["state"] == DONE
    assert kirby_state(path)["workkeys"]["WK-1"]["checkpoint"].endswith(":RESULT_ACCEPTED")


def test_host_heartbeat_waits_for_the_lock_before_it_writes(tmp_path):
    """A heartbeat must not land while another host holds the campaign lock.
    After that host publishes DONE, the heartbeat keeps the journal checkpoint."""
    from courier_runtime.ledger_engine import LedgerEngine, _exclusive

    path = tmp_path / "campaign" / "kirby.json"
    seed = LedgerEngine(None, path, "host-a")
    seed.add_workkeys(["WK-1"])
    seed.open_slot("S1", "local")
    seed.next("S1")
    signals = tmp_path / "campaign" / "signals.log"
    signals.write_text("HEARTBEAT progress=1 checkpoint=from-host-b\n", encoding="utf-8")
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    with _exclusive(seed.lock_path):
        proc = ctx.Process(target=_heartbeat_in_process, args=(path, signals, out))
        proc.start()
        proc.join(3)
        assert proc.is_alive()
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["workkeys"]["WK-1"]["checkpoint"] != "from-host-b"
        assert saved["workkeys"]["WK-1"]["state"] == CLAIMED
        saved["workkeys"]["WK-1"]["state"] = DONE
        saved["workkeys"]["WK-1"]["owner"] = ""
        saved["workkeys"]["WK-1"]["checkpoint"] = "step | journal:7:RESULT_ACCEPTED"
        for session in saved["sessions"].values():
            if session.get("workkey") == "WK-1":
                session["workkey"] = ""
                session["state"] = "IDLE"
        path.write_text(json.dumps(saved), encoding="utf-8")
    proc.join(30)
    assert proc.exitcode == 0
    state, checkpoint = out.get(timeout=5)
    assert state == DONE and checkpoint.endswith(":RESULT_ACCEPTED")


def test_a_held_campaign_lock_makes_another_process_wait(tmp_path):
    from courier_runtime.ledger_engine import _exclusive
    path = tmp_path / "campaign" / "kirby.json"
    seed = LedgerEngine(None, path, "host-a")
    seed.add_workkeys(["WK-1"])
    seed.open_slot("S1", "local")
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    with _exclusive(seed.lock_path):
        p = ctx.Process(target=_claim_in_process, args=(path, "S1", out))
        p.start()
        p.join(3)
        assert p.is_alive()                                                    # blocked on the lock
        assert kirby_state(path)["workkeys"]["WK-1"]["state"] != CLAIMED
    p.join(30)
    assert p.exitcode == 0 and out.get(timeout=5) == ("S1", "WK-1")


# -- zero-human chain ------------------------------------------------------------------------

def test_zero_human_chain_runs_three_workkeys_to_final_with_proofs(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1", "WK-2", "WK-3"])
    engine.open_slot("S1", "local")
    finished = []
    for _ in range(10):
        claimed = engine.next("S1")
        if claimed is None:
            break
        workkey, token = claimed
        task_id = engine.submit(workkey, body())
        work(ctrl, home)
        engine.finish_turn("S1", workkey, token, task_id)
        finished.append(workkey)
    state = kirby_state(engine.campaign_path)
    assert finished == ["WK-1", "WK-2", "WK-3"]
    assert all(w["state"] == DONE and ":RESULT_ACCEPTED" in w["checkpoint"] for w in state["workkeys"].values())
    assert state["counters"]["manual_continue"] == 0


# -- known gaps outside the engine (owners: controller L2, host loop L3) ----------------------

@pytest.mark.xfail(strict=True, raises=AssertionError, reason="F-C1 gap in courier_core/controller.py (owner L2, controller admission; no open PR fixes it, "
                   "LedgerEngine.submit does not cover direct calls): "
                   "create_task has no cost gate; remove this xfail when the controller rejects it")
def test_gap_direct_controller_create_task_bypasses_the_cost_gate(setup):
    _, ctrl, _, _ = setup
    status, _ = ctrl.create_task(body(cost=None, unknown_cost=True))
    assert status >= 400


def test_provider_done_signal_does_not_mark_done_without_proof(tmp_path):
    from courier_runtime.continuity import Kirby
    from courier_runtime.provider_events import handle
    kirby = Kirby(tmp_path / "kirby.json", "host-a")
    kirby.add_workkeys(["WK-1"])
    kirby.open_slot("S1", "local")
    kirby.wake("S1")
    kirby.deliver("S1")
    assert handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=trust me") == NOT_PROVEN
    assert kirby.workkeys["WK-1"].state != DONE


def test_provider_done_finalizes_only_through_finish_turn_proof(setup):
    """A DONE signal reaches DONE only via LedgerEngine.finish_turn and RESULT_ACCEPTED."""
    from courier_runtime.continuity import Kirby
    from courier_runtime.host_loop import emit_signal, run_once
    from courier_runtime.provider_events import handle

    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1", "WK-2"])
    engine.open_slot("S1", "local")
    engine.open_slot("S2", "local")
    wk1, _ = engine.next("S1")
    tid1 = engine.submit(wk1, body())
    engine.next("S2")
    kirby = Kirby(engine.campaign_path, "host-a")
    signals = engine.campaign_path.parent / "signals.log"

    assert [e for e in ctrl.journal.events(task_id=tid1) if e.type is EventType.RESULT_ACCEPTED] == []
    assert handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=trust me", engine=engine) == NOT_PROVEN
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == CLAIMED
    assert "RESULT_ACCEPTED" not in kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["checkpoint"]
    assert handle(kirby, "S2", "TURN_ENDED outcome=DONE checkpoint=borrow", engine=engine) == NOT_PROVEN

    work(ctrl, home)  # verifies WK-1 only; WK-2 has no task
    proof = engine.proof(tid1)
    assert proof.startswith("journal:") and proof.endswith(":RESULT_ACCEPTED")
    assert handle(kirby, "S2", "TURN_ENDED outcome=DONE checkpoint=borrow", engine=engine) == NOT_PROVEN
    assert handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=step", engine=engine) == "IDLE"
    done = kirby_state(engine.campaign_path)["workkeys"]["WK-1"]
    assert done["state"] == DONE and done["checkpoint"] == f"step | {proof}"
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-2"]["state"] == CLAIMED
    receipts = (engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()
    assert [json.loads(line)["workkey"] for line in receipts] == ["WK-1"]

    # The caller's Kirby reloads the saved DONE. A replay does not claim the workkey again.
    assert handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=step", engine=engine) == "IDLE"
    assert len((engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()) == 1

    restarted_kirby = Kirby(engine.campaign_path, "host-a")
    restarted = LedgerEngine(ctrl, engine.campaign_path, "host-a")
    handle(restarted_kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=again", engine=restarted)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE
    assert [json.loads(line)["workkey"] for line in (engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()] == ["WK-1"]

    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=file")
    loop_kirby = Kirby(engine.campaign_path, "host-a")
    results, _, notices = run_once(loop_kirby, "S2", signals, {"offset": 0, "last_tick": loop_kirby.clock(), "notified": {}}, engine=restarted)
    assert results == [NOT_PROVEN] and notices == []
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-2"]["state"] == CLAIMED


def test_idle_after_proven_done_does_not_restore_claimed(setup):
    """The caller's Kirby is a different object from the one finish_turn saves.

    A later IDLE or HEARTBEAT must not write that stale CLAIMED image over the
    journal-proven DONE. One receipt stays one receipt.
    """
    from courier_runtime.continuity import Kirby
    from courier_runtime.provider_events import handle

    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, _token = engine.next("S1")
    engine.submit(workkey, body())
    work(ctrl, home)
    kirby = Kirby(engine.campaign_path, "host-a")
    assert handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=step", engine=engine) == "IDLE"
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE
    handle(kirby, "S1", "IDLE")
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE
    handle(kirby, "S1", "HEARTBEAT progress=1 checkpoint=later")
    disk = kirby_state(engine.campaign_path)["workkeys"]["WK-1"]
    assert disk["state"] == DONE
    assert ":RESULT_ACCEPTED" in disk["checkpoint"]
    receipts = (engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()
    assert len(receipts) == 1


def test_host_tick_after_external_done_does_not_restore_claimed(setup):
    """main() keeps one Kirby for the life of the process. A tick with no new
    provider line must adopt a DONE that finish_turn already saved, instead of
    writing the startup CLAIMED image back over the journal proof."""
    from courier_runtime.continuity import Kirby
    from courier_runtime.host_loop import emit_signal, run_once

    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    stale = Kirby(engine.campaign_path, "host-a")
    assert stale.workkeys[workkey].state == CLAIMED
    work(ctrl, home)
    assert engine.finish_turn("S1", workkey, token, task_id, checkpoint="step")
    assert kirby_state(engine.campaign_path)["workkeys"][workkey]["state"] == DONE
    signals = engine.campaign_path.parent / "signals.log"
    signals.write_text("", encoding="utf-8")
    run_once(stale, "S1", signals, {"offset": 0, "last_tick": 0.0, "notified": {}})
    disk = kirby_state(engine.campaign_path)["workkeys"][workkey]
    assert disk["state"] == DONE and ":RESULT_ACCEPTED" in disk["checkpoint"]
    receipts = (engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()
    assert len(receipts) == 1

    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=replay")
    run_once(stale, "S1", signals, {"offset": 0, "last_tick": stale.clock(), "notified": {}}, engine=engine)
    assert kirby_state(engine.campaign_path)["workkeys"][workkey]["state"] == DONE
    assert len((engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()) == 1


def test_signal_file_done_records_the_journal_proof_once(setup):
    """The host loop's file tail is the execution path. It records
    journal:<seq>:RESULT_ACCEPTED only after the controller accepts the bytes,
    and a second line does not write a second final."""
    from courier_runtime.continuity import Kirby
    from courier_runtime.host_loop import emit_signal, run_once

    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, _token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    kirby = Kirby(engine.campaign_path, "host-a")
    signals = engine.campaign_path.parent / "signals.log"
    state = {"offset": 0, "last_tick": kirby.clock(), "notified": {}}
    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=early")
    results, _, _ = run_once(kirby, "S1", signals, state, engine=engine)
    assert results == [NOT_PROVEN]
    assert kirby_state(engine.campaign_path)["workkeys"][workkey]["state"] == CLAIMED
    assert "RESULT_ACCEPTED" not in kirby_state(engine.campaign_path)["workkeys"][workkey]["checkpoint"]

    work(ctrl, home)
    proof = engine.proof(task_id)
    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=step")
    results, _, _ = run_once(kirby, "S1", signals, state, engine=engine)
    disk = kirby_state(engine.campaign_path)["workkeys"][workkey]
    assert results == ["IDLE"] and disk["state"] == DONE and disk["checkpoint"] == f"step | {proof}"
    emit_signal(signals, "TURN_ENDED outcome=DONE checkpoint=again")
    run_once(kirby, "S1", signals, state, engine=engine)
    assert kirby_state(engine.campaign_path)["workkeys"][workkey]["state"] == DONE
    assert len((engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()) == 1


def test_provider_done_from_the_wrong_owner_does_not_finish(setup):
    from courier_runtime.continuity import Kirby
    from courier_runtime.provider_events import handle

    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, _ = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    assert engine.proof(task_id).endswith(":RESULT_ACCEPTED")
    foreign = Kirby(engine.campaign_path, "host-a")
    foreign.workkeys[workkey].owner = "not-the-session"
    foreign._save()  # the fence is the campaign file; an unsaved memory image is reloaded away
    assert handle(foreign, "S1", "TURN_ENDED outcome=DONE checkpoint=stolen", engine=engine) == "COALESCED"
    assert kirby_state(engine.campaign_path)["workkeys"][workkey]["state"] == CLAIMED
    assert not (engine.campaign_path.parent / "receipts.jsonl").exists()


# -- restart, verify and replay negatives ------------------------------------------------------

def test_restart_keeps_each_claim_with_its_owner(setup):
    engine, ctrl, _, clock = setup
    engine.add_workkeys(["WK-1", "WK-2"])
    engine.open_slot("S1", "local")
    engine.open_slot("S2", "local")
    first = engine.next("S1")
    ctrl.stop()
    restarted = LedgerEngine(None, engine.campaign_path, "host-a")
    assert restarted.next("S1") == first                                       # resumed, not re-claimed
    assert restarted.next("S2")[0] == "WK-2"                                   # the other slot gets the other key
    owners = {k: v["owner"] for k, v in kirby_state(engine.campaign_path)["workkeys"].items()}
    assert len(set(owners.values())) == 2


def test_time_passing_while_verifying_does_not_lose_the_result(setup):
    engine, ctrl, home, clock = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    (home / "out.bin").write_bytes(GOLD)
    ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": "success",
                 "artifacts": [{"path": "out.bin", "sha256": GOLD_SHA}]})
    for _ in range(30):                                                        # 30 s, ttl is 10 s
        clock.t += 1
        ctrl.tick()
    assert ctrl.task_view(task_id)["status"] == "VERIFYING"                    # no lease to lose here
    ctrl.drain()
    engine.finish_turn("S1", workkey, token, task_id)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE


def test_human_confirmed_effect_is_not_proof(setup):
    engine, ctrl, _, clock = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body(effect="non_idempotent"))
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    clock.t += 11
    ctrl.tick()
    ctrl.resolve(task_id, {"decision": "effect_confirmed", "actor": "dennis", "attempt": 1, "reason": "seen it"})
    assert ctrl.task_view(task_id)["status"] == "COMPLETE"
    assert engine.proof(task_id) is None
    assert engine.finish_turn("S1", workkey, token, task_id) == NOT_PROVEN


def test_a_second_finish_after_final_is_rejected_and_writes_no_second_receipt(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    engine.finish_turn("S1", workkey, token, task_id)
    assert engine.finish_turn("S1", workkey, token, task_id) == "REJECTED_STALE_WRITER"
    receipts = (engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()
    assert len(receipts) == 1


def test_crash_after_verifier_acceptance_completes_on_restart(setup, monkeypatch):
    engine, ctrl, home, clock = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    (home / "out.bin").write_bytes(GOLD)
    ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": "success",
                 "artifacts": [{"path": "out.bin", "sha256": GOLD_SHA}]})

    def crash(task):
        raise RuntimeError("process died after RESULT_ACCEPTED")
    monkeypatch.setattr(ctrl, "_complete", crash)
    with pytest.raises(RuntimeError):
        ctrl.drain()
    assert ctrl.task_view(task_id)["status"] == "ACCEPTED"
    assert engine.proof(task_id) is None                                       # accepted is not yet FINAL
    assert engine.finish_turn("S1", workkey, token, task_id) == NOT_PROVEN
    ctrl.stop()
    ctrl2 = Controller(home, verifier=lambda adapter: gold_verifier, clock=clock).boot()
    engine2 = LedgerEngine(ctrl2, engine.campaign_path, "host-a")
    assert ctrl2.task_view(task_id)["status"] == "COMPLETE"
    engine2.finish_turn("S1", workkey, token, task_id)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE
    assert [e.type for e in ctrl2.journal.events() if e.task_id == task_id].count(EventType.RESULT_ACCEPTED) == 1
    ctrl2.stop()


def test_final_checkpoint_and_receipt_carry_everything_needed_to_resume(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    engine.finish_turn("S1", workkey, token, task_id, checkpoint="step 5 of 5")
    wk = kirby_state(engine.campaign_path)["workkeys"]["WK-1"]
    receipt = json.loads((engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()[-1])
    assert wk["state"] == DONE and wk["owner"] == "" and wk["token"] == token
    assert wk["checkpoint"].startswith("step 5 of 5 | journal:")
    assert {"workkey", "outcome", "session", "checkpoint", "at"} <= set(receipt)
    assert receipt["workkey"] == "WK-1" and receipt["checkpoint"] == wk["checkpoint"]


# -- unknown cost across the chain -------------------------------------------------------------

def test_cost_blocked_workkey_is_parked_and_the_chain_moves_on(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1", "WK-2", "WK-3"])
    engine.open_slot("S1", "local")
    costs = {"WK-1": 0.0, "WK-2": None, "WK-3": 0.0}
    outcome = {}
    for _ in range(10):                                                        # bounded: a stall must fail, not hang
        claimed = engine.next("S1")
        if claimed is None:
            break
        workkey, token = claimed
        assert workkey not in outcome, f"{workkey} came back after it was handled"
        try:
            task_id = engine.submit(workkey, body(cost=costs[workkey]), slot="S1", token=token)
        except CostBlocked:
            outcome[workkey] = "blocked"
            continue
        work(ctrl, home)
        engine.finish_turn("S1", workkey, token, task_id)
        outcome[workkey] = "done"
    state = kirby_state(engine.campaign_path)
    assert outcome == {"WK-1": "done", "WK-2": "blocked", "WK-3": "done"}
    assert state["workkeys"]["WK-2"]["state"] == BLOCKED
    assert state["workkeys"]["WK-2"]["blocked_reason"].startswith("COST_BLOCKED: UNKNOWN_COST")
    assert len([e for e in ctrl.journal.events() if e.type is EventType.TASK_CREATED]) == 2
    assert state["sessions"]["S1"]["state"] == "WAITING_FOR_USER"              # a human decides WK-2


def test_cost_block_with_a_stale_token_does_not_park_someone_elses_workkey(setup):
    engine, _, _, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    with pytest.raises(CostBlocked):
        engine.submit(workkey, body(cost=None), slot="S1", token=token - 1)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == CLAIMED


# -- review findings (independent reviewer, 23.10.) ----------------------------------------------

def test_a_verified_task_of_another_workkey_cannot_finish_this_workkey(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1", "WK-2"])
    engine.open_slot("S1", "local")
    engine.open_slot("S2", "local")
    wk1, t1 = engine.next("S1")
    tid1 = engine.submit(wk1, body())
    work(ctrl, home)
    wk2, t2 = engine.next("S2")
    assert engine.finish_turn("S2", wk2, t2, tid1) == "REJECTED_FOREIGN_TASK"
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-2"]["state"] == CLAIMED


def test_resubmit_after_restart_with_the_same_body_returns_the_existing_task(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    assert engine.submit(workkey, body(), slot="S1", token=token) == task_id


def test_a_changed_body_under_the_same_workkey_is_a_conflict_and_parks_nothing(setup):
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    for changed in (body(cost=None), body(note="other input")):
        with pytest.raises(TaskConflict):
            engine.submit(workkey, changed, slot="S1", token=token)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == CLAIMED
    assert len([e for e in ctrl.journal.events() if e.type is EventType.TASK_CREATED]) == 1
    engine.finish_turn("S1", workkey, token, task_id)
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE


def test_a_task_with_dependencies_is_refused_before_anything_is_written(setup):
    # The engine orders work by workkey; a controller dependency would leave the slot NOT_PROVEN forever.
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    with pytest.raises(ValueError, match="depends_on"):
        engine.submit(workkey, dict(body(), depends_on=["task-x"]))
    assert [e for e in ctrl.journal.events() if e.type is EventType.TASK_CREATED] == []


def test_a_crash_after_the_receipt_and_before_the_save_writes_one_receipt(setup, monkeypatch):
    from courier_runtime import continuity
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1", "WK-2"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    task_id = engine.submit(workkey, body())
    work(ctrl, home)
    save = continuity.Kirby._save

    def killed_after_receipt(self):
        if self.workkeys["WK-1"].state == DONE:
            raise SystemExit("process killed before the campaign file was saved")
        return save(self)
    monkeypatch.setattr(continuity.Kirby, "_save", killed_after_receipt)
    with pytest.raises(SystemExit):
        engine.finish_turn("S1", workkey, token, task_id)
    monkeypatch.setattr(continuity.Kirby, "_save", save)
    restarted = LedgerEngine(ctrl, engine.campaign_path, "host-a")
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == CLAIMED
    restarted.finish_turn("S1", workkey, token, task_id)
    receipts = (engine.campaign_path.parent / "receipts.jsonl").read_text().splitlines()
    assert [json.loads(line)["workkey"] for line in receipts] == ["WK-1"]
    assert kirby_state(engine.campaign_path)["workkeys"]["WK-1"]["state"] == DONE
    assert restarted.next("S1")[0] == "WK-2"


@pytest.mark.parametrize("limit", [float("nan"), float("inf"), -1.0, True, "0"])
def test_spend_limit_must_be_a_finite_non_negative_number(tmp_path, limit):
    with pytest.raises(ValueError):
        LedgerEngine(None, tmp_path / "kirby.json", "host-a", spend_limit_eur=limit)
