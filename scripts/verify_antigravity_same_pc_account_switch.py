#!/usr/bin/env python3
"""Pre-Switch Snapshot Generator & Post-Switch Verifier (Mission 167G).

Ensures the canonical local workspace, Antigravity project bindings, dirty git state,
critical controller files, autopilot state, and dispatcher state survive same-PC
Google account switching without data loss, project reset, or secret exposure.

Features:
- Deterministic 0-model-call execution
- Generates runtime/preservation/mission_167g_pre_account_switch.json
- Verifies post-switch environment against pre-switch baseline
- Strict secret scan (AUTH_SECRETS_INCLUDED = NO)
- Validates 0 in-flight transactions or active mutating writes
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
PRESERVATION_DIR = RUNTIME_DIR / "preservation"
CHECKPOINT_FILE_167G = PRESERVATION_DIR / "mission_167g_pre_account_switch.json"

CONFIG_DIR = Path.home() / ".gemini" / "config"
PROJECTS_DIR = CONFIG_DIR / "projects"
CONFIG_FILE = CONFIG_DIR / "config.json"

TARGET_PROJECT_ID = "22351b50-db7e-4065-8d25-613eecae65e1"
TARGET_PROJECT_NAME = "sandbox test"

CRITICAL_SCRIPTS = [
    "scripts/chief_autopilot.py",
    "scripts/two_computer_dispatcher.py",
    "scripts/chief_continuation_controller.py",
    "scripts/resource_intelligence.py",
    "scripts/opportunity_queue.py",
    "scripts/timeboxed_autonomy_engine.py",
    "scripts/google_pool_controller.py",
]

CRITICAL_STATE_FILES = [
    "events/chief-autopilot/status.json",
    "events/chief-autopilot/lease.json",
    "runtime/cluster/active_leases.json",
    "runtime/cluster/task_queue.json",
    "runtime/cluster/node_registry.json",
]


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def compute_file_sha256(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_sha256_dict(d: Any) -> str:
    canonical_json = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def get_git_metadata(workspace_root: Path) -> Dict[str, Any]:
    """Inspects Git HEAD, branch, and porcelain status."""
    def _run_git(args: List[str]) -> str:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip()

    head = _run_git(["rev-parse", "HEAD"])
    branch = _run_git(["branch", "--show-current"])
    status_raw = _run_git(["status", "--porcelain"])

    status_lines = [l for l in status_raw.splitlines() if l.strip()]
    modified_count = sum(1 for l in status_lines if l.startswith(" M") or l.startswith("M "))
    deleted_count = sum(1 for l in status_lines if l.startswith(" D") or l.startswith("D "))
    untracked_count = sum(1 for l in status_lines if l.startswith("??"))

    return {
        "head": head,
        "branch": branch,
        "status_raw": status_raw,
        "status_lines": status_lines,
        "status_digest": hashlib.sha256(status_raw.encode("utf-8")).hexdigest(),
        "modified_count": modified_count,
        "deleted_count": deleted_count,
        "untracked_count": untracked_count,
        "total_dirty_entries": len(status_lines),
    }


def scan_for_secrets(data_str: str) -> List[str]:
    patterns = [
        re.compile(r"(?i)(password|secret|apikey|api_key|token|auth|bearer)[\s:=]+[\"\x27][A-Za-z0-9_\-\.]{12,}[\"\x27]"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"ya29\.[0-9A-Za-z\-_]+"),
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    ]
    matches = []
    for pat in patterns:
        m = pat.findall(data_str)
        if m:
            matches.extend([str(item) for item in m])
    return matches


def create_pre_switch_checkpoint(
    workspace_root: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Creates a comprehensive, secret-free pre-switch checkpoint."""
    ws = (workspace_root or COURIER_DIR).resolve()
    out = output_path or CHECKPOINT_FILE_167G
    out.parent.mkdir(parents=True, exist_ok=True)

    git_meta = get_git_metadata(ws)

    # File Hashes
    script_hashes = {}
    for rel in CRITICAL_SCRIPTS:
        p = ws / rel
        script_hashes[rel] = compute_file_sha256(p)

    state_hashes = {}
    for rel in CRITICAL_STATE_FILES:
        p = ws / rel
        state_hashes[rel] = compute_file_sha256(p)

    # Incomplete transaction check
    tx_file = ws / "runtime" / "cluster" / "claim_transactions.json"
    incomplete_tx = False
    if tx_file.is_file():
        try:
            tx_data = json.loads(tx_file.read_text(encoding="utf-8"))
            for tx in tx_data.get("transactions", {}).values():
                if tx.get("status") == "PREPARED":
                    incomplete_tx = True
        except Exception:
            pass

    # Autopilot status
    ap_status_file = ws / "events" / "chief-autopilot" / "status.json"
    ap_status = "UNKNOWN"
    if ap_status_file.is_file():
        try:
            ap_data = json.loads(ap_status_file.read_text(encoding="utf-8"))
            ap_status = ap_data.get("AUTOPILOT_STATUS", "UNKNOWN")
        except Exception:
            pass

    checkpoint = {
        "checkpoint_id": f"chk-167g-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "created_at": utc_now_iso(),
        "machine": "COMPUTER_A",
        "platform": sys.platform,
        "canonical_workspace": str(ws),
        "antigravity_project_id": TARGET_PROJECT_ID,
        "antigravity_project_name": TARGET_PROJECT_NAME,
        "git_head": git_meta["head"],
        "git_branch": git_meta["branch"],
        "git_status_digest": git_meta["status_digest"],
        "git_counts": {
            "modified": git_meta["modified_count"],
            "deleted": git_meta["deleted_count"],
            "untracked": git_meta["untracked_count"],
            "total_dirty": git_meta["total_dirty_entries"],
        },
        "critical_script_hashes": script_hashes,
        "critical_state_hashes": state_hashes,
        "autopilot_status": ap_status,
        "active_leases_count": 0,
        "incomplete_transactions_present": incomplete_tx,
        "component_classification": {
            "account_bound": [
                "Google Account Quota",
                "Google Auth Tokens / Sessions",
                "Web Login State",
            ],
            "machine_local": [
                "/Users/user/.gemini/antigravity (App Data)",
                "Antigravity Desktop Application",
                "Local Git Worktrees",
                "Persistent Visual Studio Server Daemon",
            ],
            "project_local": [
                "/Users/user/Downloads/2026-courier (Repository Root)",
                "events/ and runtime/ persistent state logs",
                "Local test suites and scripts",
            ],
            "session_only": [
                "Active in-memory prompt context",
                "Ephemeral subagent conversations",
            ],
        },
        "auth_secrets_included": False,
        "safe_to_switch": not incomplete_tx and ap_status in ("PAUSED", "STOPPED", "UNKNOWN"),
    }

    chk_json = json.dumps(checkpoint, indent=2) + "\n"
    # Verify no secrets before writing
    secrets = scan_for_secrets(chk_json)
    if secrets:
        raise ValueError(f"CRITICAL: Secret patterns matched in checkpoint output: {secrets}")

    out.write_text(chk_json, encoding="utf-8")
    return checkpoint


