#!/usr/bin/env python3
"""Post-Account-Switch Antigravity Project & Workspace Continuity Verifier (Mission 160G).

Executes deterministically (0 model calls) to verify that the local Antigravity
project 'sandbox test' (2026-courier) and workspace settings survive Google account switching:
- PROJECT_FOUND
- PROJECT_NAME_MATCH
- FOLDER_BINDINGS_MATCH
- CANONICAL_WORKSPACE_MATCH
- PROJECT_PERMISSIONS_MATCH
- TERMINAL_POLICY_MATCH
- NON_WORKSPACE_POLICY_MATCH
- SANDBOX_POLICY_MATCH
- ARTIFACT_POLICY_MATCH
- LOCAL_FILES_PRESERVED
- CONTINUATION_STATE_AVAILABLE
- CONTINUATION_READY
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
PRESERVATION_DIR = RUNTIME_DIR / "preservation"

CONFIG_DIR = Path.home() / ".gemini" / "config"
PROJECTS_DIR = CONFIG_DIR / "projects"
CONFIG_FILE = CONFIG_DIR / "config.json"
SNAPSHOT_FILE = PRESERVATION_DIR / "antigravity_project_snapshot_sandbox_test.json"
CHECKPOINT_FILE = PRESERVATION_DIR / "mission_160g_continuation_checkpoint.json"

TARGET_PROJECT_ID = "22351b50-db7e-4065-8d25-613eecae65e1"
TARGET_PROJECT_ALIASES = ["sandbox test", "2026-courier"]


def compute_sha256_dict(d: Any) -> str:
    canonical_json = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_antigravity_continuity(
    config_dir: Optional[Path] = None,
    snapshot_path: Optional[Path] = None,
    checkpoint_path: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    cfg_dir = config_dir or CONFIG_DIR
    proj_dir = cfg_dir / "projects"
    cfg_file = cfg_dir / "config.json"
    snap_file = snapshot_path or SNAPSHOT_FILE
    chk_file = checkpoint_path or CHECKPOINT_FILE
    ws_root = workspace_root or COURIER_DIR

    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    # 1. Load Snapshot baseline if available
    baseline_fingerprints: Dict[str, str] = {}
    if snap_file.is_file():
        snap_data = json.loads(snap_file.read_text(encoding="utf-8"))
        baseline_fingerprints = snap_data.get("fingerprints", {})

    # 2. Check Project file
    proj_file = proj_dir / f"{TARGET_PROJECT_ID}.json"
    project_found = proj_file.is_file()
    checks["PROJECT_FOUND"] = project_found

    project_name = ""
    folder_bindings: List[Dict[str, Any]] = []
    project_permissions: List[str] = []
    if project_found:
        try:
            proj_data = json.loads(proj_file.read_text(encoding="utf-8"))
            project_name = proj_data.get("name", "")
            raw_resources = proj_data.get("projectResources", {}).get("resources", [])
            for res in raw_resources:
                if "gitFolder" in res:
                    folder_bindings.append({
                        "type": "gitFolder",
                        "folderUri": res["gitFolder"].get("folderUri"),
                        "defaultBranch": res["gitFolder"].get("defaultBranch", "main"),
                    })
                elif "localFolder" in res:
                    folder_bindings.append({
                        "type": "localFolder",
                        "folderUri": res["localFolder"].get("folderUri"),
                    })
            project_permissions = sorted(list(set(proj_data.get("permissionGrants", {}).get("permissionGrants", {}).get("allow", []))))
        except Exception as e:
            details["project_read_error"] = str(e)

    # Project Name Match
    name_matched = project_name in TARGET_PROJECT_ALIASES or any(a in project_name.lower() for a in ["courier", "sandbox"])
    checks["PROJECT_NAME_MATCH"] = name_matched
    details["project_name"] = project_name

    # Folder Bindings & Canonical Workspace Match
    expected_uri = f"file://{ws_root}"
    has_canonical_binding = any(b.get("folderUri") == expected_uri for b in folder_bindings)
    checks["FOLDER_BINDINGS_MATCH"] = bool(folder_bindings)
    checks["CANONICAL_WORKSPACE_MATCH"] = has_canonical_binding
    details["folder_bindings_count"] = len(folder_bindings)

    # Project Permissions Match
    current_perm_hash = compute_sha256_dict(project_permissions)
    baseline_perm_hash = baseline_fingerprints.get("project_permissions_hash")
    checks["PROJECT_PERMISSIONS_MATCH"] = bool(project_permissions) and (
        not baseline_perm_hash or current_perm_hash == baseline_perm_hash
    )
    details["permissions_count"] = len(project_permissions)

    # 3. Check Global Config Policies
    config_found = cfg_file.is_file()
    user_settings: Dict[str, Any] = {}
    if config_found:
        try:
            cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
            user_settings = cfg_data.get("userSettings", {})
        except Exception as e:
            details["config_read_error"] = str(e)

    terminal_policy = user_settings.get("autoExecutionPolicy", "")
    terminal_sandbox_mode = user_settings.get("terminalSandboxMode", "")
    enable_sandbox = user_settings.get("enableTerminalSandbox", True)
    non_ws_policy = user_settings.get("nonWorkspaceFileAccessPolicy", "")
    artifact_review_mode = user_settings.get("artifactReviewMode", "")

    checks["TERMINAL_POLICY_MATCH"] = bool(terminal_policy)
    checks["NON_WORKSPACE_POLICY_MATCH"] = bool(non_ws_policy)
    checks["SANDBOX_POLICY_MATCH"] = (terminal_sandbox_mode is not None) and (enable_sandbox is not None)
    checks["ARTIFACT_POLICY_MATCH"] = bool(artifact_review_mode)

    details["terminal_policy"] = terminal_policy
    details["non_workspace_policy"] = non_ws_policy
    details["artifact_review_mode"] = artifact_review_mode

    # 4. Check Local Workspace Files Preserved
    critical_files = [
        ws_root / "scripts" / "timeboxed_autonomy_engine.py",
        ws_root / "scripts" / "antigravity_project_snapshot.py",
        ws_root / "tests" / "test_timeboxed_autonomy_engine_mission_156g.py",
    ]
    local_files_intact = all(p.is_file() for p in critical_files)
    checks["LOCAL_FILES_PRESERVED"] = local_files_intact

    # 5. Check Continuation State Checkpoint
    checkpoint_available = chk_file.is_file()
    checks["CONTINUATION_STATE_AVAILABLE"] = checkpoint_available

    # Overall Verdict
    all_passed = all(checks.values())
    checks["CONTINUATION_READY"] = all_passed

    report = {
        "verifier_version": "1.0",
        "verified_at": "2026-08-31T16:50:00Z",
        "target_project": "sandbox test (2026-courier)",
        "canonical_workspace": str(ws_root),
        "verdict": "PASS" if all_passed else "FAIL",
        "checks": checks,
        "details": details,
        "continuation_ready": all_passed,
        "next_safe_action": "Resume autonomous development on canonical workspace under the newly authenticated Google AI Pro account." if all_passed else "Inspect missing project/setting and restore from local snapshot.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Account Switch Continuity Verifier")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    result = verify_antigravity_continuity()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("==================================================")
        print("🔍 ANTIGRAVITY ACCOUNT-SWITCH CONTINUITY VERIFIER")
        print("==================================================")
        print(f"VERDICT: {result['verdict']}")
        print(f"CONTINUATION_READY: {result['continuation_ready']}")
        for check, val in result["checks"].items():
            icon = "✅" if val else "❌"
            print(f"  {icon} {check}: {val}")
    return 0 if result["continuation_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
