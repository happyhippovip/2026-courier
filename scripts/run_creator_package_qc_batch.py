#!/usr/bin/env python3
"""Mission PRODUCT-7 Real Work — Creator Package Batch QC Evaluator.

Evaluates all real catalogued content packages from runtime/content/catalog_manifest.json
against canonical Creator Factory quality control and compliance rules.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent


def load_json_safe(path: Optional[Path], default: Any = None) -> Any:
    if not path or not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


@dataclass
class PackageQCEvaluation:
    package_id: str
    content_id: str
    is_eligible: bool
    verdict: str  # PASS, FAIL, BLOCKED, UNKNOWN
    qc_report_status: str
    master_file_status: str
    hash_linkage_status: str  # VALID, MISMATCH, MISSING_QC_HASH, NOT_AVAILABLE
    duration_seconds: Any
    resolution: Any
    codec_name: str
    blocker_reason: Optional[str] = None
    media_path: Optional[str] = None
    media_sha256: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_batch_qc(repo_dir: Path = COURIER_DIR) -> dict[str, Any]:
    catalog_path = repo_dir / "runtime/content/catalog_manifest.json"
    if not catalog_path.is_file():
        raise FileNotFoundError("catalog_manifest.json not found; build it first")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    packages = catalog.get("packages", [])

    evaluations: list[PackageQCEvaluation] = []

    for pkg in packages:
        pkg_id = pkg["package_id"]
        content_id = pkg.get("content_id", pkg_id)
        pkg_dir = repo_dir / pkg["relative_directory"]

        # Check if this is a real video short package vs batch container
        is_batch_meta = any(fname.startswith("mission_") and fname.endswith("_batch_manifest.json") for fname in pkg.get("metadata_files_present", []))
        is_audit_folder = "audit" in pkg_id or "fix_test" in pkg_id or "camera_fix_verify" in pkg_id

        media_files = pkg.get("media_files", [])
        has_media = len(media_files) > 0

        # Eligibility determination
        if is_batch_meta or is_audit_folder or not has_media:
            evaluations.append(PackageQCEvaluation(
                package_id=pkg_id,
                content_id=content_id,
                is_eligible=False,
                verdict="UNKNOWN",
                qc_report_status="NOT_APPLICABLE",
                master_file_status="NOT_APPLICABLE" if not has_media else "CONTAINER_MEDIA",
                hash_linkage_status="NOT_AVAILABLE",
                duration_seconds="NOT_AVAILABLE",
                resolution="NOT_AVAILABLE",
                codec_name="NOT_AVAILABLE",
                blocker_reason="Not a standalone video package (batch metadata container or audit folder)",
            ))
            continue

        # For eligible packages, find primary video master
        master_media = next((m for m in media_files if m["filename"].endswith((".mp4", ".avi"))), None)
        if not master_media:
            evaluations.append(PackageQCEvaluation(
                package_id=pkg_id,
                content_id=content_id,
                is_eligible=True,
                verdict="BLOCKED",
                qc_report_status="NO_MASTER_VIDEO",
                master_file_status="MISSING",
                hash_linkage_status="NOT_AVAILABLE",
                duration_seconds="NOT_AVAILABLE",
                resolution="NOT_AVAILABLE",
                codec_name="NOT_AVAILABLE",
                blocker_reason="Missing master video file (.mp4 or .avi)",
            ))
            continue

        m_sha = master_media.get("sha256", "")
        m_rel = master_media.get("relative_path", "")

        # Check QC report
        qc_file = pkg_dir / "qc_report.json"
        qc_data = load_json_safe(qc_file)

        if not qc_data:
            evaluations.append(PackageQCEvaluation(
                package_id=pkg_id,
                content_id=content_id,
                is_eligible=True,
                verdict="BLOCKED",
                qc_report_status="MISSING",
                master_file_status="EXISTS",
                hash_linkage_status="NOT_AVAILABLE",
                duration_seconds=pkg.get("duration_seconds", "NOT_AVAILABLE"),
                resolution=pkg.get("resolution", "NOT_AVAILABLE"),
                codec_name=pkg.get("video_codec", "NOT_AVAILABLE"),
                blocker_reason="qc_report.json is missing for package",
                media_path=m_rel,
                media_sha256=m_sha,
            ))
            continue

        qc_raw_st = qc_data.get("verdict", qc_data.get("status", "NONE"))
        qc_src_hash = (qc_data.get("source_hash") or qc_data.get("media_sha256") or "").strip().lower()

        # Check hash linkage
        if not qc_src_hash:
            hash_status = "MISSING_QC_HASH"
        elif qc_src_hash != m_sha.lower():
            hash_status = "MISMATCH"
        else:
            hash_status = "VALID"

        # Check overall verdict
        if hash_status == "VALID" and qc_raw_st == "PASS":
            verdict = "PASS"
            blocker = None
        elif hash_status == "MISMATCH":
            verdict = "FAIL"
            blocker = f"QC report source_hash ({qc_src_hash[:16]}...) does not match media sha256 ({m_sha[:16]}...)"
        elif qc_raw_st != "PASS":
            verdict = "FAIL"
            blocker = f"QC report recorded non-passing verdict: {qc_raw_st}"
        else:
            verdict = "BLOCKED"
            blocker = f"Hash linkage status: {hash_status}"

        evaluations.append(PackageQCEvaluation(
            package_id=pkg_id,
            content_id=content_id,
            is_eligible=True,
            verdict=verdict,
            qc_report_status=qc_raw_st,
            master_file_status="EXISTS",
            hash_linkage_status=hash_status,
            duration_seconds=pkg.get("duration_seconds", "NOT_AVAILABLE"),
            resolution=pkg.get("resolution", "NOT_AVAILABLE"),
            codec_name=pkg.get("video_codec", "NOT_AVAILABLE"),
            blocker_reason=blocker,
            media_path=m_rel,
            media_sha256=m_sha,
        ))

    # Summary calculations
    total = len(evaluations)
    eligible = sum(1 for e in evaluations if e.is_eligible)
    pass_cnt = sum(1 for e in evaluations if e.verdict == "PASS")
    fail_cnt = sum(1 for e in evaluations if e.verdict == "FAIL")
    blocked_cnt = sum(1 for e in evaluations if e.verdict == "BLOCKED")
    unknown_cnt = sum(1 for e in evaluations if e.verdict == "UNKNOWN")

    report = {
        "schema_version": "CREATOR_QC_BATCH_REPORT_V1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_catalog_packages": total,
        "qc_eligible_count": eligible,
        "qc_pass_count": pass_cnt,
        "qc_fail_count": fail_cnt,
        "qc_blocked_count": blocked_cnt,
        "qc_unknown_count": unknown_cnt,
        "deterministic_qc": "PASS",
        "model_calls_for_qc": 0,
        "pass_package_ids": [e.package_id for e in evaluations if e.verdict == "PASS"],
        "fail_package_ids": [e.package_id for e in evaluations if e.verdict == "FAIL"],
        "blocked_package_ids": [e.package_id for e in evaluations if e.verdict == "BLOCKED"],
        "unknown_package_ids": [e.package_id for e in evaluations if e.verdict == "UNKNOWN"],
        "evaluations": [e.to_dict() for e in evaluations],
    }
    return report


if __name__ == "__main__":
    rep = evaluate_batch_qc()
    out_file = COURIER_DIR / "runtime/content/qc_batch_report.json"
    save_json_atomic(out_file, rep)
    print("==================================================")
    print(f"CREATOR BATCH QC COMPLETED: {rep['total_catalog_packages']} packages")
    print(f"  Eligible: {rep['qc_eligible_count']}")
    print(f"  PASS:     {rep['qc_pass_count']}")
    print(f"  FAIL:     {rep['qc_fail_count']}")
    print(f"  BLOCKED:  {rep['qc_blocked_count']}")
    print(f"  UNKNOWN:  {rep['qc_unknown_count']}")
    print(f"Output written to: {out_file}")
    print("==================================================")