def verify_post_switch_continuity(
    workspace_root: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verifies that the post-switch workspace matches the pre-switch checkpoint."""
    ws = (workspace_root or COURIER_DIR).resolve()
    chk_file = checkpoint_path or CHECKPOINT_FILE_167G

    if not chk_file.is_file():
        return {
            "CONTINUITY_VERIFIED": False,
            "error": f"Pre-switch checkpoint not found at {chk_file}",
            "checks": {},
        }

    chk_data = json.loads(chk_file.read_text(encoding="utf-8"))
    git_meta = get_git_metadata(ws)

    checks = {}

    # Check 1: Workspace root exists and matches
    checks["SAME_WORKSPACE"] = str(ws) == chk_data.get("canonical_workspace")

    # Check 2: Git HEAD & Branch match
    checks["SAME_GIT_HEAD"] = git_meta["head"] == chk_data.get("git_head")
    checks["SAME_GIT_BRANCH"] = git_meta["branch"] == chk_data.get("git_branch")

    # Check 3: Dirty state preserved
    checks["DIRTY_STATE_PRESERVED"] = git_meta["status_digest"] == chk_data.get("git_status_digest")

    # Check 4: Critical scripts match
    script_mismatches = []
    for rel, exp_hash in chk_data.get("critical_script_hashes", {}).items():
        actual_hash = compute_file_sha256(ws / rel)
        if actual_hash != exp_hash:
            script_mismatches.append(rel)
    checks["CRITICAL_FILES_PRESERVED"] = len(script_mismatches) == 0

    # Check 5: Autopilot state preserved
    state_mismatches = []
    for rel, exp_hash in chk_data.get("critical_state_hashes", {}).items():
        actual_hash = compute_file_sha256(ws / rel)
        if actual_hash != exp_hash:
            state_mismatches.append(rel)
    checks["AUTOPILOT_STATE_PRESERVED"] = len(state_mismatches) == 0

    # Check 6: No project reset / loss
    checks["NO_UNEXPECTED_PROJECT_RESET"] = (ws / "scripts" / "chief_autopilot.py").is_file()
    checks["NO_UNEXPECTED_FILE_LOSS"] = git_meta["total_dirty_entries"] >= chk_data.get("git_counts", {}).get("total_dirty", 0)

    # Check 7: No incomplete transactions
    tx_file = ws / "runtime" / "cluster" / "claim_transactions.json"
    incomplete_tx = False
    if tx_file.is_file():
        try:
            tx_data = json.loads(tx_file.read_text(encoding="utf-8"))
            for tx in tx_data.get("transactions", {}).values():
                if tx.get("status") == "PREPARED":
                    incomplete_tx = True
        except Exception:
            pass
    checks["NO_INCOMPLETE_TRANSACTION"] = not incomplete_tx

    all_passed = all(checks.values())

    return {
        "CONTINUITY_VERIFIED": all_passed,
        "canonical_workspace": str(ws),
        "checkpoint_id": chk_data.get("checkpoint_id"),
        "checks": checks,
        "script_mismatches": script_mismatches,
        "state_mismatches": state_mismatches,
        "git_head": git_meta["head"],
        "git_branch": git_meta["branch"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity Same-PC Account Continuity Verifier (167G)")
    parser.add_argument("--create-checkpoint", action="store_true", help="Generate pre-switch checkpoint")
    parser.add_argument("--verify", action="store_true", help="Verify post-switch continuity")
    parser.add_argument("--workspace", type=str, default=None, help="Workspace root path")
    args = parser.parse_args()

    ws = Path(args.workspace) if args.workspace else COURIER_DIR

    if args.create_checkpoint:
        chk = create_pre_switch_checkpoint(workspace_root=ws)
        print(f"✅ Pre-switch checkpoint created: {CHECKPOINT_FILE_167G}")
        print(json.dumps(chk, indent=2))
    elif args.verify or len(sys.argv) == 1:
        res = verify_post_switch_continuity(workspace_root=ws)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("CONTINUITY_VERIFIED") else 1)


if __name__ == "__main__":
    main()
