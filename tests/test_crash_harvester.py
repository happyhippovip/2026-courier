"""Tests for Crash Report Harvester and Diagnostic Bundler."""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path
import pytest

from courier_core.crash_harvester import (
    CrashHarvester,
    CrashReport,
    harvest_crash,
    classify_error,
    redact_sensitive_text,
    create_diagnostic_bundle,
    main,
)


def test_redaction_of_sensitive_patterns():
    ghp_dummy = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz"
    ghs_dummy = "ghs_" + "1234567890abcdefghijklmnopqrstuvwxyz"
    pat_dummy = "github_pat_" + "11ABCDEF0123456789_secret"
    google_dummy = "AIzaSy" + "AbCdEfGhIjKlMnOpQrStUvWxYz0123456"
    raw = (
        "Authorization: Bearer my-secret-jwt-token-12345\n"
        "Connecting with api_key=sk-ant-api03-abcdef1234567890\n"
        "password=SuperSecretPassword! in connection URI\n"
        f"token: {ghp_dummy}\n"
        f"{ghs_dummy} and {pat_dummy}\n"
        f"google key {google_dummy}\n"
    )
    redacted = redact_sensitive_text(raw)
    assert "my-secret-jwt-token-12345" not in redacted
    assert "sk-ant-api03-abcdef1234567890" not in redacted
    assert "SuperSecretPassword!" not in redacted
    assert "ghp_1234567890abcdef" not in redacted
    assert "ghs_1234567890abcdef" not in redacted
    assert "github_pat_11ABCDEF" not in redacted
    assert "AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz0123456" not in redacted
    assert "[REDACTED]" in redacted


def test_classification_categories():
    assert classify_error("TimeoutError: Operation timed out after 30s") == "TIMEOUT"
    assert classify_error("Process timed out after 60 seconds") == "TIMEOUT"
    assert classify_error("MemoryError: Unable to allocate 4.00 GiB") == "OOM"
    assert classify_error("AssertionError: Expected 200 OK got 500") == "ASSERTION_FAILURE"
    assert classify_error("PermissionError: [WinError 5] Access is denied") == "PERMISSION_DENIED"
    assert classify_error("FileNotFoundError: [Errno 2] No such file") == "NOT_FOUND"
    assert classify_error("ZeroDivisionError: division by zero") == "EXCEPTION"
    assert classify_error("") == "UNKNOWN"


def test_harvest_exception_traceback(tmp_path):
    log_content = (
        "2026-10-18T12:00:00Z [INFO] Initializing worker\n"
        "2026-10-18T12:00:01Z [INFO] Processing workkey P17\n"
        "Traceback (most recent call last):\n"
        '  File "worker.py", line 42, in run\n'
        '    raise ValueError("Invalid configuration for worker")\n'
        "ValueError: Invalid configuration for worker\n"
    )
    log_file = tmp_path / "worker_err.log"
    log_file.write_text(log_content, encoding="utf-8")

    harvester = CrashHarvester(work_dir=str(tmp_path))
    report = harvester.harvest_from_file(str(log_file), item_id="P17")

    assert report.item_id == "P17"
    assert report.category == "EXCEPTION"
    assert "ValueError: Invalid configuration for worker" in report.error_message
    assert len(report.breadcrumbs) >= 2
    assert "Initializing worker" in report.breadcrumbs[0]
    assert report.crash_id.startswith("crash-")


def test_context_breadcrumbs_window(tmp_path):
    lines = [f"2026-10-18T12:00:{i:02d}Z Line {i}" for i in range(100)]
    lines.append("Exception: Sudden unexpected failure")
    log_file = tmp_path / "long.log"
    log_file.write_text("\n".join(lines), encoding="utf-8")

    harvester = CrashHarvester(max_breadcrumbs=10)
    report = harvester.harvest_from_file(str(log_file))

    assert len(report.breadcrumbs) == 10
    assert "Line 99" in report.breadcrumbs[-2]
    assert "Exception: Sudden unexpected failure" in report.breadcrumbs[-1]


def test_bundle_creation_and_reproduction_hint(tmp_path):
    report = CrashReport(
        crash_id="crash-test-001",
        timestamp="2026-10-18T12:00:00Z",
        item_id="P17",
        category="TIMEOUT",
        error_message="Subprocess timed out",
        traceback_cleaned="TimeoutError: Worker timed out",
        breadcrumbs=["Starting", "Waiting"],
        system_info={"os": sys.platform, "python": sys.version},
        reproduction_hint="python -m courier_core.worker run --item P17",
    )

    out_dir = tmp_path / "crash_dumps"
    bundle_path = create_diagnostic_bundle(report, str(out_dir), make_zip=True)

    json_path = out_dir / "crash-test-001.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["crash_id"] == "crash-test-001"
    assert data["category"] == "TIMEOUT"
    assert data["reproduction_hint"] == "python -m courier_core.worker run --item P17"

    zip_file = Path(bundle_path)
    assert zip_file.exists()
    assert zip_file.suffix == ".zip"
    with zipfile.ZipFile(zip_file, "r") as zf:
        namelist = zf.namelist()
        assert "crash_report.json" in namelist


def test_resilience_empty_or_missing_file(tmp_path):
    missing_file = tmp_path / "does_not_exist.log"
    harvester = CrashHarvester()
    report = harvester.harvest_from_file(str(missing_file), item_id="P17")
    assert report.category == "UNKNOWN"
    assert "FileNotFound" in report.error_message or "missing" in report.error_message.lower()

    empty_file = tmp_path / "empty.log"
    empty_file.write_text("", encoding="utf-8")
    report2 = harvester.harvest_from_file(str(empty_file), item_id="P17")
    assert report2.category == "UNKNOWN"


def test_cli_invocation(tmp_path):
    log_file = tmp_path / "cli_crash.log"
    log_file.write_text(
        "Traceback (most recent call last):\n"
        '  File "test.py", line 1, in <module>\n'
        "AssertionError: Expected true got false\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "cli_out"
    code = main([
        "--log-file", str(log_file),
        "--out-dir", str(out_dir),
        "--item", "P17",
        "--bundle",
    ])
    assert code == 0
    assert out_dir.exists()
    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) == 1
    content = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert content["category"] == "ASSERTION_FAILURE"
