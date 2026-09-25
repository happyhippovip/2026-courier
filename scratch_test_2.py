import os
import sys
sys.path.insert(0, os.path.abspath("scripts"))
from agent_handoff_ledger import load_bundle, update, RevisionConflictError
from pathlib import Path

bundle = load_bundle(Path("agent_handoff_ledger.json"))
expected = bundle["revision"] - 1

try:
    update(Path("agent_handoff_ledger.json"), expected, {"STATUS": "READY"}, "Google-Antigravity", 5.0)
except Exception as e:
    print(f"str(e): {str(e)}")
    print(f"repr(e): {repr(e)}")
    if "revision conflict" in str(e).lower():
        print("MATCHED!")
