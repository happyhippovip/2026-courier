import os
import sys
sys.path.insert(0, os.path.abspath("scripts"))
from agent_handoff_ledger import load_bundle, update, RevisionConflictError
import copy
from pathlib import Path

bundle = load_bundle(Path("agent_handoff_ledger.json"))
expected = bundle["revision"] - 1  # Intentionally pass stale revision

try:
    update(Path("agent_handoff_ledger.json"), expected, {"STATUS": "READY"}, "Google-Antigravity", 5.0)
    print("SUCCESS")
except RevisionConflictError as e:
    print(f"THREW REVISION CONFLICT: {e}")
