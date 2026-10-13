"""GAP-B repro: oversized local_shell evidence accepted unbounded (origin base)."""
import os
import sys
import tempfile

sys.path.insert(0, os.environ.get("COURIER_PRISTINE_TREE", r"C:\tmp\courier-evidence"))

from adapters import local_shell
from courier_worker.host import ContainmentError, collect_artifacts

workdir = tempfile.mkdtemp(prefix="repro-evidence-")
argv = [sys.executable, "-c", "open('out.txt','wb').write(b'x'*20*1024*1024)"]
res = local_shell.run({"command": argv, "write": "out.txt", "timeout_s": 120}, workdir)
print("adapter outcome:", res.outcome,
      "| size:", res.artifacts[0]["size"] if res.artifacts else None)
assert res.outcome == "success", "expected current code to accept oversized evidence"
try:
    collect_artifacts(workdir)
    print("collect_artifacts: no error (unexpected)")
except ContainmentError as exc:
    print("collect_artifacts:", type(exc).__name__, "-", exc)
print("REPRO-B CONFIRMED")
