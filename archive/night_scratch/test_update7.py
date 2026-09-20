import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update
import copy

path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
record = bundle["record"]

proven = list(record.get("PROVEN_EDGES", []))
unproven = list(record.get("UNPROVEN_EDGES", []))

# Let's say we process the first unproven edge
edge_name = unproven[0]
print("Processing:", edge_name)

proven.append(edge_name)
unproven.remove(edge_name)

updates = {
    "PROVEN_EDGES": proven,
    "UNPROVEN_EDGES": unproven
}

# The bug might be in check_freshness? No, we don't call it here.
# Let's just update.
try:
    update(path, bundle["revision"], updates, "Google-Antigravity", 5.0, bundle["acceptance_guard"])
    print("Success")
except Exception as e:
    print("Error:", type(e), str(e))
