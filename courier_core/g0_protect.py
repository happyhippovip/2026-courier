"""Gate G0: protect data before anything is removed.

A backup manifest records path, size and SHA-256. Checking it returns PASS
only when every entry still matches. A hash or size deviation is FAIL. A
missing file is FAIL. Anything that cannot be decided is UNKNOWN, and
UNKNOWN is not PASS.

Deletion planning is a dry-run. Approval applies to one exact candidate
path and never removes the file.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

SCHEMA = "courier.g0.backup_manifest/v1"
GATE_STATUSES = ("NOT TESTED", "TEST PASSED")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def gate_status(tested: bool = False) -> str:
    """Report NOT TESTED or TEST PASSED. Any other input stays NOT TESTED."""
    if tested is True:
        return "TEST PASSED"
    return "NOT TESTED"


def _safe_rel(path: str) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    if path.startswith(("/", "\\")) or "\\" in path:
        return None
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        return None
    return path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(root: str | Path, paths: Iterable[str]) -> dict:
    """Record path, size and SHA-256 for each readable file under root."""
    root = Path(root)
    entries = []
    for rel in paths:
        safe = _safe_rel(rel)
        file = (root / safe) if safe else None
        if file is None or not file.is_file():
            entries.append({"path": rel, "size": None, "sha256": None})
            continue
        data = file.read_bytes()
        entries.append({"path": safe, "size": len(data), "sha256": _sha256(data)})
    return {"schema": SCHEMA, "entries": entries}


def check_manifest(root: str | Path, manifest: dict) -> dict:
    """PASS only when every entry matches. UNKNOWN is never turned into PASS."""
    root = Path(root)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("entries"), list):
        return {"result": "UNKNOWN", "entries": []}
    entries = manifest["entries"]
    if not entries:
        return {"result": "UNKNOWN", "entries": []}

    findings = []
    saw_fail = False
    saw_unknown = False
    for item in entries:
        if not isinstance(item, dict):
            findings.append({"path": None, "result": "UNKNOWN"})
            saw_unknown = True
            continue
        rel = item.get("path")
        safe = _safe_rel(rel) if isinstance(rel, str) else None
        if safe is None:
            findings.append({"path": rel, "result": "UNKNOWN"})
            saw_unknown = True
            continue
        file = root / safe
        if not file.exists():
            findings.append({"path": safe, "result": "FAIL"})
            saw_fail = True
            continue
        if not file.is_file():
            findings.append({"path": safe, "result": "UNKNOWN"})
            saw_unknown = True
            continue
        digest = item.get("sha256")
        size = item.get("size")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest) or not isinstance(size, int) or isinstance(size, bool):
            findings.append({"path": safe, "result": "UNKNOWN"})
            saw_unknown = True
            continue
        data = file.read_bytes()
        if len(data) != size or _sha256(data) != digest:
            findings.append({"path": safe, "result": "FAIL"})
            saw_fail = True
            continue
        findings.append({"path": safe, "result": "PASS"})

    if saw_fail:
        result = "FAIL"
    elif saw_unknown:
        result = "UNKNOWN"
    else:
        result = "PASS"
    return {"result": result, "entries": findings}


def deletion_plan(root: str | Path, candidates: Iterable[str], approvals: Iterable[str]) -> dict:
    """List candidates. Approval is exact and per path. Nothing is deleted."""
    tree = Path(root).resolve()
    approved = {item for item in approvals if isinstance(item, str)}
    listed = []
    for rel in candidates:
        safe = _safe_rel(rel)
        inside = False
        if safe is not None:
            try:
                (tree / safe).resolve().relative_to(tree)
                inside = True
            except ValueError:
                inside = False
        listed.append({
            "path": rel,
            "action": "DRY_RUN",
            "approved": inside and rel in approved,
        })
    return {"mode": "DRY_RUN", "candidates": listed, "deleted": []}
