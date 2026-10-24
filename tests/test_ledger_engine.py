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

def test_direct_controller_create_task_is_cost_gated_too(setup):
    """F-C1 closed in the controller: a direct create_task with unknown cost writes nothing."""
    from courier_core.controller import ApiError
    _, ctrl, _, _ = setup
    with pytest.raises(ApiError) as exc:
        ctrl.create_task(body(cost=None, unknown_cost=True))
    assert exc.value.code == "cost_blocked"
    assert [e for e in ctrl.journal.events() if e.type is EventType.TASK_CREATED] == []


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="F-K1 gap in courier_runtime/provider_events.py + host_loop.py (owner L3): "
                   "a provider TURN_ENDED outcome=DONE line marks the workkey DONE without journal proof; "
                   "remove this xfail when that path goes through LedgerEngine.finish_turn")
def test_gap_host_loop_provider_signal_marks_done_without_proof(tmp_path):
    from courier_runtime.continuity import Kirby
    from courier_runtime.provider_events import handle
    kirby = Kirby(tmp_path / "kirby.json", "host-a")
    kirby.add_workkeys(["WK-1"])
    kirby.open_slot("S1", "local")
    kirby.wake("S1")
    kirby.deliver("S1")
    handle(kirby, "S1", "TURN_ENDED outcome=DONE checkpoint=trust me")
    assert kirby.workkeys["WK-1"].state != DONE


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


def test_a_controller_cost_refusal_parks_the_workkey_like_the_engine_gate(setup):
    # The engine gate reads params only; the controller gate (F-C1) also needs the adapter's
    # COST_CLASS. When the controller refuses, the slot must move on instead of re-serving it.
    engine, ctrl, home, _ = setup
    engine.add_workkeys(["WK-1", "WK-2"])
    engine.open_slot("S1", "local")
    workkey, token = engine.next("S1")
    undeclared = dict(body(), adapter="adapter_without_cost_class")
    with pytest.raises(CostBlocked, match="cost_blocked"):
        engine.submit(workkey, undeclared, slot="S1", token=token)
    state = kirby_state(engine.campaign_path)["workkeys"]["WK-1"]
    assert state["state"] == BLOCKED and state["blocked_reason"].startswith("COST_BLOCKED")
    assert [e for e in ctrl.journal.events() if e.type is EventType.TASK_CREATED] == []
    assert engine.next("S1")[0] == "WK-2"
