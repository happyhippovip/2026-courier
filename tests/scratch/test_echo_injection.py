import json
import subprocess
from pathlib import Path
import sys

REPO = Path(__file__).parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))
from mac_worker.daemon import run_native

task = {
    "task_id": "test",
    "action": "echo",
    "instruction": "echo test; echo INJECTED > injected.txt"
}
config = {}
res = run_native(task, config)
print(res)
if Path("injected.txt").exists():
    print("INJECTION SUCCEEDED")
    Path("injected.txt").unlink()
else:
    print("NO INJECTION")
