import os
import sys
import copy
from pathlib import Path
sys.path.insert(0, os.path.abspath("scripts"))
from agent_handoff_ledger import load_bundle, update

path = Path("agent_handoff_ledger.json")
bundle = load_bundle(path)
updates = {
    "STATUS": "READY",
    "FIRST_CAUSAL_BLOCKER": "NONE",
    "CLEAN_IDLE": "NO"
}
update(path, bundle["revision"], updates, "Google-Antigravity", 5.0)
print("Reset STATUS and FIRST_CAUSAL_BLOCKER!")
