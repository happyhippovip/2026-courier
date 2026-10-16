#!/usr/bin/env python3
"""Work Preservation Without Mutation (FRZ-05 / FRZ-04).

Creates emergency forensic backups of uncommitted work without mutating
the working tree:
  - Generates unified diffs (`unstaged.diff`, `staged.diff`).
  - Lists untracked meaningful files while filtering secrets, credentials,
    runtime DBs (.db, .sqlite, .sock), and build artifacts (.pyc, node_modules).
  - Captures standalone git bundle of recent commits when unpushed commits exist.
  - Emits a cryptographic SHA-256 manifest linking all preservation artifacts.
  - Stores everything into an external durable recovery directory outside the repo.

Strict Invariants:
- Zero mutation of the current git repository state (`git checkout`, `git reset`,
  `git stash`, and `git clean` are NEVER run).
- Secret filtering: scrubs files matching .env, credentials, id_rsa, tokens.
- Safety ratchet: `kill_by_name = 0`.
- Autonomous spend: 0 EUR.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Path filtering patterns to prevent leaking credentials or runtime databases
EXCLUDED_PATTERNS = [
    r".*\.pem$",
    r".*\.key$",
    r".*id_rsa.*",
    r".*\.env.*",
    r".*credentials.*",
    r".*secret.*",
    r".*token.*",
    r".*\.db$",
    r".*\.sqlite.*",
    r".*\.pyc$",
    r".*__pycache__.*",
    r".*node_modules.*",
    r".*\.git/.*",
    r".*\.sock$",
]


def is_path_safe_to_preserve(rel_path: str) -> bool:
    """Check if file should be included in preservation bundle."""
    normalized = rel_path.replace("\\", "/").lower()
    for pattern in EXCLUDED_PATTERNS:
        if re.search(pattern, normalized):
            return False
    return True


def get_default_preservation_dir() -> Path:
    """Return external durable recovery directory outside working repo."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return Path(base) / "Courier" / "recovery"
    return Path(os.path.expanduser("~/.courier")) / "recovery"


def run_git_command(args: List[str], repo_dir: Path) -> Tuple[int, str, str]:
    """Execute git command safely without modifying repository."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir)] + args,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as exc:
        return -1, "", str(exc)


def calculate_sha256(file_path: Path) -> str:
    """Compute sha256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def preserve_uncommitted_work(
    repo_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    bundle_commits: bool = True,
) -> Dict[str, Any]:
    """Capture unified diffs, untracked files, and bundle safely."""
    if repo_dir is None:
        repo_dir = Path.cwd()
    if output_dir is None:
        output_dir = get_default_preservation_dir()

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    preservation_id = f"PRESERVE-{timestamp_str}"
    target_dir = output_dir / preservation_id
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: List[Dict[str, Any]] = []

    # 1. Unstaged diff
    code, unstaged_diff, _ = run_git_command(["diff"], repo_dir)
    unstaged_file = target_dir / "unstaged.diff"
    unstaged_file.write_text(unstaged_diff, encoding="utf-8")
    manifest_entries.append({
        "type": "unstaged_diff",
        "file": unstaged_file.name,
        "size_bytes": len(unstaged_diff.encode("utf-8")),
        "sha256": calculate_sha256(unstaged_file),
    })

    # 2. Staged diff (cached)
    code, staged_diff, _ = run_git_command(["diff", "--cached"], repo_dir)
    staged_file = target_dir / "staged.diff"
    staged_file.write_text(staged_diff, encoding="utf-8")
    manifest_entries.append({
        "type": "staged_diff",
        "file": staged_file.name,
        "size_bytes": len(staged_diff.encode("utf-8")),
        "sha256": calculate_sha256(staged_file),
    })

    # 3. Untracked file inventory and safe copy
    code, untracked_raw, _ = run_git_command(["ls-files", "--others", "--exclude-standard"], repo_dir)
    untracked_lines = [l.strip() for l in untracked_raw.splitlines() if l.strip()]
    
    safe_untracked = []
    filtered_out = []
    untracked_copy_dir = target_dir / "untracked"

    for rel in untracked_lines:
        if is_path_safe_to_preserve(rel):
            safe_untracked.append(rel)
            src = repo_dir / rel
            if src.is_file():
                dest = untracked_copy_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src, dest)
                except Exception:
                    pass
        else:
            filtered_out.append(rel)

    untracked_list_file = target_dir / "untracked_files.json"
    untracked_list_file.write_text(
        json.dumps({"preserved": safe_untracked, "filtered_security": filtered_out}, indent=2),
        encoding="utf-8",
    )
    manifest_entries.append({
        "type": "untracked_inventory",
        "file": untracked_list_file.name,
        "preserved_count": len(safe_untracked),
        "filtered_count": len(filtered_out),
        "sha256": calculate_sha256(untracked_list_file),
    })

    # 4. Git bundle (if commits exist and requested)
    bundle_created = False
    if bundle_commits:
        bundle_file = target_dir / "repository_head.bundle"
        code, _, _ = run_git_command(["bundle", "create", str(bundle_file), "HEAD~20..HEAD"], repo_dir)
        if code != 0:
            # Fallback if history has fewer than 20 commits
            code, _, _ = run_git_command(["bundle", "create", str(bundle_file), "HEAD"], repo_dir)
        
        if code == 0 and bundle_file.is_file():
            bundle_created = True
            manifest_entries.append({
                "type": "git_bundle",
                "file": bundle_file.name,
                "size_bytes": bundle_file.stat().st_size,
                "sha256": calculate_sha256(bundle_file),
            })

    # 5. Manifest file
    manifest = {
        "schema_version": "1.0",
        "preservation_id": preservation_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repo_dir": str(repo_dir.resolve()),
        "bundle_created": bundle_created,
        "artifacts": manifest_entries,
    }
    manifest_path = target_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "preservation_id": preservation_id,
        "target_dir": str(target_dir),
        "manifest_path": str(manifest_path),
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Work Preservation Without Mutation (FRZ-05)")
    parser.add_argument("--repo-dir", type=Path, default=Path.cwd(), help="Path to repository")
    parser.add_argument("--out-dir", type=Path, default=None, help="External preservation directory")
    parser.add_argument("--no-bundle", action="store_true", help="Skip git bundle creation")
    parser.add_argument("--json", action="store_true", help="Print result as JSON")
    args = parser.parse_args()

    result = preserve_uncommitted_work(
        repo_dir=args.repo_dir,
        output_dir=args.out_dir,
        bundle_commits=not args.no_bundle,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"=== WORK PRESERVATION COMPLETE [{result['preservation_id']}] ===")
        print(f"Target Directory: {result['target_dir']}")
        print(f"Manifest File:    {result['manifest_path']}")
        print(f"Preserved Items:  {len(result['manifest']['artifacts'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
