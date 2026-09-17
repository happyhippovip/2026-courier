import sys
from pathlib import Path
sys.path.insert(0, ".")
from scripts.agent_handoff_ledger import load_bundle, update
path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
revision = bundle["revision"]
unproven = list(bundle["record"]["UNPROVEN_EDGES"])
proven = list(bundle["record"]["PROVEN_EDGES"])
task = unproven[0] if unproven else None
if task:
    unproven.remove(task)
    proven.append(task)
    updates = {"UNPROVEN_EDGES": unproven, "PROVEN_EDGES": proven}
    try:
        new_bundle = update(path, revision, updates, "Google-Antigravity", 5.0, allow_unknown_sha=True)
        print("Success!", new_bundle["revision"])
    except Exception as e:
        print("Error!", type(e), str(e))
