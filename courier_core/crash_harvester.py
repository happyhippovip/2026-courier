"""Crash Report Harvester and Diagnostic Bundler.

Extracts, redacts, classifies, and bundles runtime crashes and failure traces
into structured diagnostic artifacts for automated analysis and triage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# Sensitive pattern definitions for sanitization
SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]+"), r"\1[REDACTED]"),
    (re.compile(r"sk-[a-zA-Z0-9_\-]{16,}"), "[REDACTED]"),
    (re.compile(r"gh[pousr]_[a-zA-Z0-9]{20,}"), "[REDACTED]"),
    (re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"), "[REDACTED]"),
    (re.compile(r"AIzaSy[a-zA-Z0-9_\-]{20,}"), "[REDACTED]"),
    (re.compile(r"(?i)(password\s*[:=]\s*)([^\s;&]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s;&]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(token\s*[:=]\s*)([^\s;&]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(secret\s*[:=]\s*)([^\s;&]+)"), r"\1[REDACTED]"),
]


def redact_sensitive_text(text: str) -> str:
    """Scrub sensitive credentials, bearer tokens, and API keys from text."""
    if not text:
        return text
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def classify_error(text: str) -> str:
    """Classify crash category based on error signatures."""
    if not text or not text.strip():
        return "UNKNOWN"

    lower = text.lower()
    if "timeouterror" in lower or "timed out" in lower:
        return "TIMEOUT"
    if "memoryerror" in lower or "unable to allocate" in lower or "out of memory" in lower:
        return "OOM"
    if "assertionerror" in lower or "assert " in lower:
        return "ASSERTION_FAILURE"
    if "permissionerror" in lower or "access is denied" in lower:
        return "PERMISSION_DENIED"
    if "filenotfounderror" in lower or "no such file or directory" in lower:
        return "NOT_FOUND"
    if "error" in lower or "exception" in lower or "traceback" in lower:
        return "EXCEPTION"
    return "UNKNOWN"


@dataclass
class CrashReport:
    """Structured report representing a failure/crash event."""

    crash_id: str
    timestamp: str
    item_id: str | None = None
    category: str = "UNKNOWN"
    error_message: str = ""
    traceback_cleaned: str = ""
    breadcrumbs: list[str] = field(default_factory=list)
    system_info: dict[str, Any] = field(default_factory=dict)
    reproduction_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CrashHarvester:
    """Collects and processes failure logs into structured CrashReports."""

    def __init__(self, work_dir: str | None = None, max_breadcrumbs: int = 20):
        self.work_dir = Path(work_dir) if work_dir else Path.cwd()
        self.max_breadcrumbs = max_breadcrumbs

    def harvest_from_file(self, log_path: str, item_id: str | None = None) -> CrashReport:
        p = Path(log_path)
        if not p.is_absolute():
            p = self.work_dir / p

        if not p.exists():
            return CrashReport(
                crash_id=f"crash-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                item_id=item_id,
                category="UNKNOWN",
                error_message=f"Log file missing: {p}",
                system_info=self._gather_system_info(),
            )

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return CrashReport(
                crash_id=f"crash-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                item_id=item_id,
                category="EXCEPTION",
                error_message=f"Error reading log file: {e}",
                system_info=self._gather_system_info(),
            )

        return self.harvest_from_text(content, item_id=item_id)

    def harvest_from_text(self, text: str, item_id: str | None = None) -> CrashReport:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        crash_id = f"crash-{uuid.uuid4().hex[:8]}"

        if not text or not text.strip():
            return CrashReport(
                crash_id=crash_id,
                timestamp=now_utc,
                item_id=item_id,
                category="UNKNOWN",
                error_message="Empty log or trace provided",
                system_info=self._gather_system_info(),
            )

        sanitized = redact_sensitive_text(text)
        lines = [line.rstrip() for line in sanitized.splitlines()]

        # Extract breadcrumbs (last N lines prior to trace or recent activity)
        breadcrumbs = lines[-self.max_breadcrumbs :] if len(lines) > self.max_breadcrumbs else list(lines)

        # Traceback and error message extraction
        error_msg = ""
        traceback_cleaned = ""
        category = classify_error(sanitized)

        # Find traceback block if present
        traceback_idx = -1
        for i, line in enumerate(lines):
            if "Traceback (most recent call last):" in line:
                traceback_idx = i
                break

        if traceback_idx != -1:
            traceback_lines = lines[traceback_idx:]
            traceback_cleaned = "\n".join(traceback_lines)
            # Last non-empty line of traceback is usually the exception message
            non_empty = [ln for ln in traceback_lines if ln.strip()]
            if non_empty:
                error_msg = non_empty[-1]
                category = classify_error(error_msg)
        else:
            # Look for error or failure line from bottom up
            for line in reversed(lines):
                if any(k in line.lower() for k in ("error", "exception", "failed", "failure", "fatal")):
                    error_msg = line.strip()
                    break
            if not error_msg and lines:
                error_msg = lines[-1].strip()

        hint = ""
        if item_id:
            safe_id = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(item_id))
            hint = f"python -m courier_core.worker run --item {safe_id}"

        return CrashReport(
            crash_id=crash_id,
            timestamp=now_utc,
            item_id=item_id,
            category=category,
            error_message=error_msg,
            traceback_cleaned=traceback_cleaned,
            breadcrumbs=breadcrumbs,
            system_info=self._gather_system_info(),
            reproduction_hint=hint,
        )

    def _gather_system_info(self) -> dict[str, Any]:
        return {
            "os": sys.platform,
            "python": sys.version.split()[0],
            "cwd": str(self.work_dir),
            "pid": os.getpid(),
        }


def harvest_crash(log_path: str, item_id: str | None = None, work_dir: str | None = None) -> CrashReport:
    """Convenience functional wrapper for harvesting."""
    harvester = CrashHarvester(work_dir=work_dir)
    return harvester.harvest_from_file(log_path, item_id=item_id)


def create_diagnostic_bundle(report: CrashReport, out_dir: str, make_zip: bool = False) -> str:
    """Serialize CrashReport to json and optionally produce zip bundle."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    json_filename = f"{report.crash_id}.json"
    json_path = out_path / json_filename
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    if not make_zip:
        return str(json_path)

    zip_filename = f"{report.crash_id}.zip"
    zip_path = out_path / zip_filename
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("crash_report.json", json.dumps(report.to_dict(), indent=2))
        if report.traceback_cleaned:
            zf.writestr("traceback.txt", report.traceback_cleaned)
        if report.reproduction_hint:
            repro_script = (
                f"@echo off\r\n{report.reproduction_hint}\r\n"
                if sys.platform == "win32"
                else f"#!/bin/sh\n{report.reproduction_hint}\n"
            )
            zf.writestr("reproduce.cmd" if sys.platform == "win32" else "reproduce.sh", repro_script)

    return str(zip_path)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI Entrypoint for Crash Report Harvester."""
    parser = argparse.ArgumentParser(description="Harvest and bundle crash reports.")
    parser.add_argument("--log-file", required=True, help="Path to input log/trace file")
    parser.add_argument("--out-dir", default="crashes", help="Output directory for reports")
    parser.add_argument("--item", help="Optional work item ID associated with crash")
    parser.add_argument("--bundle", action="store_true", help="Generate compressed zip bundle")

    args = parser.parse_args(argv)

    harvester = CrashHarvester()
    report = harvester.harvest_from_file(args.log_file, item_id=args.item)
    result_path = create_diagnostic_bundle(report, args.out_dir, make_zip=args.bundle)

    print(json.dumps({
        "status": "HARVESTED",
        "crash_id": report.crash_id,
        "category": report.category,
        "bundle": result_path,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
