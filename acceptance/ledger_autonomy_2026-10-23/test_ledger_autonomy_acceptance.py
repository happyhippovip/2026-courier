"""LEDGER_AUTONOMY_ACCEPTANCE probes (CLD-AUTO-003..021), isolated: no repo file is changed.

Runs the real courier_core Controller and courier_runtime Kirby from integration/v1.
Each test name carries its workkey. A test asserting current behaviour that is a finding
is marked FINDING in its docstring; it passes when the finding is reproduced.
"""
import hashlib
import json
import sqlite3

import pytest

from courier_core.controller import ApiError, Controller
from courier_core.events import EventType
from courier_core.verification import Verdict
from courier_runtime.continuity import CLAIMED, DONE, Kirby


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


GOLD = b"COURIER-ACCEPTANCE"
GOLD_SHA = hashlib.sha256(GOLD).hexdigest()


def gold_verifier(task, result, home):
    arts = result.payload.get("artifacts") or []
    ok = len(arts) == 1 and arts[0].get("sha256") == GOLD_SHA and (home / arts[0]["path"]).read_bytes() == GOLD
    return Verdict(ok, "bytes match gold" if ok else "bytes differ", retryable=True)


def reject_verifier(task, result, home):
    return Verdict(False, "always rejects", retryable=True)


def boot(home, clock, verify=gold_verifier):
    return Controller(home, verifier=lambda adapter: verify, clock=clock).boot()


def new_task(ctrl, effect="idempotent", attempts=3, ttl=30, key=None, params=None):
    body = {"adapter": "synthetic", "params": params or {}, "effect_class": effect,
            "max_attempts": attempts, "lease_ttl_s": ttl}
    if key:
        body["idempotency_key"] = key
    return ctrl.create_task(body)[1]["task_id"]


def run_to_result(ctrl, home, worker="w1", rid="r1", payload=GOLD):
    c = ctrl.claim({"worker_id": worker})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": worker})
    (home / "out.bin").write_bytes(payload)
    ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": rid, "outcome": "success",
                 "artifacts": [{"path": "out.bin", "sha256": hashlib.sha256(payload).hexdigest()}]})
    return c


def types(ctrl, task_id):
    return [e.type for e in ctrl.journal.events() if e.task_id == task_id]


# -- 003/004/013: FINAL only with a verified resolution and evidence -------------------------

def test_cld004_happy_path_final_carries_verified_resolution_and_proof(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl)
    run_to_result(ctrl, tmp_path)
    ctrl.drain()
    view = ctrl.task_view(tid)
    assert view["status"] == "COMPLETE" and view["resolution"] == "verified"
    assert types(ctrl, tid) == [EventType.TASK_CREATED, EventType.TASK_CLAIMED, EventType.TASK_STARTED,
                                EventType.RESULT_READY, EventType.RESULT_ACCEPTED, EventType.TASK_COMPLETE]
    ctrl.stop()


def test_cld013_wrong_bytes_never_reach_final(tmp_path):
    ctrl = boot(tmp_path, Clock())
    tid = new_task(ctrl, attempts=1)
    run_to_result(ctrl, tmp_path, payload=b"tampered")
    ctrl.drain()
    assert ctrl.task_view(tid)["status"] == "FAILED"
    assert EventType.TASK_COMPLETE not in types(ctrl, tid)
    ctrl.stop()


def test_cld013_missing_verifier_fails_closed(tmp_path):
    ctrl = Controller(tmp_path, verifier=lambda adapter: None, clock=Clock()).boot()
    tid = new_task(ctrl, attempts=1)
    run_to_result(ctrl, tmp_path)
    ctrl.drain()
    assert ctrl.task_view(tid)["status"] == "FAILED"
    ctrl.stop()


def test_cld013_worker_reported_failure_is_not_success(tmp_path):
    ctrl = boot(tmp_path, Clock())
    tid = new_task(ctrl, attempts=1)
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": "failure", "artifacts": []})
    ctrl.drain()
    assert ctrl.task_view(tid)["status"] == "FAILED"
    ctrl.stop()


# -- 012: no SUCCESS from heartbeats alone ---------------------------------------------------

