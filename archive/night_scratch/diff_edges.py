import sys, json
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle

bundle = load_bundle(Path("agent_handoff_ledger.json"))
all_edges = set(bundle["record"]["PROVEN_EDGES"] + bundle["record"]["UNPROVEN_EDGES"])

from scripts.courier_continue import PLAN
plan_set = set(PLAN)

print("Missing:", plan_set - all_edges)
