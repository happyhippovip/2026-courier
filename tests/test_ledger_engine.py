"""Ledger engine: cost gate before the task, FINAL only with journal proof, one campaign writer."""
import hashlib
import json
import multiprocessing

import pytest

from courier_core.controller import Controller
from courier_core.events import EventType
from courier_core.verification import Verdict
from courier_runtime.continuity import BLOCKED, CLAIMED, DONE, FAILED_FINAL
from courier_runtime.ledger_engine import NOT_PROVEN, CostBlocked, LedgerEngine, cost_admission

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
    while (claimed := engine.next("S1")) is not None:
        workkey, token = claimed
        task_id = engine.submit(workkey, body())
        work(ctrl, home)
        engine.finish_turn("S1", workkey, token, task_id)
        finished.append(workkey)
    state = kirby_state(engine.campaign_path)
    assert finished == ["WK-1", "WK-2", "WK-3"]
    assert all(w["state"] == DONE and ":RESULT_ACCEPTED" in w["checkpoint"] for w in state["workkeys"].values())
    assert state["counters"]["manual_continue"] == 0