def test_cld012_heartbeats_alone_never_complete(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl, ttl=10)
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    for _ in range(50):
        clock.t += 5
        ctrl.heartbeat({"worker_id": "w1", "dispatch_ids": [c["dispatch_id"]]})
        ctrl.tick()
    ctrl.drain()
    assert ctrl.task_view(tid)["status"] == "RUNNING"
    ctrl.stop()


# -- 007/020: no double claim, stale writer fenced -------------------------------------------

def test_cld007_one_task_is_claimed_once(tmp_path):
    ctrl = boot(tmp_path, Clock())
    new_task(ctrl)
    first = ctrl.claim({"worker_id": "w1"})
    assert first is not None
    assert ctrl.claim({"worker_id": "w2"}) is None
    ctrl.stop()


def test_cld020_wrong_worker_and_stale_dispatch_are_refused(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl, ttl=10)
    old = ctrl.claim({"worker_id": "w1"})
    with pytest.raises(ApiError) as exc:
        ctrl.start({"dispatch_id": old["dispatch_id"], "worker_id": "w2"})
    assert exc.value.code == "wrong_worker"
    clock.t += 11                                   # never started: lease expires, idempotent -> retry
    ctrl.tick()
    new = ctrl.claim({"worker_id": "w2"})
    assert new["task_id"] == tid and new["attempt"] == 2
    with pytest.raises(ApiError) as exc:
        ctrl.start({"dispatch_id": old["dispatch_id"], "worker_id": "w1"})
    assert exc.value.code == "stale_dispatch"
    ctrl.stop()


def test_cld020_late_result_of_superseded_dispatch_is_discarded(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl, ttl=10)
    old = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": old["dispatch_id"], "worker_id": "w1"})
    clock.t += 11
    ctrl.tick()                                     # idempotent + started + lease lost -> retry
    ctrl.claim({"worker_id": "w2"})
    (tmp_path / "out.bin").write_bytes(GOLD)
    with pytest.raises(ApiError) as exc:
        ctrl.result({"dispatch_id": old["dispatch_id"], "result_id": "late", "outcome": "success",
                     "artifacts": [{"path": "out.bin", "sha256": GOLD_SHA}]})
    assert exc.value.code == "stale_dispatch"
    assert EventType.LATE_RESULT_DISCARDED in types(ctrl, tid)
    assert ctrl.task_view(tid)["status"] == "CLAIMED"
    ctrl.stop()


# -- 008: lease expiry: non-idempotent uncertain outcome is BLOCKED, never retried -----------

def test_cld008_non_idempotent_lost_lease_blocks_for_a_human(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl, effect="non_idempotent", ttl=10)
    c = ctrl.claim({"worker_id": "w1"})
    ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    clock.t += 11
    ctrl.tick()
    assert ctrl.task_view(tid)["status"] == "BLOCKED"
    assert ctrl.claim({"worker_id": "w2"}) is None
    ctrl.stop()


# -- 009: idempotent transitions (duplicate create, duplicate result) -----------------------

def test_cld009_duplicate_create_and_duplicate_result_are_acknowledged_once(tmp_path):
    ctrl = boot(tmp_path, Clock())
    a = ctrl.create_task({"adapter": "synthetic", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 30, "idempotency_key": "k1"})
    b = ctrl.create_task({"adapter": "synthetic", "params": {}, "effect_class": "idempotent",
                          "max_attempts": 2, "lease_ttl_s": 30, "idempotency_key": "k1"})
    assert a[0] == 201 and b[0] == 200 and b[1]["duplicate"] is True
    c = run_to_result(ctrl, tmp_path)
    again = ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": "success",
                         "artifacts": [{"path": "out.bin", "sha256": GOLD_SHA}]})
    assert again[1]["status"] == "ACK_DUPLICATE"
    assert types(ctrl, a[1]["task_id"]).count(EventType.RESULT_READY) == 1
    ctrl.stop()


# -- 010/011: bounded retry budget, terminal FAILED as dead letter ---------------------------

def test_cld010_retry_budget_is_bounded_and_ends_failed(tmp_path):
    ctrl = boot(tmp_path, Clock(), verify=reject_verifier)
    tid = new_task(ctrl, attempts=3)
    for i in range(3):
        run_to_result(ctrl, tmp_path, rid=f"r{i}")
        ctrl.drain()
    view = ctrl.task_view(tid)
    assert view["status"] == "FAILED" and view["attempt"] == 3
    assert ctrl.claim({"worker_id": "w1"}) is None
    ctrl.stop()


