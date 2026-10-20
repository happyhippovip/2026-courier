"""Index evidence files in one Courier home (P4).

Read-only, fail-closed indexer of all evidence artifacts and files located
within or referenced by a Courier home directory. Produces a deterministic,
cryptographically attestable manifest that can be audited, stored, or verified
against disk to detect tampering, corruption, or missing evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from courier_core.events import canonical_json


@dataclass(frozen=True)
class EvidenceEntry:
    relative_path: str
    sha256: str
    size_bytes: int
    category: str  # "LOG", "JSON_RECORD", "JSONL_STREAM", "MARKDOWN_REPORT", "DATABASE", "BINARY"
    modified_utc: str
    pilot_evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "category": self.category,
            "modified_utc": self.modified_utc,
            "pilot_evidence": self.pilot_evidence,
        }


@dataclass(frozen=True)
class EvidenceIndex:
    status: str  # "OK", "EMPTY", "NOT_FOUND", "CORRUPT"
    home: str
    total_files: int = 0
    total_bytes: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    files: list[dict[str, Any]] = field(default_factory=list)
    index_sha256: str = ""
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "home": self.home,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "categories": self.categories,
            "files": self.files,
            "index_sha256": self.index_sha256,
            "error_detail": self.error_detail,
        }

    def write_index(self, output_path: Path | str | None = None) -> Path:
        """Write the index to a JSON file."""
        target = Path(output_path) if output_path else Path(self.home) / "evidence_index.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return target


def _hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _classify_category(path: Path) -> str:
    """Classify file into standard Courier evidence categories."""
    suffix = path.suffix.lower()
    name = path.name.lower()

    if suffix in (".log", ".txt") or "log" in name:
        return "LOG"
    if suffix == ".jsonl":
        return "JSONL_STREAM"
    if suffix == ".json":
        return "JSON_RECORD"
    if suffix in (".md", ".markdown"):
        return "MARKDOWN_REPORT"
    if suffix in (".db", ".sqlite", ".sqlite3"):
        return "DATABASE"
    return "BINARY"


def _parse_pilot_evidence(path: Path) -> dict[str, Any] | None:
    """Extract pilot evidence record if the file matches the schema."""
    if path.suffix.lower() != ".json":
        return None
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(content, dict):
            return None
        required = {"pilot_id", "evidence_type", "metric", "result", "timestamp_utc"}
        if required.issubset(content.keys()):
            return {
                "pilot_id": str(content["pilot_id"]),
                "evidence_type": str(content["evidence_type"]),
                "metric": str(content["metric"]),
                "result": str(content["result"]),
                "timestamp_utc": str(content["timestamp_utc"]),
            }
    except Exception:
        pass
    return None


def index_evidence(
    home: Path | str,
    evidence_dir: Path | str | None = None,
) -> EvidenceIndex:
    """Index all evidence files in one Courier home.

    Searches:
    1. <home>/evidence directory (if present).
    2. Any evidence or result files at the root of <home> (e.g. *.evidence.json, *.result.md, *.proof.json).
    """
    home_path = Path(home).resolve()
    if not home_path.exists() or not home_path.is_dir():
        return EvidenceIndex(
            status="NOT_FOUND",
            home=str(home_path),
            error_detail=f"Home directory not found: {home_path}",
        )

    target_files: set[Path] = set()

    # Priority 1: Specific or default evidence/ subdirectory
    candidate_ev_dir = Path(evidence_dir).resolve() if evidence_dir else home_path / "evidence"
    if candidate_ev_dir.exists() and candidate_ev_dir.is_dir():
        for root, _, files in os.walk(candidate_ev_dir):
            for f in files:
                target_files.add(Path(root) / f)

    # Priority 2: Direct evidence files in <home> root
    for entry in home_path.iterdir():
        if entry.is_file():
            name = entry.name.lower()
            if (
                "evidence" in name
                or "proof" in name
                or name.endswith(".result.md")
                or name.endswith(".result.json")
            ):
                target_files.add(entry)

    if not target_files:
        return EvidenceIndex(
            status="EMPTY",
            home=str(home_path),
            total_files=0,
            total_bytes=0,
            categories={},
            files=[],
            index_sha256=hashlib.sha256(b"[]").hexdigest(),
        )

    entries: list[EvidenceEntry] = []
    category_counts: dict[str, int] = {}
    total_bytes = 0

    for file_path in sorted(target_files):
        try:
            rel_path = file_path.relative_to(home_path).as_posix()
        except ValueError:
            rel_path = file_path.name

        try:
            stat = file_path.stat()
            size = stat.st_size
            sha256 = _hash_file(file_path)
            category = _classify_category(file_path)
            mod_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            pilot = _parse_pilot_evidence(file_path)

            entry = EvidenceEntry(
                relative_path=rel_path,
                sha256=sha256,
                size_bytes=size,
                category=category,
                modified_utc=mod_utc,
                pilot_evidence=pilot,
            )
            entries.append(entry)

            total_bytes += size
            category_counts[category] = category_counts.get(category, 0) + 1
        except Exception as exc:
            return EvidenceIndex(
                status="CORRUPT",
                home=str(home_path),
                error_detail=f"Failed to read evidence file {file_path}: {exc}",
            )

    # Deterministic sorting by relative path
    entries.sort(key=lambda e: e.relative_path)
    files_dicts = [e.to_dict() for e in entries]

    # Deterministic canonical digest
    canonical_repr = canonical_json(files_dicts)
    index_sha256 = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    return EvidenceIndex(
        status="OK",
        home=str(home_path),
        total_files=len(entries),
        total_bytes=total_bytes,
        categories=category_counts,
        files=files_dicts,
        index_sha256=index_sha256,
    )


def verify_evidence_index(
    index_path: Path | str,
    home: Path | str | None = None,
) -> tuple[bool, str]:
    """Verify that current files match a previously recorded evidence index."""
    idx_p = Path(index_path).resolve()
    if not idx_p.exists():
        return False, f"Evidence index file not found: {idx_p}"

    try:
        data = json.loads(idx_p.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Failed to parse evidence index JSON: {exc}"

    home_dir = Path(home).resolve() if home else idx_p.parent
    if not home_dir.exists():
        return False, f"Home directory not found: {home_dir}"

    recorded_files = data.get("files", [])
    for item in recorded_files:
        rel = item.get("relative_path")
        expected_sha = item.get("sha256")
        expected_size = item.get("size_bytes")

        actual_file = home_dir / rel
        if not actual_file.exists():
            return False, f"Missing evidence file: {rel}"

        if actual_file.stat().st_size != expected_size:
            return False, f"Size mismatch for {rel}: expected {expected_size}, got {actual_file.stat().st_size}"

        actual_sha = _hash_file(actual_file)
        if actual_sha != expected_sha:
            return False, f"Evidence file sha256 mismatch for {rel}: expected {expected_sha}, got {actual_sha}"

    return True, "VERIFIED"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for evidence index."""
    parser = argparse.ArgumentParser(description="Index or verify Courier home evidence files.")
    parser.add_argument("--home", type=str, help="Courier home directory path")
    parser.add_argument("--output", type=str, help="Destination JSON path for the generated index")
    parser.add_argument("--verify", type=str, help="Path to evidence_index.json to verify against disk")

    args = parser.parse_args(argv)

    if args.verify:
        valid, reason = verify_evidence_index(args.verify, home=args.home)
        print(f"VERIFICATION: {'PASS' if valid else 'FAIL'} - {reason}")
        return 0 if valid else 1

    if not args.home:
        parser.error("Must specify --home or --verify")

    idx = index_evidence(args.home)
    result_json = json.dumps(idx.to_dict(), indent=2, sort_keys=True)

    if args.output:
        Path(args.output).write_text(result_json, encoding="utf-8")
        print(f"Evidence index written to: {args.output}")
    else:
        print(result_json)

    return 0 if idx.status in ("OK", "EMPTY") else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
