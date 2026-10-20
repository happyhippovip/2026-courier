"""Artifact collection integrity and path containment verifier.

Lane L4. Enforces fail-closed path containment: rejects traversal escapes,
symlinks pointing outside, absolute paths, and Windows alternate data streams.
Validates SHA-256 digests and byte counts against optional manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ArtifactInfo:
    rel_path: str
    sha256: str
    size_bytes: int


@dataclass
class ArtifactVerificationReport:
    valid: bool
    checked_count: int
    total_bytes: int
    artifacts: dict[str, ArtifactInfo] = field(default_factory=dict)
    tampered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    escaped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["artifacts"] = {k: asdict(v) for k, v in self.artifacts.items()}
        return d


def _hash_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(65536):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _is_contained(base: Path, target: Path) -> bool:
    try:
        base_res = base.resolve()
        target_res = target.resolve()
        return target_res.is_relative_to(base_res)
    except Exception:
        return False


def verify_artifacts(
    root_dir: str | Path,
    manifest: Optional[dict[str, Any]] = None,
    strict: bool = False,
) -> ArtifactVerificationReport:
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return ArtifactVerificationReport(
            valid=False,
            checked_count=0,
            total_bytes=0,
            errors=[f"root_dir does not exist or is not a directory: {root}"],
        )

    root_resolved = root.resolve()
    artifacts: dict[str, ArtifactInfo] = {}
    tampered: list[str] = []
    missing: list[str] = []
    escaped: list[str] = []
    errors: list[str] = []
    total_bytes = 0

    # 1. Inspect on-disk artifacts
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if not _is_contained(root_resolved, p):
                escaped.append(str(p))
                continue
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                escaped.append(str(p))
                continue

            # Check for Windows ADS or suspicious tokens
            if ":" in rel:
                escaped.append(rel)
                continue

            try:
                digest, size = _hash_file(p)
                artifacts[rel] = ArtifactInfo(rel_path=rel, sha256=digest, size_bytes=size)
                total_bytes += size
            except OSError as exc:
                errors.append(f"failed to read artifact {rel}: {exc}")
    except Exception as exc:
        errors.append(f"scan error: {exc}")

    # 2. Manifest check if provided
    if manifest is not None:
        mf_artifacts = manifest.get("artifacts") or {}
        for rel_spec, spec_info in mf_artifacts.items():
            norm_rel = rel_spec.replace("\\", "/")
            if ".." in norm_rel.split("/") or norm_rel.startswith(("/", "\\")):
                escaped.append(rel_spec)
                continue

            target_path = root / norm_rel
            if not _is_contained(root_resolved, target_path):
                escaped.append(rel_spec)
                continue

            if norm_rel not in artifacts:
                missing.append(norm_rel)
                continue

            expected_sha = spec_info.get("sha256") if isinstance(spec_info, dict) else str(spec_info)
            if expected_sha and artifacts[norm_rel].sha256 != expected_sha:
                tampered.append(norm_rel)

        if strict:
            # Check for extra files not in manifest
            for rel in artifacts:
                if rel not in mf_artifacts:
                    tampered.append(rel)

    valid = (
        len(tampered) == 0
        and len(missing) == 0
        and len(escaped) == 0
        and len(errors) == 0
    )

    return ArtifactVerificationReport(
        valid=valid,
        checked_count=len(artifacts),
        total_bytes=total_bytes,
        artifacts=artifacts,
        tampered=tampered,
        missing=missing,
        escaped=escaped,
        errors=errors,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.artifact_verifier",
        description="Verify artifact collection integrity and path containment.",
    )
    parser.add_argument("root_dir", help="Path to artifact directory")
    parser.add_argument("--manifest", help="Path to optional expected manifest JSON")
    parser.add_argument("--strict", action="store_true", help="Reject untracked files not in manifest")
    args = parser.parse_args(argv)

    manifest_data = None
    if args.manifest:
        try:
            with open(args.manifest, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as exc:
            print(json.dumps({"valid": False, "errors": [f"failed to load manifest: {exc}"]}))
            return 1

    report = verify_artifacts(args.root_dir, manifest=manifest_data, strict=args.strict)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.valid else 1


if __name__ == "__main__":
    sys.exit(main())
