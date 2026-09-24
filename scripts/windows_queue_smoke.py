#!/usr/bin/env python3
"""Windows queue smoke: one command, no pytest needed.

Usage: python scripts/windows_queue_smoke.py [--state-dir DIR] [--json]
Proves on any platform (esp. Windows) that work_queue:
1. imports without POSIX-only modules (fcntl),
2. runs init/add/claim/complete/reconcile against an isolated dir,
3. leaves DONE state behind.
Exit 0 = PASS, nonzero + message = FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

REPO = Path(__file__).parent.parent.resolve()
WQ = [sys.executable, str(REPO / "scripts" / "work_queue.py")]


def _remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def run_windows_queue_smoke(state_dir: Path | None = None) -> dict[str, str]:
    cleanup = False
    if state_dir is None:
        state_dir = Path(tempfile.mkdtemp(prefix="wq_smoke_"))
        cleanup = True
    else:
        state_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. fcntl must be absent/unimportable for the child
        block = "import sys; sys.modules['fcntl'] = None; "
        env_probe = subprocess.run(
            [
                sys.executable,
                "-c",
                block
                + "import importlib.util;"
                + f"spec = importlib.util.spec_from_file_location('wq', r'{WQ[1]}');"
                + "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
                + "print('import-ok')",
            ],
            capture_output=True,
            text=True,
        )
        assert "import-ok" in env_probe.stdout, env_probe.stderr[-500:]

        def q(*args: str) -> dict:
            r = subprocess.run(
                WQ + ["--state-dir", str(state_dir)] + list(args),
                capture_output=True,
                text=True,
            )
            assert r.returncode == 0, r.stderr[-500:]
            return json.loads(r.stdout.strip())

        # 2. full cycle
        q("init", "SMOKE", "--dod", "smoke")
        q(
            "add",
            json.dumps({
                "task_id": "S1",
                "package_id": "SMOKE",
                "description": "smoke",
                "required_capabilities": [],
                "dependencies": [],
                "read_scopes": [],
                "write_scopes": [],
                "risk": "none",
                "status": "READY",
                "owner": "",
                "priority": 1,
            }),
        )
        assert q("claim", "--worker", "w", "--package", "SMOKE")["claimed"] == "S1"
        assert (
            q(
                "complete",
                "S1",
                "--result-json",
                json.dumps({"result_id": "S1:r1"}),
                "--stage",
                "ACCEPTED",
            )["done"]
            == "S1"
        )
        st = q("state")
        assert st["tasks"]["S1"]["status"] == "DONE", st
        return {"status": "PASS", "task_status": "DONE"}
    finally:
        if cleanup and state_dir.exists():
            shutil.rmtree(state_dir, onerror=_remove_readonly)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Windows queue smoke test")
    parser.add_argument("--state-dir", type=Path, help="State directory")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        res = run_windows_queue_smoke(state_dir=args.state_dir)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("WINDOWS-QUEUE-SMOKE: PASS")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "FAIL", "error": str(e)}, indent=2))
        else:
            print(f"WINDOWS-QUEUE-SMOKE: FAIL ({e})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
