import sys, json
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update

path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)

# Deduplicate UNPROVEN_EDGES while preserving order
seen = set()
deduped_unproven = []
for edge in bundle["record"]["UNPROVEN_EDGES"]:
    if edge not in seen:
        seen.add(edge)
        deduped_unproven.append(edge)

# Same for PROVEN_EDGES
seen = set()
deduped_proven = []
for edge in bundle["record"]["PROVEN_EDGES"]:
    if edge not in seen:
        seen.add(edge)
        deduped_proven.append(edge)

updates = {
    "UNPROVEN_EDGES": deduped_unproven,
    "PROVEN_EDGES": deduped_proven
}

update(path, bundle["revision"], updates, "Google-Antigravity", 5.0, bundle["acceptance_guard"])
print("Fixed!")
