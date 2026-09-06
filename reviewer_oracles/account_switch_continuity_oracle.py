#!/usr/bin/env python3
"""Secret-free, local continuity evidence for an Antigravity account switch.

This utility deliberately snapshots only deterministic workspace metadata.  It
does not inspect browser profiles, keychains, cookies, credentials, or session
stores.  A human performs authentication; this program compares the local
project state before and after that human-controlled action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_SAFE_PATHS = (
    "config/local_tools.json",
    "events/chief-autopilot/status.json",
    "events/chief-autopilot/lease.json",
)
FORBIDDEN_KEY_PARTS = ("password", "token", "cookie", "credential", "secret", "authorization")
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
)


def _run_git(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(workspace: Path, relative_path: str) -> Path:
    candidate = (workspace / relative_path).resolve()
    if workspace not in candidate.parents and candidate != workspace:
        raise ValueError(f"Path escapes workspace: {relative_path}")
    return candidate


def workspace_integrity(workspace: Path) -> dict[str, Any]:
    status_lines = _run_git(workspace, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    counts = {"staged": 0, "modified": 0, "deleted": 0, "untracked": 0}
    for line in status_lines:
        xy = line[:2]
        if xy == "??":
            counts["untracked"] += 1
            continue
        if "D" in xy:
            counts["deleted"] += 1
        if xy[0] != " ":
            counts["staged"] += 1
        if xy[1] != " ":
            counts["modified"] += 1
    status_digest = hashlib.sha256("\n".join(status_lines).encode("utf-8")).hexdigest()
    return {
        "branch": _run_git(workspace, "branch", "--show-current").strip(),
        "head": _run_git(workspace, "rev-parse", "HEAD").strip(),
        "dirty_counts": counts,
        "status_digest": status_digest,
    }


def fingerprint_paths(workspace: Path, paths: tuple[str, ...]) -> dict[str, Any]:
    fingerprints: dict[str, Any] = {}
    for relative_path in paths:
        path = _safe_path(workspace, relative_path)
        fingerprints[relative_path] = (
            {"present": True, "sha256": sha256_file(path), "size": path.stat().st_size}
            if path.is_file()
            else {"present": False}
        )
    return fingerprints


def _walk_values(value: Any, key_path: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                problems.append(f"forbidden key: {child_path}")
            problems.extend(_walk_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            problems.extend(_walk_values(child, f"{key_path}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
            problems.append(f"sensitive-looking value at: {key_path}")
    return problems


def secret_exclusion_check(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"passed": not (problems := _walk_values(snapshot)), "problems": problems}


def capture_snapshot(workspace: Path, project_name: str, policy_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "declared_project": {"name": project_name, "classification": "UNKNOWN"},
        "canonical_workspace": str(workspace),
        "workspace_integrity": workspace_integrity(workspace),
        "safe_configuration_fingerprints": fingerprint_paths(workspace, DEFAULT_SAFE_PATHS),
        "project_policy": policy_manifest if policy_manifest is not None else {"classification": "UNKNOWN"},
        "continuation_checkpoint": fingerprint_paths(workspace, DEFAULT_SAFE_PATHS[1:]),
        "persistence_expectations": {
            "workspace": "LOCAL_MACHINE_PERSISTENT",
            "git_state": "PROJECT_LOCAL_PERSISTENT",
            "authentication": "ACCOUNT_BOUND",
            "browser_session": "SESSION_BOUND",
            "project_permission_state": "UNKNOWN",
        },
    }
    snapshot["sensitive_data_exclusion"] = secret_exclusion_check(snapshot)
    return snapshot


def _compare_value(label: str, before: Any, after: Any, mismatches: list[str]) -> None:
    if before != after:
        mismatches.append(label)


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    _compare_value("project name", before["declared_project"]["name"], after["declared_project"]["name"], mismatches)
    _compare_value("canonical workspace", before["canonical_workspace"], after["canonical_workspace"], mismatches)
    _compare_value("branch", before["workspace_integrity"]["branch"], after["workspace_integrity"]["branch"], mismatches)
    _compare_value("HEAD", before["workspace_integrity"]["head"], after["workspace_integrity"]["head"], mismatches)
    _compare_value("worktree status", before["workspace_integrity"]["status_digest"], after["workspace_integrity"]["status_digest"], mismatches)
    _compare_value("safe configuration fingerprints", before["safe_configuration_fingerprints"], after["safe_configuration_fingerprints"], mismatches)
    _compare_value("continuation checkpoint", before["continuation_checkpoint"], after["continuation_checkpoint"], mismatches)
    _compare_value("project policy", before["project_policy"], after["project_policy"], mismatches)
    for label, snapshot in (("pre-switch", before), ("post-switch", after)):
        if not secret_exclusion_check(snapshot)["passed"]:
            mismatches.append(f"{label} snapshot secret exclusion")
    return {"result": "PASS" if not mismatches else "REMEDIATE", "mismatches": mismatches}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--workspace", required=True, type=Path)
    capture.add_argument("--project-name", default="sandbox test")
    capture.add_argument("--output", required=True, type=Path)
    capture.add_argument("--policy-manifest", type=Path)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--pre", required=True, type=Path)
    compare.add_argument("--post", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "capture":
        policy = _load_json(args.policy_manifest) if args.policy_manifest else None
        snapshot = capture_snapshot(args.workspace, args.project_name, policy)
        if not snapshot["sensitive_data_exclusion"]["passed"]:
            print(json.dumps({"result": "REMEDIATE", "reason": "snapshot secret exclusion failed"}))
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"result": "CAPTURED", "output": str(args.output)}))
        return 0
    result = compare_snapshots(_load_json(args.pre), _load_json(args.post))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
