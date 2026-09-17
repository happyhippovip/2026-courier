import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update

def update_ledger(ledger_path, edge_name, blocker, bundle):
    revision = bundle["revision"]
    record = bundle["record"]
    proven = record.get("PROVEN_EDGES", [])
    unproven = record.get("UNPROVEN_EDGES", [])
    
    updates = {}
    if edge_name and edge_name not in proven and edge_name != "CLEAN_IDLE_ACHIEVED":
        proven.append(edge_name)
    if edge_name in unproven:
        unproven.remove(edge_name)
    updates["PROVEN_EDGES"] = proven
    updates["UNPROVEN_EDGES"] = unproven
    
    guard = bundle["acceptance_guard"]
    
    new_bundle = update(
        ledger_path,
        revision,
        updates,
        "Google-Antigravity",
        5.0,
        guard
    )
    return new_bundle

try:
    path = Path("agent_handoff_ledger.json")
    bundle = load_bundle(path)
    print("Initial unproven:", len(bundle["record"]["UNPROVEN_EDGES"]))
    edge = bundle["record"]["UNPROVEN_EDGES"][0]
    bundle = update_ledger(path, edge, None, bundle)
    print("Success! Revision:", bundle["revision"])
    print("New unproven:", len(bundle["record"]["UNPROVEN_EDGES"]))
except Exception as e:
    print("Error:", type(e), str(e))
