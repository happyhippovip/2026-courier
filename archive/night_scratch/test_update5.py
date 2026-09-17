import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update

path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
print("Initial unproven:", len(bundle["record"]["UNPROVEN_EDGES"]))
edge = bundle["record"]["UNPROVEN_EDGES"][0]
print("Edge:", edge)

unproven = bundle["record"].get("UNPROVEN_EDGES", [])
unproven.remove(edge)

updates = {"UNPROVEN_EDGES": unproven}
print("Updates passed to update:", updates["UNPROVEN_EDGES"])

bundle2 = load_bundle(path)
print("bundle2 before update():", bundle2["record"]["UNPROVEN_EDGES"])

print("Are they equal?", updates["UNPROVEN_EDGES"] == bundle2["record"]["UNPROVEN_EDGES"])

new_bundle = update(path, bundle["revision"], updates, "Google-Antigravity", 5.0, bundle["acceptance_guard"])
print("After update:", len(new_bundle["record"]["UNPROVEN_EDGES"]))
