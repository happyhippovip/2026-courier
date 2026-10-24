"""Does run_once invoke on_wake_ready while holding the campaign lock (engine callback deadlock)?"""
import sys, tempfile, threading
from pathlib import Path
from courier_runtime.continuity import Kirby
from courier_runtime.ledger_engine import LedgerEngine
from courier_runtime import host_loop

tmp = Path(tempfile.mkdtemp())
camp = tmp / "kirby.json"
engine = LedgerEngine(None, camp, "host-a")          # controller not needed for next()
engine.add_workkeys(["WK-1", "WK-2"])
engine.open_slot("S1", "local")
kirby = Kirby(camp, "host-a")
kirby._load()
print("wake:", kirby.wake("S1"), kirby.sessions["S1"].state)
sig = tmp / "signals.log"
sig.write_text("")
state = {"offset": 0, "last_tick": 0.0, "notified": {}}
seen = []

def on_wake_ready(slot, workkey, token):
    seen.append(("callback", workkey))
    engine.next(slot)                                 # a natural engine call from the callback
    seen.append(("engine.next returned", workkey))

t = threading.Thread(target=lambda: host_loop.run_once(kirby, "S1", sig, state, on_wake_ready=on_wake_ready, engine=engine), daemon=True)
t.start(); t.join(5)
print("DEADLOCK (still blocked after 5s)" if t.is_alive() else "no deadlock", seen)
