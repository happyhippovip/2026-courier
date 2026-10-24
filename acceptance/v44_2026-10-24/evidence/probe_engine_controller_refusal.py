"""V44: engine cost gate admits, controller F-C1 gate refuses (adapter without COST_CLASS). Does the slot move on?"""
import json, tempfile
from pathlib import Path
from courier_core.controller import Controller, ApiError
from courier_runtime.ledger_engine import LedgerEngine, CostBlocked

tmp = Path(tempfile.mkdtemp())
ctrl = Controller(tmp / "ctrl").boot()
eng = LedgerEngine(ctrl, tmp / "camp" / "kirby.json", "host-a")
eng.add_workkeys(["WK-1", "WK-2"]); eng.open_slot("S1", "local")
wk, tok = eng.next("S1")
body = {"adapter": "telegram_delivery", "params": {"estimated_cost_eur": 0.0}, "effect_class": "idempotent",
        "max_attempts": 1, "lease_ttl_s": 10}
try:
    print("submit ->", eng.submit(wk, body, slot="S1", token=tok))
except CostBlocked as exc:
    print("CostBlocked (slot parks):", exc)
except ApiError as exc:
    print("ApiError escapes engine:", exc.status, exc.code)
state = json.loads((tmp / "camp" / "kirby.json").read_text())
print("WK-1 state:", state["workkeys"]["WK-1"]["state"], "| next for S1:", eng.next("S1"))
ctrl.stop()
