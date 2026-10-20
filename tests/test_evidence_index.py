"""Unit tests for courier_core.evidence_index (P4)."""

import hashlib
import json
import pytest
from pathlib import Path

from courier_core.evidence_index import (
    index_evidence,
    verify_evidence_index,
    main,
    EvidenceIndex,
)


def test_index_evidence_home_not_found(tmp_path):
    idx = index_evidence(tmp_path / "nonexistent")
    assert idx.status == "NOT_FOUND"
    assert idx.total_files == 0
    assert idx.error_detail is not None


def test_index_evidence_empty_home(tmp_path):
    empty = tmp_path / "empty_home"
    empty.mkdir()
    idx = index_evidence(empty)
    assert idx.status == "EMPTY"
    assert idx.total_files == 0
    assert idx.files == []
    assert idx.index_sha256 == hashlib.sha256(b"[]").hexdigest()


def test_index_evidence_with_evidence_dir(tmp_path):
    home = tmp_path / "home_with_evidence"
    home.mkdir()
    ev_dir = home / "evidence"
    ev_dir.mkdir()

    server_log = ev_dir / "server_run1.log"
    server_log.write_text("server log content\n", encoding="utf-8")

    worker_log = ev_dir / "worker_run1.log"
    worker_log.write_text("worker log line 1\nworker log line 2\n", encoding="utf-8")

    pilot_record = ev_dir / "pilot_evidence_01.json"
    record_data = {
        "pilot_id": "pilot-100",
        "evidence_type": "TECHNICAL",
        "metric": "lcp_ms",
        "result": "850",
        "timestamp_utc": "2026-10-18T10:00:00Z"
    }
    pilot_record.write_text(json.dumps(record_data), encoding="utf-8")

    idx = index_evidence(home)
    assert idx.status == "OK"
    assert idx.total_files == 3
    assert idx.total_bytes == len(server_log.read_bytes()) + len(worker_log.read_bytes()) + len(pilot_record.read_bytes())
    assert "LOG" in idx.categories
    assert "JSON_RECORD" in idx.categories
    assert len(idx.index_sha256) == 64

    # Check deterministic ordering
    paths = [f["relative_path"] for f in idx.files]
    assert paths == sorted(paths)

    # Check pilot record parsing
    pilot_entry = next(f for f in idx.files if "pilot_evidence_01.json" in f["relative_path"])
    assert pilot_entry["pilot_evidence"] is not None
    assert pilot_entry["pilot_evidence"]["pilot_id"] == "pilot-100"
    assert pilot_entry["pilot_evidence"]["evidence_type"] == "TECHNICAL"


def test_index_evidence_with_root_evidence_files(tmp_path):
    home = tmp_path / "home_root_evidence"
    home.mkdir()

    run_proof = home / "run1.evidence.json"
    run_proof.write_text('{"evidence": "validated"}', encoding="utf-8")

    result_md = home / "G201.result.md"
    result_md.write_text("# Result G201\nOutcome: DONE\n", encoding="utf-8")

    idx = index_evidence(home)
    assert idx.status == "OK"
    assert idx.total_files == 2
    paths = [f["relative_path"] for f in idx.files]
    assert "run1.evidence.json" in paths
    assert "G201.result.md" in paths


def test_index_evidence_read_only_never_mutates_home(tmp_path):
    home = tmp_path / "ro_home"
    home.mkdir()
    ev_dir = home / "evidence"
    ev_dir.mkdir()
    sample = ev_dir / "sample.log"
    sample.write_text("IMMUTABLE DATA", encoding="utf-8")
    before_mtime = sample.stat().st_mtime_ns

    idx = index_evidence(home)
    assert idx.status == "OK"

    after_mtime = sample.stat().st_mtime_ns
    assert before_mtime == after_mtime


def test_verify_evidence_index_happy_path(tmp_path):
    home = tmp_path / "verify_happy"
    home.mkdir()
    ev_dir = home / "evidence"
    ev_dir.mkdir()
    (ev_dir / "test.log").write_text("Hello World", encoding="utf-8")

    idx = index_evidence(home)
    index_file = home / "evidence_index.json"
    idx.write_index(index_file)
    assert index_file.exists()

    valid, reason = verify_evidence_index(index_file, home=home)
    assert valid is True
    assert reason == "VERIFIED"


def test_verify_evidence_index_detects_tampered_file(tmp_path):
    home = tmp_path / "verify_tampered"
    home.mkdir()
    ev_dir = home / "evidence"
    ev_dir.mkdir()
    log_file = ev_dir / "audit.log"
    log_file.write_text("ORIGINAL CONTENT", encoding="utf-8")

    idx = index_evidence(home)
    index_file = home / "evidence_index.json"
    idx.write_index(index_file)

    # Tamper with file
    log_file.write_text("TAMPERED CONTENT", encoding="utf-8")

    valid, reason = verify_evidence_index(index_file, home=home)
    assert valid is False
    assert "sha256 mismatch" in reason


def test_verify_evidence_index_detects_missing_file(tmp_path):
    home = tmp_path / "verify_missing"
    home.mkdir()
    ev_dir = home / "evidence"
    ev_dir.mkdir()
    log_file = ev_dir / "delete_me.log"
    log_file.write_text("Temporary", encoding="utf-8")

    idx = index_evidence(home)
    index_file = home / "evidence_index.json"
    idx.write_index(index_file)

    # Delete the file
    log_file.unlink()

    valid, reason = verify_evidence_index(index_file, home=home)
    assert valid is False
    assert "Missing evidence file" in reason


def test_cli_index_and_verify(tmp_path, capsys):
    home = tmp_path / "cli_test"
    home.mkdir()
    ev_dir = home / "evidence"
    ev_dir.mkdir()
    (ev_dir / "cli_sample.txt").write_text("CLI evidence", encoding="utf-8")

    out_json = home / "cli_index.json"

    # Index command
    code = main(["--home", str(home), "--output", str(out_json)])
    assert code == 0
    assert out_json.exists()

    # Verify command
    code = main(["--verify", str(out_json), "--home", str(home)])
    assert code == 0
    captured = capsys.readouterr().out
    assert "VERIFIED" in captured
