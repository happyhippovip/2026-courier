"""O7-12 (B6): a provider turn without journal proof (the finish_turn canary) is not DONE.

Guard (holds): LedgerEngine.finish_turn (courier_runtime/ledger_engine.py:228-252)
returns NOT_PROVEN without journal:<seq>:RESULT_ACCEPTED (proof(), :216-226).
Defect (strict xfail): the provider signal path bypasses that gate. A line
``TURN_ENDED outcome=DONE`` in the signal file is read by host_loop.run_once
(courier_runtime/host_loop.py:68-75) -> provider_events.drive/handle
(courier_runtime/provider_events.py:76-83) -> Kirby.on_turn_end(..., "DONE")
(courier_runtime/continuity.py:225-230), which marks the workkey DONE and writes
a DONE receipt with no proof at all. The provider's word decides, not the result.
"""
import json

import pytest

from courier_core.controller import Controller
from courier_runtime import host_loop
from courier_runtime.continuity import Kirby
from courier_runtime.ledger_engine import NOT_PROVEN, LedgerEngine, task_id_for


def _working(tmp_path, controller=None):
    camp = tmp_path / "kirby.json"
    engine = LedgerEngine(controller, camp, "host-a")
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    kirby = Kirby(camp, "host-a")
    kirby._load()
    kirby.wake("S1")
    assert host_loop.drain_pending(kirby, "S1") == "WK-1"
    return engine, kirby, camp


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-12/B6: provider TURN_ENDED outcome=DONE completes a workkey without journal proof")
def test_provider_done_signal_without_proof_does_not_complete_the_workkey(tmp_path):
    _engine, kirby, camp = _working(tmp_path)
    signals = tmp_path / "signals.log"
    signals.write_text("TURN_ENDED outcome=DONE checkpoint=provider says done\n", encoding="utf-8")
    host_loop.run_once(kirby, "S1", signals, {"offset": 0, "last_tick": 0.0, "notified": {}})
    fresh = Kirby(camp, "host-a")
    fresh._load()
    receipts = camp.parent / "receipts.jsonl"
    done_receipts = [json.loads(l) for l in receipts.read_text().splitlines()] if receipts.exists() else []
    done_receipts = [r for r in done_receipts if r.get("workkey") == "WK-1" and r.get("outcome") == "DONE"]
    assert fresh.workkeys["WK-1"].state != "DONE" and done_receipts == [], (
        fresh.workkeys["WK-1"].state, done_receipts)


def test_guard_finish_turn_without_journal_proof_is_not_proven(tmp_path):
    ctrl = Controller(tmp_path / "home").boot()
    try:
        engine, kirby, _camp = _working(tmp_path, ctrl)
        token = kirby.sessions["S1"].token
        assert engine.finish_turn("S1", "WK-1", token, task_id_for("WK-1")) == NOT_PROVEN
    finally:
        ctrl.stop()
