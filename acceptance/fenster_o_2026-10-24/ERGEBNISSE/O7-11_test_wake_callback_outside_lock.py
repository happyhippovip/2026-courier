"""O7-11 (B6): the wake callback must not run inside the campaign lock (deadlock).

On integration/v1 81bbf224 courier_runtime/host_loop.py:run_once (:58-87) takes no
lock; the callback at :81-85 runs with no lock held, and the LedgerEngine lock
(courier_runtime/ledger_engine.py:97-125, "Not re-entrant") is free. The deadlock
exists only in the code of PR #836 (run_once inside the campaign lock), see
acceptance/v34_review_2026-10-24/REV836_wake_callback_outside_lock.diff.
So this is NOT a strict xfail on the base: it passes here and is the regression
guard that fails (thread still alive after 5 s) on the unfixed #836 head.
"""
import threading

from courier_runtime import host_loop
from courier_runtime.continuity import Kirby
from courier_runtime.ledger_engine import LedgerEngine


def test_wake_callback_may_use_the_ledger_engine_without_deadlock(tmp_path):
    camp = tmp_path / "kirby.json"
    engine = LedgerEngine(None, camp, "host-a")
    engine.add_workkeys(["WK-1"])
    engine.open_slot("S1", "local")
    kirby = Kirby(camp, "host-a")
    kirby._load()
    kirby.wake("S1")
    signals = tmp_path / "signals.log"
    signals.write_text("")
    seen = []

    def on_wake_ready(slot, workkey, token):
        engine.next(slot)                       # takes the (non re-entrant) campaign lock
        seen.append(workkey)

    worker = threading.Thread(target=host_loop.run_once, daemon=True,
                              args=(kirby, "S1", signals, {"offset": 0, "last_tick": 0.0, "notified": {}}),
                              kwargs={"on_wake_ready": on_wake_ready})
    worker.start()
    worker.join(5)
    assert not worker.is_alive(), "run_once still blocked after 5 s: wake callback ran inside the lock"
    assert seen == ["WK-1"]
