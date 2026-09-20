import sys, json
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle
path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
record = bundle["record"]
proven = record.get("PROVEN_EDGES", [])
unproven = record.get("UNPROVEN_EDGES", [])

print("PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION in proven:", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION" in proven)
print("PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION in unproven:", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION" in unproven)
