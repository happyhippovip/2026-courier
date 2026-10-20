"""Branch diff verifier against declared scope and V3 protected baseline.

Lane L4. Enforces:
- Every changed file in a branch or PR must match at least one allowed scope pattern
- No changed file may touch protected V3 baseline paths
- Supports fnmatch / glob pattern matching with recursive wildcard (**)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class BranchDiffReport:
    valid: bool
    changed_files: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    protected_breaches: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _match_pattern(path_str: str, pattern: str) -> bool:
    norm_path = path_str.replace("\\", "/").lstrip("/")
    norm_pattern = pattern.replace("\\", "/").lstrip("/")

    if norm_pattern.endswith("/**"):
        prefix = norm_pattern[:-3]
        return norm_path == prefix or norm_path.startswith(prefix + "/")

    return fnmatch.fnmatchcase(norm_path, norm_pattern)


def _matches_any(path_str: str, patterns: list[str]) -> bool:
    return any(_match_pattern(path_str, pat) for pat in patterns)


def verify_changed_files_scope(
    changed_files: list[str],
    allowed_scope: list[str],
    protected_patterns: Optional[list[str]] = None,
) -> BranchDiffReport:
    protected = protected_patterns or [
        "courier_v3/**",
        "contracts/v3/**",
        "security/**",
        ".github/workflows/**",
    ]

    out_of_scope: list[str] = []
    protected_breaches: list[str] = []
    violations: list[str] = []

    for path in changed_files:
        norm_path = path.replace("\\", "/").strip()
        if not norm_path:
            continue

        parts = [p for p in norm_path.split("/") if p]
        if ".." in parts:
            protected_breaches.append(path)
            out_of_scope.append(path)
            violations.append(f"path_traversal_blocked: {path} contains '..' traversal segment")
            continue

        # Check protected patterns first
        if _matches_any(norm_path, protected):
            protected_breaches.append(path)
            violations.append(f"protected_breach: {path} touches protected baseline")

        # Check allowed scope
        if not _matches_any(norm_path, allowed_scope):
            out_of_scope.append(path)
            violations.append(f"out_of_scope: {path} is not in declared files_scope")

    valid = len(out_of_scope) == 0 and len(protected_breaches) == 0

    return BranchDiffReport(
        valid=valid,
        changed_files=changed_files,
        out_of_scope=out_of_scope,
        protected_breaches=protected_breaches,
        violations=violations,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.branch_diff_verifier",
        description="Verify changed files against declared scope and protected baseline.",
    )
    parser.add_argument("manifest_path", help="Path to diff manifest JSON ({changed: [], scope: [], protected: []})")
    args = parser.parse_args(argv)

    try:
        with open(args.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        report = BranchDiffReport(
            valid=False,
            violations=[f"failed to read manifest: {exc}"],
        )
        print(json.dumps(report.to_dict(), indent=2))
        return 1

    changed = data.get("changed") or []
    scope = data.get("scope") or []
    protected = data.get("protected")

    report = verify_changed_files_scope(changed, allowed_scope=scope, protected_patterns=protected)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.valid else 1


if __name__ == "__main__":
    sys.exit(main())
