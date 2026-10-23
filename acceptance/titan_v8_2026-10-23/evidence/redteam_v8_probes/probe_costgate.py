"""Probe: CostGate admits included-quota resources on a caller-asserted 0.0 (no provider-verified marker)."""
from scripts.resource_policy import CostGate
for r in ("chatgpt_plus_codex", "google_antigravity_plus", "windows_native"):
    v = CostGate.evaluate_spend_request(r, estimated_cost_eur=0.0)
    print(r, v["allowed"], v["reason"])
from courier_worker.adapters import provider_exec as pe
print("agy admit_cost:", pe.admit_cost("agy"), "| evaluate_cost_gate self-0.0:", pe.evaluate_cost_gate({"provider":"agy","estimated_cost_eur":0.0}, None))
try:
    print("10**400:", pe.evaluate_cost_gate({"provider":"agy","estimated_cost_eur":10**400}, None))
except Exception as e:
    print("10**400 raises", type(e).__name__)
