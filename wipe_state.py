import shutil
from pathlib import Path
import os
base = Path.home() / ".courier_runtime"
for d in ["goals", "tasks", "workers", "state", "ledger", "server"]:
    p = base / d
    if p.exists():
        shutil.rmtree(p)
f = base / "server_state.json"
if f.exists():
    f.unlink()

repo_state = Path("server/state")
if repo_state.exists():
    shutil.rmtree(repo_state)

