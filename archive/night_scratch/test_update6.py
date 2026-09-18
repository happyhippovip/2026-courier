import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update

path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
revision = bundle["revision"]
record = bundle["record"]
proven = list(record.get("PROVEN_EDGES", []))
unproven = list(record.get("UNPROVEN_EDGES", []))

edge_name = "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION"
if edge_name and edge_name not in proven and edge_name != "CLEAN_IDLE_ACHIEVED":
    proven.append(edge_name)
if edge_name in unproven:
    unproven.remove(edge_name)

updates = {}
updates["PROVEN_EDGES"] = proven
updates["UNPROVEN_EDGES"] = unproven

print("Equal proven?", updates["PROVEN_EDGES"] == record.get("PROVEN_EDGES"))
print("Equal unproven?", updates["UNPROVEN_EDGES"] == record.get("UNPROVEN_EDGES"))

try:
    update(path, revision, updates, "Google-Antigravity", 5.0, bundle["acceptance_guard"])
    print("Success")
except Exception as e:
    print("Error:", type(e), str(e))