# -- 015: fair, reproducible selection --------------------------------------------------------

def test_cld015_queue_is_fifo_by_creation(tmp_path):
    ctrl = boot(tmp_path, Clock())
    ids = [new_task(ctrl, key=f"k{n}") for n in (3, 1, 2)]
    claimed = [ctrl.claim({"worker_id": f"w{n}"})["task_id"] for n in range(3)]
    assert claimed == ids
    ctrl.stop()


# -- 006/018/019: restart safety -------------------------------------------------------------

def test_cld018_restart_while_verifying_verifies_exactly_once(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl)
    run_to_result(ctrl, tmp_path)
    ctrl.stop()                                     # crash/stop before the verifier ran
    ctrl2 = boot(tmp_path, clock)
    ctrl2.drain()
    assert ctrl2.task_view(tid)["status"] == "COMPLETE"
    assert types(ctrl2, tid).count(EventType.RESULT_ACCEPTED) == 1
    ctrl2.stop()


def test_cld019_restart_after_final_does_not_execute_again(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    tid = new_task(ctrl)
    run_to_result(ctrl, tmp_path)
    ctrl.drain()
    before = types(ctrl, tid)
    ctrl.stop()
    ctrl2 = boot(tmp_path, clock)
    assert ctrl2.claim({"worker_id": "w9"}) is None
    ctrl2.drain()
    assert types(ctrl2, tid) == before
    ctrl2.stop()


def test_cld006_restart_mid_run_gives_grace_then_retries_idempotent_only(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    idem = new_task(ctrl, key="idem", ttl=10)
    risky = new_task(ctrl, key="risky", effect="non_idempotent", ttl=10)
    for _ in range(2):
        c = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
    ctrl.stop()                                     # process dies with two running attempts
    ctrl2 = boot(tmp_path, clock)
    ctrl2.tick()
    assert ctrl2.task_view(idem)["status"] == "RUNNING"      # one ttl of restart grace
    for _ in range(11):                             # small steps: a big jump counts as suspend
        clock.t += 1
        ctrl2.tick()
    assert ctrl2.task_view(idem)["status"] == "QUEUED"       # retried
    assert ctrl2.task_view(risky)["status"] == "BLOCKED"     # never blindly retried
    ctrl2.stop()


def test_cld003_tampered_journal_boots_read_only(tmp_path):
    clock = Clock()
    ctrl = boot(tmp_path, clock)
    new_task(ctrl)
    ctrl.stop()
    db = sqlite3.connect(tmp_path / "courier.db")
    triggers = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
    for name in triggers:
        db.execute(f"DROP TRIGGER {name}")
    db.execute("UPDATE events SET payload = replace(payload, 'synthetic', 'evil') WHERE seq = 2")
    db.commit()
    db.close()
    ctrl2 = boot(tmp_path, clock)
    assert ctrl2.mode != "normal"
    with pytest.raises(ApiError):
        new_task(ctrl2)
    ctrl2.stop()


# -- 014: unknown cost at the controller ------------------------------------------------------

def test_cld014_FINDING_controller_accepts_and_dispatches_unknown_cost(tmp_path):
    """FINDING: the controller has no cost gate; a task with estimated_cost_eur None is created
    and claimed. Enforcement exists only inside adapters (provider_exec, gemini, google builder)."""
    ctrl = boot(tmp_path, Clock())
    tid = new_task(ctrl, params={"estimated_cost_eur": None, "unknown_cost": True})
    assert ctrl.claim({"worker_id": "w1"})["task_id"] == tid
    ctrl.stop()


# -- Kirby (workkey loop): 005/007/013/016/017/021 -------------------------------------------

def kirby(path, clock):
    return Kirby(path, "host-a", clock=clock)


def test_cld016_next_workkey_after_turn_end_with_checkpoint(tmp_path):
    clock = Clock()
    k = kirby(tmp_path / "kirby.json", clock)
    k.add_workkeys(["WK-2", "WK-1"])
    k.open_slot("S1", "claude")
    assert k.wake("S1") == "WAKE_PENDING"
    assert k.deliver("S1") == "WK-1"                         # deterministic: priority, then key
    token = k.sessions["S1"].token
    k.on_turn_end("S1", "DONE", token, checkpoint="cp-1")
    assert k.workkeys["WK-1"].state == DONE and k.workkeys["WK-1"].checkpoint == "cp-1"
    assert k.sessions["S1"].workkey == "WK-2"


def test_cld005_checkpoint_survives_restart(tmp_path):
    clock = Clock()
    path = tmp_path / "kirby.json"
    k = kirby(path, clock)
    k.add_workkeys(["WK-1"])
    k.open_slot("S1", "claude")
    k.wake("S1")
    k.deliver("S1")
    k.heartbeat("S1", progress=True, checkpoint="step-3-of-5")
    k2 = kirby(path, clock)                                  # process restart
    assert k2.workkeys["WK-1"].checkpoint == "step-3-of-5"
    assert k2.workkeys["WK-1"].state == CLAIMED
    assert k2.reconcile_after_restart() == {"S1": "RESUMED"}


def test_cld017_duplicate_wakes_are_coalesced(tmp_path):
    k = kirby(tmp_path / "kirby.json", Clock())
    k.add_workkeys(["WK-1", "WK-2"])
    k.open_slot("S1", "claude")
    assert k.wake("S1") == "WAKE_PENDING"
    assert k.wake("S1") == "COALESCED"
    assert k.wake("S1", manual=True) == "COALESCED"
    assert [w.key for w in k.workkeys.values() if w.state == CLAIMED] == ["WK-1"]


def test_cld020_stale_kirby_writer_is_rejected(tmp_path):
    k = kirby(tmp_path / "kirby.json", Clock())
    k.add_workkeys(["WK-1"])
    k.open_slot("S1", "claude")
    k.wake("S1")
    k.deliver("S1")
    token = k.sessions["S1"].token
    assert k.on_turn_end("S1", "DONE", token - 1) == "REJECTED_STALE_WRITER"
    assert k.workkeys["WK-1"].state == CLAIMED


def test_cld013_FINDING_kirby_marks_workkey_done_without_verifier_proof(tmp_path):
    """FINDING: Kirby turns a workkey DONE on the provider's word; no verifier, no evidence is
    required. The controller path is strict, the workkey loop is not."""
    k = kirby(tmp_path / "kirby.json", Clock())
    k.add_workkeys(["WK-1"])
    k.open_slot("S1", "claude")
    k.wake("S1")
    k.deliver("S1")
    k.on_turn_end("S1", "DONE", k.sessions["S1"].token, checkpoint="")
    assert k.workkeys["WK-1"].state == DONE
    receipt = json.loads((tmp_path / "receipts.jsonl").read_text().splitlines()[-1])
    assert receipt["outcome"] == DONE and receipt["checkpoint"] == ""


def test_cld007_FINDING_two_kirby_processes_claim_the_same_workkey(tmp_path):
    """FINDING: Kirby state is one JSON file without a lock. Two processes that loaded it before
    either saved both claim the same workkey; the last save wins and the other owner is lost."""
    clock = Clock()
    path = tmp_path / "kirby.json"
    seed = kirby(path, clock)
    seed.add_workkeys(["WK-1"])
    seed.open_slot("S1", "claude")
    seed.open_slot("S2", "codex")
    a, b = kirby(path, clock), kirby(path, clock)           # both load the same snapshot
    assert a.wake("S1") == "WAKE_PENDING" and b.wake("S2") == "WAKE_PENDING"
    assert a.sessions["S1"].workkey == "WK-1" and b.sessions["S2"].workkey == "WK-1"
    final = kirby(path, clock)
    owners = {s.slot for s in final.sessions.values() if s.workkey == "WK-1"}
    assert owners == {"S2"}                                   # S1 still believes it owns WK-1


def test_cld021_offline_campaign_runs_to_the_end_without_a_human(tmp_path):
    clock = Clock()
    k = kirby(tmp_path / "kirby.json", clock)
    k.add_workkeys([f"WK-{n}" for n in range(1, 6)])
    k.open_slot("S1", "local")
    k.wake("S1")
    done = []
    while (wk := k.deliver("S1")) is not None:
        done.append(wk)
        k.on_turn_end("S1", "DONE", k.sessions["S1"].token, checkpoint=f"cp-{wk}")
    assert done == [f"WK-{n}" for n in range(1, 6)]
    assert k.sessions["S1"].state == "IDLE" and k.counters["manual_continue"] == 0
