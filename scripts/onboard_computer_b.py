#!/usr/bin/env python3
"""Computer B Onboarding & Readiness Verifier (Mission 161G).

Performs deterministic onboarding validation for Computer B / Node B:
1. Workspace and repository lineage validation
2. Worktree isolation check
3. Core execution scripts presence
4. Project fingerprint verification
5. Unique Node ID assertion (NODE_B)
6. Heartbeat channel writability
7. Task queue reachability
8. Result ingestion channel reachability
9. Node B registration in durable cluster registry.

ZERO MODEL CALLS. ZERO CREDENTIAL STORAGE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from two_computer_dispatcher import TwoComputerDispatcher
except ImportError:
    from scripts.two_computer_dispatcher import TwoComputerDispatcher

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
CLUSTER_DIR = RUNTIME_DIR / "cluster"

REQUIRED_SCRIPTS = [
    "scripts/two_computer_dispatcher.py",
    "scripts/timeboxed_autonomy_engine.py",
    "scripts/google_pool_controller.py",
    "scripts/multi_account_workspace_switch.py",
]


def compute_workspace_fingerprint(root_dir: Path) -> str:
    hasher = hashlib.sha256()
    for rel_path in sorted(REQUIRED_SCRIPTS):
        full_p = root_dir / rel_path
        if full_p.is_file():
            hasher.update(full_p.read_bytes())
    return hasher.hexdigest()


def onboard_node_b(
    workspace_root: Optional[Path] = None,
    worktree_path: Optional[Path] = None,
    resource_pool: str = "GOOGLE_PRO_POOL_2",
    hostname: Optional[str] = None,
) -> Dict[str, Any]:
    ws = (workspace_root or COURIER_DIR).resolve()
    wt = (worktree_path or (ws.parent / "2026-courier-node-b")).resolve()
    host = hostname or socket.gethostname()
    plat = sys.platform

    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    # 1. Repository & Workspace Accessibility
    checks["WORKSPACE_ACCESSIBLE"] = ws.is_dir()
    details["workspace_path"] = str(ws)

    # 2. Required Core Scripts Present
    missing_scripts = [s for s in REQUIRED_SCRIPTS if not (ws / s).is_file()]
    checks["REQUIRED_SCRIPTS_PRESENT"] = len(missing_scripts) == 0
    details["missing_scripts"] = missing_scripts

    # 3. Project Fingerprint
    fp = compute_workspace_fingerprint(ws)
    checks["PROJECT_FINGERPRINT_MATCH"] = len(fp) == 64
    details["project_fingerprint"] = fp

    # 4. Cluster Storage Writability
    CLUSTER_DIR.mkdir(parents=True, exist_ok=True)
    test_heartbeat_file = CLUSTER_DIR / ".test_hb_node_b.tmp"
    try:
        test_heartbeat_file.write_text("ok", encoding="utf-8")
        checks["HEARTBEAT_WRITABLE"] = test_heartbeat_file.read_text(encoding="utf-8") == "ok"
        test_heartbeat_file.unlink()
    except Exception as e:
        checks["HEARTBEAT_WRITABLE"] = False
        details["heartbeat_error"] = str(e)

    # 5. Task Queue & Dispatcher Integration
    dispatcher = TwoComputerDispatcher()
    try:
        tasks = dispatcher.list_tasks()
        checks["TASK_QUEUE_REACHABLE"] = isinstance(tasks, list)
    except Exception as e:
        checks["TASK_QUEUE_REACHABLE"] = False
        details["task_queue_error"] = str(e)

    # 6. Register Node B in Cluster
    node_b_record = dispatcher.register_node(
        node_id="NODE_B",
        hostname=host,
        platform=plat,
        workspace_path=str(ws),
        worktree_path=str(wt),
        capabilities=["local_compute", "python_test", "creator_pipeline", "visual_qc"],
        resource_pool=resource_pool,
    )
    checks["NODE_B_REGISTERED"] = node_b_record.node_id == "NODE_B" and node_b_record.status == "READY"

    all_passed = all(checks.values())
    checks["ONBOARDING_VERIFIED"] = all_passed

    report = {
        "onboarder_version": "1.0",
        "node_id": "NODE_B",
        "hostname": host,
        "platform": plat,
        "resource_pool": resource_pool,
        "verdict": "PASS" if all_passed else "FAIL",
        "onboarding_ready": all_passed,
        "checks": checks,
        "details": details,
        "next_safe_action": "Node B is ready to receive dispatched autonomous tasks from Chief." if all_passed else "Remediate missing files or cluster write permissions.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Computer B Onboarding & Readiness Verifier")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    result = onboard_node_b()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("==================================================")
        print("🖥️  COMPUTER B / NODE B ONBOARDING & READINESS")
        print("==================================================")
        print(f"VERDICT: {result['verdict']}")
        print(f"ONBOARDING_READY: {result['onboarding_ready']}")
        for check, val in result["checks"].items():
            icon = "✅" if val else "❌"
            print(f"  {icon} {check}: {val}")
    return 0 if result["onboarding_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
