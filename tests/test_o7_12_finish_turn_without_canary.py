"""O7-12 (WK-O7-NEG-01), Option A (Dennis t764u).

Every workkey becomes DONE only with RESULT_ACCEPTED journal proof. A task marked
params.canary=True additionally needs a courier_canary_* artifact (with sha256) in its
accepted result; checkpoint text never counts. Kirby itself never accepts DONE without
a journal proof (gap 2, courier_runtime/continuity.py on_turn_end).
Source spec: GrokBot/WORKKEYS/ERGEBNISSE/O7-12_ERGEBNIS.md, adapted to Option A.
"""
from __future__ import annotations

import hashlib
import json

from courier_core.controller import Controller
from courier_core.verification import Verdict
from courier_runtime.continuity import DONE, Kirby
from courier_runtime.ledger_engine import NOT_PROVEN, LedgerEngine


def permissive_verifier(task, result, home):
    return Verdict(True, "permissive pass, no canary check")


def body(canary=None):
    params = {"estimated_cost_eur": 0.0}
    if canary is not None:
        params["canary"] = canary
    return {"adapter": "synthetic", "params": params,
            "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 10}


def run(tmp_path, wk, task_body, artifact, checkpoint):
    home = tmp_path / "home"
    ctrl = Controller(home, verifier=lambda adapter: permissive_verifier).boot()
    try:
        engine = LedgerEngine(ctrl, tmp_path / "campaign" / "kirby.json", "host-a")
        engine.add_workkeys([wk])
        engine.open_slot("S-1", "local")
        got, tok = engine.next("S-1")
        assert got == wk
        task_id = engine.submit(wk, task_body, slot="S-1", token=tok)
        c = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
        data = f"DATA-{wk}".encode()
        (home / artifact).write_bytes(data)
        ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": "success",
                     "artifacts": [{"path": artifact, "sha256": hashlib.sha256(data).hexdigest()}]})
        ctrl.drain()
        res = engine.finish_turn("S-1", wk, tok, task_id, checkpoint=checkpoint)
        state = json.loads(engine.campaign_path.read_text())["workkeys"][wk]["state"]
        return res, state
    finally:
        ctrl.stop()


def test_o7_12_canary_task_without_canary_artifact_is_not_done(tmp_path):
    res, state = run(tmp_path, "WK-CANARY-NOART", body(canary=True), "random.txt",
                     checkpoint="canary passed")          # checkpoint text alone must not count
    assert state != DONE and res == NOT_PROVEN, (res, state)


def test_o7_12_canary_task_with_canary_artifact_is_done(tmp_path):
    res, state = run(tmp_path, "WK-CANARY-OK", body(canary=True),
                     "courier_canary_WK-CANARY-OK.txt", checkpoint="plain_run")
    assert state == DONE, (res, state)


def test_o7_12_unmarked_task_with_result_accepted_is_done(tmp_path):
    res, state = run(tmp_path, "WK-PLAIN", body(), "out.bin", checkpoint="plain_run")
    assert state == DONE, (res, state)


def test_o7_12_kirby_on_turn_end_done_without_result_accepted_is_not_proven(tmp_path):
    k = Kirby(tmp_path / "kirby.json", "host-a")
    k.add_workkeys(["WK-K"])
    k.open_slot("S-1", "local")
    k.wake("S-1")
    key = k.deliver("S-1")
    assert key == "WK-K"
    tok = k.sessions["S-1"].token
    assert k.on_turn_end("S-1", "DONE", tok, checkpoint="journal:1:RESULT_ACCEPTED") == "NOT_PROVEN"
    assert k.on_turn_end("S-1", "DONE", tok, proof="forged") == "NOT_PROVEN"
    assert k.workkeys["WK-K"].state != DONE
