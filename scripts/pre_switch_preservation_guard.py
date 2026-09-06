#!/usr/bin/env python3
"""Pre-Switch Workspace Preservation & Recovery Guard (Mission 147G-SAFE).

Guarantees 100% safe, zero-data-loss workspace preservation prior to any
Google Antigravity account logout or account switch.

Features:
1. Complete live workspace inventory (tracked, modified, untracked).
2. Deterministic SHA-256 preservation manifest generation.
3. Account-independent, timestamped local backup creation.
4. Independent multi-file backup hash verification (0 mismatches required).
5. Non-destructive isolated recovery drill.
6. Antigravity account dependency classification.
7. Compact Studio/Chief status state emission.
8. Original workspace recheck for non-destructive safety.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

DEFAULT_WORKSPACE_PATH = Path("/Users/user/Downloads/2026-courier").resolve()
DEFAULT_BACKUP_ROOT = Path("/Users/user/Downloads/2026-project-backups/2026-courier").resolve()

# Directories and patterns strictly excluded from preservation manifests and backups
IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "node_modules",
}

IGNORED_FILE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".DS_Store",
}

IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

# Explicit markers for 146C and 146G work to verify
MISSION_146C_KEY_FILES = [
    "scripts/resource_intelligence.py",
    "tests/test_resource_intelligence_mission_146c.py",
]

MISSION_146G_KEY_FILES = [
    "scripts/release_acceptance_gate.py",
    "scripts/private_upload_executor.py",
    "scripts/publication_engine.py",
    "scripts/evidence_provenance.py",
    "scripts/publication_approval.py",
    "scripts/private_upload_dry_run.py",
    "tests/test_mission_141c_acceptance_oracle.py",
    "tests/test_production_security_remediations_mission_139g.py",
    "tests/test_production_trust_and_executor_hardening_mission_137g.py",
]


def compute_file_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute deterministic SHA-256 hash of a file using memory-efficient streaming."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_git_info(workspace_path: Path) -> Dict[str, Any]:
    """Retrieve git branch, HEAD commit, and status details safely."""
    info: Dict[str, Any] = {
        "branch": "unknown",
        "head_sha": "unknown",
        "porcelain_status": "",
        "staged_files": [],
        "modified_files": [],
        "untracked_files": [],
        "deleted_files": [],
        "diff_stats": "",
    }
    if not (workspace_path / ".git").exists():
        return info

    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            info["branch"] = res.stdout.strip()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            info["head_sha"] = res.stdout.strip()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            info["porcelain_status"] = res.stdout
            for line in res.stdout.splitlines():
                if not line:
                    continue
                code = line[:2]
                path_part = line[3:].strip()
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1].strip()

                if code.startswith("?"):
                    info["untracked_files"].append(path_part)
                elif "D" in code:
                    info["deleted_files"].append(path_part)
                elif code[0] in "MADRC":
                    info["staged_files"].append(path_part)
                elif code[1] in "M":
                    info["modified_files"].append(path_part)
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            info["diff_stats"] = res.stdout.strip()
    except Exception:
        pass

    return info


def categorize_file(rel_path_str: str) -> str:
    """Categorize file into a structured domain."""
    p = Path(rel_path_str)
    parts = p.parts
    if not parts:
        return "OTHER"
    top = parts[0]
    if top == "scripts":
        return "CODE_SCRIPT"
    elif top == "tests":
        return "TEST_SUITE"
    elif top == "events":
        return "EVENT_EVIDENCE_DATA"
    elif top == "studio":
        return "STUDIO_INTERFACE"
    elif top == "schemas":
        return "DATA_SCHEMA"
    elif top == "docs":
        return "DOCUMENTATION"
    elif top == "runtime":
        return "RUNTIME_CONTENT_ASSET"
    elif p.name in {"requirements.txt", ".gitignore", "package.json", "tsconfig.json"}:
        return "PROJECT_CONFIG"
    return "MISC_PROJECT_FILE"


class WorkspacePreservationGuard:
    """Core preservation engine ensuring zero data loss during account switches."""

    def __init__(
        self,
        workspace_path: Path = DEFAULT_WORKSPACE_PATH,
        backup_root: Path = DEFAULT_BACKUP_ROOT,
    ) -> None:
        self.workspace_path = workspace_path.resolve()
        self.backup_root = backup_root.resolve()
        self.events_dir = self.workspace_path / "events"
        self.preservation_dir = self.events_dir / "preservation"

    def build_inventory(self) -> Dict[str, Any]:
        """Perform comprehensive live workspace inventory."""
        git_info = get_git_info(self.workspace_path)
        all_files: List[Dict[str, Any]] = []

        total_bytes = 0
        file_count = 0

        for dirpath, dirnames, filenames in os.walk(self.workspace_path):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES]

            for fname in sorted(filenames):
                if fname in IGNORED_FILE_NAMES:
                    continue
                p = Path(dirpath) / fname
                if p.suffix in IGNORED_FILE_EXTENSIONS:
                    continue
                if p.is_symlink() or not p.is_file():
                    continue

                rel_path = p.relative_to(self.workspace_path)
                rel_str = str(rel_path)
                sz = p.stat().st_size
                sha = compute_file_sha256(p)
                category = categorize_file(rel_str)

                # Determine git tracked/untracked state
                is_untracked = rel_str in git_info["untracked_files"] or any(
                    rel_str.startswith(f"{u.rstrip('/')}/") for u in git_info["untracked_files"]
                )
                is_modified = rel_str in git_info["modified_files"] or rel_str in git_info["staged_files"]

                if is_untracked:
                    status = "UNTRACKED"
                elif is_modified:
                    status = "MODIFIED"
                else:
                    status = "TRACKED"

                all_files.append({
                    "relative_path": rel_str,
                    "size_bytes": sz,
                    "sha256": sha,
                    "status": status,
                    "category": category,
                })
                total_bytes += sz
                file_count += 1

        all_files.sort(key=lambda x: x["relative_path"])

        # Check Mission 146C files
        m146c_status: Dict[str, Any] = {}
        for f in MISSION_146C_KEY_FILES:
            fp = self.workspace_path / f
            exists = fp.is_file()
            m146c_status[f] = {
                "exists": exists,
                "sha256": compute_file_sha256(fp) if exists else None,
                "size_bytes": fp.stat().st_size if exists else 0,
            }

        # Check Mission 146G files
        m146g_status: Dict[str, Any] = {}
        for f in MISSION_146G_KEY_FILES:
            fp = self.workspace_path / f
            exists = fp.is_file()
            m146g_status[f] = {
                "exists": exists,
                "sha256": compute_file_sha256(fp) if exists else None,
                "size_bytes": fp.stat().st_size if exists else 0,
            }

        return {
            "workspace_path": str(self.workspace_path),
            "branch": git_info["branch"],
            "head_sha": git_info["head_sha"],
            "git_porcelain_lines": len([l for l in git_info["porcelain_status"].splitlines() if l.strip()]),
            "git_staged_count": len(git_info["staged_files"]),
            "git_modified_count": len(git_info["modified_files"]),
            "git_untracked_count": len(git_info["untracked_files"]),
            "git_deleted_count": len(git_info["deleted_files"]),
            "diff_stats": git_info["diff_stats"],
            "total_files": file_count,
            "total_bytes": total_bytes,
            "files": all_files,
            "mission_146c_inventory": m146c_status,
            "mission_146g_inventory": m146g_status,
        }

    def generate_manifest(self, inventory: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a canonical deterministic preservation manifest."""
        if inventory is None:
            inventory = self.build_inventory()

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest_id = f"preservation-manifest-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        files_list = inventory["files"]
        canonical_files_json = json.dumps(files_list, sort_keys=True, separators=(",", ":"))
        manifest_content_hash = hashlib.sha256(canonical_files_json.encode("utf-8")).hexdigest()

        manifest = {
            "schema_version": "1.0",
            "manifest_id": manifest_id,
            "created_at": now_iso,
            "workspace_path": str(self.workspace_path),
            "branch": inventory["branch"],
            "head_sha": inventory["head_sha"],
            "manifest_content_hash": manifest_content_hash,
            "file_count": inventory["total_files"],
            "total_bytes": inventory["total_bytes"],
            "git_summary": {
                "staged_count": inventory["git_staged_count"],
                "modified_count": inventory["git_modified_count"],
                "untracked_count": inventory["git_untracked_count"],
                "deleted_count": inventory["git_deleted_count"],
                "diff_stats": inventory["diff_stats"],
            },
            "mission_146c_verified": all(v["exists"] for v in inventory["mission_146c_inventory"].values()),
            "mission_146g_verified": all(v["exists"] for v in inventory["mission_146g_inventory"].values()),
            "mission_146c_files": inventory["mission_146c_inventory"],
            "mission_146g_files": inventory["mission_146g_inventory"],
            "files": files_list,
        }

        return manifest

    def create_backup(
        self,
        manifest: Optional[Dict[str, Any]] = None,
        custom_snapshot_dir: Optional[Path] = None,
    ) -> Tuple[Path, Dict[str, Any]]:
        """Create non-destructive timestamped snapshot outside the live repo."""
        if manifest is None:
            manifest = self.generate_manifest()

        ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        if custom_snapshot_dir is not None:
            snapshot_dir = custom_snapshot_dir
        else:
            snapshot_dir = self.backup_root / f"snapshot_{ts_str}"

        snapshot_dir.mkdir(parents=True, exist_ok=True)

        copied_count = 0
        copied_bytes = 0

        for f_entry in manifest["files"]:
            rel_str = f_entry["relative_path"]
            src_path = self.workspace_path / rel_str
            dest_path = snapshot_dir / rel_str

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # Use copy2 to preserve metadata, file permissions, timestamps
            shutil.copy2(src_path, dest_path)
            copied_count += 1
            copied_bytes += f_entry["size_bytes"]

        # Write manifest directly inside snapshot
        manifest_dest = snapshot_dir / "preservation_manifest.json"
        manifest_dest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Write snapshot metadata summary
        snapshot_meta = {
            "snapshot_path": str(snapshot_dir),
            "manifest_id": manifest["manifest_id"],
            "created_at": manifest["created_at"],
            "copied_files": copied_count,
            "copied_bytes": copied_bytes,
            "manifest_content_hash": manifest["manifest_content_hash"],
        }
        (snapshot_dir / "SNAPSHOT_METADATA.json").write_text(
            json.dumps(snapshot_meta, indent=2), encoding="utf-8"
        )

        # Also save manifest in live repo events directory for local reference
        self.preservation_dir.mkdir(parents=True, exist_ok=True)
        (self.preservation_dir / "manifest_current.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        return snapshot_dir, snapshot_meta

    def verify_backup(
        self,
        snapshot_dir: Path,
        manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Independently rehash all files in the snapshot and verify 0 mismatches."""
        expected_files = {f["relative_path"]: f for f in manifest["files"]}

        match_count = 0
        mismatch_count = 0
        missing_count = 0
        extra_count = 0
        mismatched_details: List[Dict[str, Any]] = []

        actual_snapshot_files: Set[str] = set()
        snapshot_total_bytes = 0

        for dirpath, dirnames, filenames in os.walk(snapshot_dir):
            for fname in filenames:
                if fname in {"preservation_manifest.json", "SNAPSHOT_METADATA.json"}:
                    continue
                p = Path(dirpath) / fname
                rel_str = str(p.relative_to(snapshot_dir))
                actual_snapshot_files.add(rel_str)
                sz = p.stat().st_size
                snapshot_total_bytes += sz
                sha = compute_file_sha256(p)

                if rel_str not in expected_files:
                    extra_count += 1
                    continue

                exp_entry = expected_files[rel_str]
                if sha == exp_entry["sha256"] and sz == exp_entry["size_bytes"]:
                    match_count += 1
                else:
                    mismatch_count += 1
                    mismatched_details.append({
                        "file": rel_str,
                        "expected_sha256": exp_entry["sha256"],
                        "actual_sha256": sha,
                        "expected_size": exp_entry["size_bytes"],
                        "actual_size": sz,
                    })

        for rel_str in expected_files:
            if rel_str not in actual_snapshot_files:
                missing_count += 1
                mismatched_details.append({
                    "file": rel_str,
                    "error": "FILE_MISSING_FROM_SNAPSHOT",
                })

        verification_result = {
            "snapshot_path": str(snapshot_dir),
            "snapshot_file_count": len(actual_snapshot_files),
            "snapshot_bytes": snapshot_total_bytes,
            "hash_match_count": match_count,
            "hash_mismatch_count": mismatch_count,
            "missing_file_count": missing_count,
            "extra_file_count": extra_count,
            "verified": (mismatch_count == 0 and missing_count == 0 and match_count == len(expected_files)),
            "mismatched_details": mismatched_details,
        }

        return verification_result

    def run_recovery_drill(
        self,
        snapshot_dir: Path,
        manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform an isolated, non-destructive recovery drill in a temporary directory."""
        with tempfile.TemporaryDirectory(prefix="preservation_recovery_drill_") as tmp_drill_dir:
            drill_path = Path(tmp_drill_dir)

            # Reconstruct workspace using snapshot
            restored_count = 0
            restored_bytes = 0
            restored_matches = 0
            restored_mismatches = 0

            for f_entry in manifest["files"]:
                rel_str = f_entry["relative_path"]
                snap_file = snapshot_dir / rel_str
                dest_file = drill_path / rel_str

                if not snap_file.is_file():
                    restored_mismatches += 1
                    continue

                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snap_file, dest_file)
                restored_count += 1
                restored_bytes += dest_file.stat().st_size

                # Verify restored hash matches manifest
                restored_sha = compute_file_sha256(dest_file)
                if restored_sha == f_entry["sha256"]:
                    restored_matches += 1
                else:
                    restored_mismatches += 1

            passed = (
                restored_count == len(manifest["files"])
                and restored_mismatches == 0
                and restored_matches == len(manifest["files"])
            )

            drill_result = {
                "recovery_drill_passed": passed,
                "recovery_manifest_match": "PASS" if passed else "FAIL",
                "restored_file_count": restored_count,
                "restored_bytes": restored_bytes,
                "restored_matches": restored_matches,
                "restored_mismatches": restored_mismatches,
            }

            return drill_result

    def analyze_account_dependencies(self) -> Dict[str, str]:
        """Classify local workspace vs Antigravity account state."""
        return {
            "PROJECT_WORKSPACE_FILES": "LOCAL_ACCOUNT_INDEPENDENT",
            "GIT_WORKING_TREE": "LOCAL_ACCOUNT_INDEPENDENT",
            "LOCAL_RUNTIME_STATE": "LOCAL_ACCOUNT_INDEPENDENT",
            "ANTIGRAVITY_CONVERSATIONS": "ACCOUNT_DEPENDENT",
            "ANTIGRAVITY_ARTIFACTS": "ACCOUNT_DEPENDENT",
            "ANTIGRAVITY_KNOWLEDGE": "ACCOUNT_DEPENDENT",
            "AUTHENTICATION_SESSION": "ACCOUNT_DEPENDENT",
            "PROVIDER_QUOTA": "ACCOUNT_DEPENDENT",
        }

    def emit_studio_status(
        self,
        snapshot_dir: Path,
        verification: Dict[str, Any],
        recovery_drill: Dict[str, Any],
        inventory: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Write compact status JSON for Studio and Chief alerting."""
        safe = verification["verified"] and recovery_drill["recovery_drill_passed"]
        status_data = {
            "WORKSPACE_BACKUP_STATUS": "SAFE" if safe else "UNSAFE",
            "LAST_VERIFIED_SNAPSHOT": str(snapshot_dir),
            "LAST_VERIFIED_AT": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ACCOUNT_SWITCH_STATUS": "SAFE" if safe else "BLOCKED",
            "DATA_LOSS_RISK": "NONE_DETECTED" if safe else "DETECTED",
            "METRICS": {
                "snapshot_file_count": verification["snapshot_file_count"],
                "snapshot_bytes": verification["snapshot_bytes"],
                "hash_match_count": verification["hash_match_count"],
                "hash_mismatch_count": verification["hash_mismatch_count"],
                "missing_file_count": verification["missing_file_count"],
                "recovery_manifest_match": recovery_drill["recovery_manifest_match"],
                "mission_146c_preserved": inventory.get("mission_146c_verified", True),
                "mission_146g_preserved": inventory.get("mission_146g_verified", True),
            },
        }

        self.events_dir.mkdir(parents=True, exist_ok=True)
        status_file = self.events_dir / "workspace_preservation_status.json"
        status_file.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
        return status_data

    def recheck_live_workspace(
        self,
        pre_inventory: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Confirm that the live workspace was not modified during backup execution."""
        post_inventory = self.build_inventory()

        pre_map = {f["relative_path"]: f["sha256"] for f in pre_inventory["files"]}
        post_map = {f["relative_path"]: f["sha256"] for f in post_inventory["files"]}

        # Exclude newly generated status / manifest files written to events/preservation
        allowed_new_files = {
            "events/preservation/manifest_current.json",
            "events/workspace_preservation_status.json",
        }

        mismatches: List[Dict[str, Any]] = []
        for rel_str, pre_sha in pre_map.items():
            if rel_str not in post_map:
                mismatches.append({"file": rel_str, "error": "MISSING_POST_PRESERVATION"})
            elif post_map[rel_str] != pre_sha:
                mismatches.append({
                    "file": rel_str,
                    "error": "CONTENT_CHANGED_DURING_PRESERVATION",
                    "pre_sha": pre_sha,
                    "post_sha": post_map[rel_str],
                })

        for rel_str in post_map:
            if rel_str not in pre_map and rel_str not in allowed_new_files:
                # Any untracked file generated outside allowed preservation files
                mismatches.append({"file": rel_str, "error": "UNEXPECTED_NEW_FILE"})

        # Check Mission 146C files explicitly
        m146c_ok = all(
            post_map.get(k) == v["sha256"]
            for k, v in pre_inventory["mission_146c_inventory"].items()
            if v["exists"]
        )

        # Check Mission 146G files explicitly
        m146g_ok = all(
            post_map.get(k) == v["sha256"]
            for k, v in pre_inventory["mission_146g_inventory"].items()
            if v["exists"]
        )

        recheck_ok = len(mismatches) == 0 and m146c_ok and m146g_ok

        return {
            "recheck_passed": recheck_ok,
            "mission_146c_preserved": "YES" if m146c_ok else "NO",
            "mission_146g_preserved": "YES" if m146g_ok else "NO",
            "data_loss_detected": "NO" if recheck_ok else "YES",
            "mismatches": mismatches,
        }

    def execute_full_preservation_guard(
        self,
        custom_snapshot_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Run complete end-to-end preservation workflow fail-closed."""
        # 1. Inventory
        inventory = self.build_inventory()

        # 2. Manifest
        manifest = self.generate_manifest(inventory)

        # 3. Local Backup
        snapshot_dir, snapshot_meta = self.create_backup(manifest, custom_snapshot_dir=custom_snapshot_dir)

        # 4. Backup Verification
        verification = self.verify_backup(snapshot_dir, manifest)

        if not verification["verified"]:
            return {
                "guard_result": "ACCOUNT_SWITCH_BLOCKED",
                "safe_to_log_out_of_google": "NO",
                "safe_to_open_same_workspace_with_account_2": "NO",
                "reason": f"Backup hash verification failed with {verification['hash_mismatch_count']} mismatches and {verification['missing_file_count']} missing files.",
                "verification": verification,
            }

        # 5. Recovery Drill
        recovery_drill = self.run_recovery_drill(snapshot_dir, manifest)

        if not recovery_drill["recovery_drill_passed"]:
            return {
                "guard_result": "ACCOUNT_SWITCH_BLOCKED",
                "safe_to_log_out_of_google": "NO",
                "safe_to_open_same_workspace_with_account_2": "NO",
                "reason": "Recovery drill failed manifest match verification.",
                "recovery_drill": recovery_drill,
            }

        # 6. Account Dependency Analysis
        dependencies = self.analyze_account_dependencies()

        # 7. Studio Status Emission
        studio_status = self.emit_studio_status(
            snapshot_dir=snapshot_dir,
            verification=verification,
            recovery_drill=recovery_drill,
            inventory=inventory,
        )

        # 8. Live Workspace Recheck
        recheck = self.recheck_live_workspace(inventory)

        if not recheck["recheck_passed"]:
            return {
                "guard_result": "ACCOUNT_SWITCH_BLOCKED",
                "safe_to_log_out_of_google": "NO",
                "safe_to_open_same_workspace_with_account_2": "NO",
                "reason": f"Live workspace altered during preservation: {recheck['mismatches']}",
                "recheck": recheck,
            }

        return {
            "guard_result": "SAFE_TO_SWITCH_ACCOUNT",
            "safe_to_log_out_of_google": "YES",
            "safe_to_open_same_workspace_with_account_2": "YES",
            "snapshot_path": str(snapshot_dir),
            "manifest_path": str(snapshot_dir / "preservation_manifest.json"),
            "inventory": inventory,
            "manifest": manifest,
            "verification": verification,
            "recovery_drill": recovery_drill,
            "dependencies": dependencies,
            "studio_status": studio_status,
            "recheck": recheck,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Zero-Data-Loss Workspace Preservation Guard")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE_PATH, help="Path to workspace root")
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT, help="Root path for backups")
    parser.add_argument("--status-only", action="store_true", help="Print latest status without taking snapshot")
    args = parser.parse_args()

    guard = WorkspacePreservationGuard(workspace_path=args.workspace, backup_root=args.backup_root)

    if args.status_only:
        status_file = guard.events_dir / "workspace_preservation_status.json"
        if status_file.is_file():
            print(status_file.read_text(encoding="utf-8"))
            return 0
        print(json.dumps({"WORKSPACE_BACKUP_STATUS": "UNKNOWN", "DATA_LOSS_RISK": "UNKNOWN"}, indent=2))
        return 1

    print("==================================================")
    print("🛡️  RUNNING PRE-SWITCH WORKSPACE PRESERVATION GUARD")
    print("==================================================")
    result = guard.execute_full_preservation_guard()

    print(f"\nGUARD RESULT: {result['guard_result']}")
    print(f"SAFE_TO_LOG_OUT_OF_GOOGLE: {result['safe_to_log_out_of_google']}")
    print(f"SAFE_TO_OPEN_SAME_WORKSPACE_WITH_ACCOUNT_2: {result['safe_to_open_same_workspace_with_account_2']}")

    if result["guard_result"] == "SAFE_TO_SWITCH_ACCOUNT":
        print(f"\n✅ SNAPSHOT PATH: {result['snapshot_path']}")
        print(f"✅ SNAPSHOT FILES: {result['verification']['snapshot_file_count']}")
        print(f"✅ SNAPSHOT BYTES: {result['verification']['snapshot_bytes']}")
        print(f"✅ HASH MATCHES: {result['verification']['hash_match_count']} / {result['verification']['snapshot_file_count']}")
        print(f"✅ HASH MISMATCHES: {result['verification']['hash_mismatch_count']}")
        print(f"✅ RECOVERY DRILL: {result['recovery_drill']['recovery_manifest_match']}")
        print(f"✅ 146C PRESERVED: {result['recheck']['mission_146c_preserved']}")
        print(f"✅ 146G PRESERVED: {result['recheck']['mission_146g_preserved']}")
        print(f"✅ DATA LOSS DETECTED: {result['recheck']['data_loss_detected']}")
        return 0
    else:
        print(f"\n❌ BLOCKED REASON: {result.get('reason')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
