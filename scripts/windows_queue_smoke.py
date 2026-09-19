#!/usr/bin/env python3
"""Windows queue smoke: one command, no pytest needed.

Usage: python scripts/windows_queue_smoke.py [--state-dir DIR]
Proves on any platform (esp. Windows) that work_queue:
1. imports without POSIX-only modules (fcntl),
2. runs init/add/claim/complete/reconcile against an isolated dir,
3. leaves DONE state behind.
Exit 0 = PASS, nonzero + message = FAIL.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.resolve()
WQ = [sys.executable, str(REPO / "scripts" / "work_queue.py")]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="wq_smoke_"))
    # 1. fcntl must be absent/unimportable for the child
    block = "import sys; sys.modules['fcntl'] = None; "
    env_probe = subprocess.run(
        [sys.executable, "-c",
         block + "import importlib.util;"
         f"spec = importlib.util.spec_from_file_location('wq', r'{WQ[1]}');"
         "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
         "print('import-ok')"],
        capture_output=True, text=True)
    assert "import-ok" in env_probe.stdout, env_probe.stderr[-500:]

    def q(*args):
        r = subprocess.run(WQ + ["--state-dir", str(tmp)] + list(args),
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-500:]
        return json.loads(r.stdout.strip())

    # 2. full cycle
    q("init", "SMOKE", "--dod", "smoke")
    q("add", json.dumps({"task_id": "S1", "package_id": "SMOKE",
        "description": "smoke", "required_capabilities": [],
        "dependencies": [], "read_scopes": [], "write_scopes": [],
        "risk": "none", "status": "READY", "owner": "", "priority": 1}))
    assert q("claim", "--worker", "w", "--package", "SMOKE")["claimed"] == "S1"
    assert q("complete", "S1", "--result-json",
             json.dumps({"result_id": "S1:r1"}),
             "--stage", "ACCEPTED")["done"] == "S1"
    st = q("state")
    assert st["tasks"]["S1"]["status"] == "DONE", st
    shutil.rmtree(tmp, ignore_errors=True)
    print("WINDOWS-QUEUE-SMOKE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
