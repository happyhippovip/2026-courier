import json
import sys
from pathlib import Path
repo_dir = Path(".").resolve()
sys.path.insert(0, str(repo_dir / "scripts"))
from agent_handoff_ledger import update, load_bundle

path = repo_dir / "test_tmp.json"
bundle = load_bundle(path)
guard = bundle["acceptance_guard"]

try:
    bundle = update(path, bundle["revision"], {"CLEAN_IDLE": "NO"}, "Google-Antigravity", 5.0, guard)
except Exception as e:
    print("ERROR:", e)
