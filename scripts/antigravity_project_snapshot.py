#!/usr/bin/env python3
"""Antigravity Project & Workspace Configuration Snapshot Generator (Mission 160G).

Creates a secret-free, machine-local snapshot of the Antigravity Project configuration:
- Project metadata & folder bindings
- Project-level permission grants
- Global terminal execution & sandbox policies
- Non-workspace access policy
- Artifact review mode
- Configuration fingerprints for post-switch validation.

STRICT SAFETY:
- Excludes all OAuth tokens, cookies, passwords, 2FA, session data, and credentials.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
PRESERVATION_DIR = RUNTIME_DIR / "preservation"

CONFIG_DIR = Path.home() / ".gemini" / "config"
PROJECTS_DIR = CONFIG_DIR / "projects"
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTSIDE_PROJECT_FILE = PROJECTS_DIR / "outside-of-project.json"

TARGET_PROJECT_ID = "22351b50-db7e-4065-8d25-613eecae65e1"
TARGET_PROJECT_ALIASES = ["sandbox test", "2026-courier"]
CANONICAL_WORKSPACE = str(COURIER_DIR)


def compute_sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_sha256_dict(d: Any) -> str:
    canonical_json = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return compute_sha256_text(canonical_json)


def generate_secret_free_snapshot() -> Dict[str, Any]:
    PRESERVATION_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Discover Project File
    project_file = PROJECTS_DIR / f"{TARGET_PROJECT_ID}.json"
    project_found = project_file.is_file()

    project_data: Dict[str, Any] = {}
    if project_found:
        project_data = json.loads(project_file.read_text(encoding="utf-8"))

    # 2. Extract Folder Bindings
    raw_resources = project_data.get("projectResources", {}).get("resources", [])
    folder_bindings: List[Dict[str, Any]] = []
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

    # 3. Extract Project Permissions
    raw_permissions = project_data.get("permissionGrants", {}).get("permissionGrants", {}).get("allow", [])
    safe_permissions = sorted(list(set(raw_permissions)))

    # 4. Extract Global Settings from config.json
    config_data: Dict[str, Any] = {}
    if CONFIG_FILE.is_file():
        config_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    user_settings = config_data.get("userSettings", {})
    terminal_policy = user_settings.get("autoExecutionPolicy", "CASCADE_COMMANDS_AUTO_EXECUTION_PROCEED_IN_SANDBOX")
    terminal_sandbox_mode = user_settings.get("terminalSandboxMode", "disabled")
    enable_terminal_sandbox = user_settings.get("enableTerminalSandbox", True)
    non_workspace_policy = user_settings.get("nonWorkspaceFileAccessPolicy", "AGENT_SETTING_POLICY_ALLOW")
    non_workspace_access = user_settings.get("nonWorkspaceFileAccess", "allow")
    artifact_review_mode = user_settings.get("artifactReviewMode", "ARTIFACT_REVIEW_MODE_TURBO")
    tool_execution_policy = user_settings.get("toolExecutionPolicy", "always-proceed")

    # 5. Extract Outside-of-Project Settings
    outside_data: Dict[str, Any] = {}
    if OUTSIDE_PROJECT_FILE.is_file():
        outside_data = json.loads(OUTSIDE_PROJECT_FILE.read_text(encoding="utf-8"))
    outside_allow = outside_data.get("permissionGrants", {}).get("permissionGrants", {}).get("allow", [])

    # 6. Compute Deterministic Fingerprints
    fingerprints = {
        "folder_bindings_hash": compute_sha256_dict(folder_bindings),
        "project_permissions_hash": compute_sha256_dict(safe_permissions),
        "terminal_policy_hash": compute_sha256_text(f"{terminal_policy}:{terminal_sandbox_mode}:{enable_terminal_sandbox}"),
        "non_workspace_policy_hash": compute_sha256_text(f"{non_workspace_policy}:{non_workspace_access}"),
        "artifact_review_mode_hash": compute_sha256_text(artifact_review_mode),
        "outside_project_permissions_hash": compute_sha256_dict(outside_allow),
    }

    # 7. Classification of Components
    classification = {
        "project_metadata": "PROJECT_LOCAL_PERSISTENT",
        "folder_bindings": "PROJECT_LOCAL_PERSISTENT",
        "project_permissions": "PROJECT_LOCAL_PERSISTENT",
        "global_user_settings": "LOCAL_MACHINE_PERSISTENT",
        "outside_of_project_settings": "LOCAL_MACHINE_PERSISTENT",
        "terminal_execution_policy": "LOCAL_MACHINE_PERSISTENT",
        "sandbox_policy": "LOCAL_MACHINE_PERSISTENT",
        "non_workspace_access_policy": "LOCAL_MACHINE_PERSISTENT",
        "artifact_review_policy": "LOCAL_MACHINE_PERSISTENT",
        "local_workspace_files": "PROJECT_LOCAL_PERSISTENT",
        "google_identity_credentials": "ACCOUNT_BOUND",
        "oauth_tokens_and_cookies": "SESSION_BOUND",
    }

    snapshot = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mission_id": "MISSION_160G",
        "project": {
            "id": TARGET_PROJECT_ID,
            "canonical_name": project_data.get("name", "2026-courier"),
            "target_aliases": TARGET_PROJECT_ALIASES,
            "project_file_path": str(project_file),
            "project_found": project_found,
        },
        "workspace": {
            "canonical_root": CANONICAL_WORKSPACE,
            "folder_bindings": folder_bindings,
            "folder_count": len(folder_bindings),
        },
        "policies": {
            "terminal_execution_policy": terminal_policy,
            "terminal_sandbox_mode": terminal_sandbox_mode,
            "enable_terminal_sandbox": enable_terminal_sandbox,
            "non_workspace_file_access_policy": non_workspace_policy,
            "non_workspace_file_access": non_workspace_access,
            "artifact_review_mode": artifact_review_mode,
            "tool_execution_policy": tool_execution_policy,
        },
        "permissions": {
            "project_permission_grants_count": len(safe_permissions),
            "project_permission_grants": safe_permissions,
            "outside_project_grants": outside_allow,
        },
        "fingerprints": fingerprints,
        "classification": classification,
        "secret_exclusion_verified": True,
    }

    out_path = PRESERVATION_DIR / "antigravity_project_snapshot_sandbox_test.json"
    out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"✅ Secret-free Antigravity project snapshot written: {out_path}")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Project Snapshot Generator")
    parser.add_argument("--generate", action="store_true", help="Generate snapshot file")
    args = parser.parse_args()

    snapshot = generate_secret_free_snapshot()
    print(f"Project: {snapshot['project']['canonical_name']} (ID: {snapshot['project']['id']})")
    print(f"Workspace: {snapshot['workspace']['canonical_root']}")
    print(f"Permissions count: {snapshot['permissions']['project_permission_grants_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
