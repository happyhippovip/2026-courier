"""Probe: engine crash between Kirby receipt append and Kirby _save -> duplicate receipt?"""
import hashlib, json, sys, tempfile
from pathlib import Path
from courier_core.controller import Controller
from courier_core.verification import Verdict
from courier_runtime import continuity
from courier_runtime.ledger_engine import LedgerEngine

GOLD = b"X"; SHA = hashlib.sha256(GOLD).hexdigest()
def ver(task, result, home):
    a = result.payload.get("artifacts") or []
    return Verdict(bool(a) and a[0]["sha256"] == SHA, "x")
class C:
    t = 1000.0
    def __call__(self): return self.t
tmp = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
clock = C()
ctrl = Controller(tmp / "home", verifier=lambda a: ver, clock=clock).boot()
eng = LedgerEngine(ctrl, tmp / "camp" / "kirby.json", "host-a")
eng.add_workkeys(["WK-1", "WK-2"]); eng.open_slot("S1", "local")
wk, tok = eng.next("S1")
body = {"adapter": "synthetic", "params": {"estimated_cost_eur": 0.0}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 10}
tid = eng.submit(wk, body)
c = ctrl.claim({"worker_id": "w"}); ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w"})
(tmp / "home" / "o").write_bytes(GOLD)
ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": "r1", "outcome": "success", "artifacts": [{"path": "o", "sha256": SHA}]})
ctrl.drain()
# crash: receipt appended, then process dies before _save
orig = continuity.Kirby._save
state = {"n": 0}
def crashing_save(self):
    if any(w.state == continuity.DONE for w in self.workkeys.values()) and state["n"] == 0:
        state["n"] += 1
        raise SystemExit("killed before save")
    return orig(self)
continuity.Kirby._save = crashing_save
try:
    eng.finish_turn("S1", wk, tok, tid)
except SystemExit as e:
    print("crash:", e)
continuity.Kirby._save = orig
# restart
eng2 = LedgerEngine(ctrl, tmp / "camp" / "kirby.json", "host-a")
print("after restart next:", eng2.next("S1"))
print("finish again:", eng2.finish_turn("S1", wk, tok, tid))
rec = (tmp / "camp" / "receipts.jsonl").read_text().splitlines()
print("receipts for WK-1:", sum(json.loads(l)["workkey"] == "WK-1" for l in rec))
print("D08 probe: changed body same workkey ->", eng2.submit(wk, dict(body, params={"estimated_cost_eur": 0.0, "other": 1})) == tid)
ctrl.stop()
