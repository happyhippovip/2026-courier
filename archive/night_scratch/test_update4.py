import sys, json
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle
path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
print("Unproven:", len(bundle["record"]["UNPROVEN_EDGES"]))
