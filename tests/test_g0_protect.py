"""G0 Daten schützen: backup manifest, hash check, deletion only as dry-run."""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from courier_core.g0_protect import (  # noqa: E402
    GATE_STATUSES,
    build_manifest,
    check_manifest,
    deletion_plan,
    gate_status,
)


def _file(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, newline="\n")
    return path


def test_manifest_records_path_size_and_sha256(tmp_path):
    payload = "keep\n"
    _file(tmp_path, "keep.txt", payload)
    manifest = build_manifest(tmp_path, ["keep.txt"])
    [entry] = manifest["entries"]
    assert entry["path"] == "keep.txt"
    assert entry["size"] == len(payload.encode())
    assert entry["sha256"] == hashlib.sha256(payload.encode()).hexdigest()
    assert len(entry["sha256"]) == 64


def test_matching_manifest_passes(tmp_path):
    _file(tmp_path, "keep.txt", "keep\n")
    manifest = build_manifest(tmp_path, ["keep.txt"])
    assert check_manifest(tmp_path, manifest)["result"] == "PASS"


def test_hash_deviation_is_fail(tmp_path):
    _file(tmp_path, "keep.txt", "keep\n")
    manifest = build_manifest(tmp_path, ["keep.txt"])
    (tmp_path / "keep.txt").write_text("changed\n")
    assert check_manifest(tmp_path, manifest)["result"] == "FAIL"


def test_size_deviation_is_fail(tmp_path):
    _file(tmp_path, "keep.txt", "keep\n")
    manifest = build_manifest(tmp_path, ["keep.txt"])
    manifest["entries"][0]["size"] += 1
    assert check_manifest(tmp_path, manifest)["result"] == "FAIL"


def test_missing_file_is_fail(tmp_path):
    path = _file(tmp_path, "keep.txt", "keep\n")
    manifest = build_manifest(tmp_path, ["keep.txt"])
    path.unlink()
    assert check_manifest(tmp_path, manifest)["result"] == "FAIL"


def test_unknown_is_not_pass(tmp_path):
    _file(tmp_path, "keep.txt", "keep\n")
    manifest = build_manifest(tmp_path, ["keep.txt"])
    manifest["entries"][0]["sha256"] = "UNKNOWN"
    result = check_manifest(tmp_path, manifest)["result"]
    assert result == "UNKNOWN"
    assert result != "PASS"


def test_unhashable_directory_is_unknown_not_pass(tmp_path):
    (tmp_path / "folder").mkdir()
    manifest = {
        "entries": [{"path": "folder", "size": 0, "sha256": "ab" * 32}],
    }
    result = check_manifest(tmp_path, manifest)["result"]
    assert result == "UNKNOWN"
    assert result != "PASS"


def test_path_escape_is_unknown_not_pass(tmp_path):
    manifest = {
        "entries": [{"path": "../outside.txt", "size": 1, "sha256": "ab" * 32}],
    }
    result = check_manifest(tmp_path, manifest)["result"]
    assert result == "UNKNOWN"
    assert result != "PASS"


def test_empty_manifest_is_unknown_not_pass(tmp_path):
    result = check_manifest(tmp_path, {"entries": []})["result"]
    assert result == "UNKNOWN"
    assert result != "PASS"


def test_deletion_is_dry_run_and_removes_nothing(tmp_path):
    _file(tmp_path, "a.txt", "a")
    _file(tmp_path, "b.txt", "b")
    plan = deletion_plan(tmp_path, ["a.txt", "b.txt"], approvals=["a.txt"])
    assert plan["mode"] == "DRY_RUN"
    assert plan["deleted"] == []
    assert (tmp_path / "a.txt").is_file()
    assert (tmp_path / "b.txt").is_file()
    by_path = {item["path"]: item for item in plan["candidates"]}
    assert by_path["a.txt"]["approved"] is True
    assert by_path["a.txt"]["action"] == "DRY_RUN"
    assert by_path["b.txt"]["approved"] is False
    assert by_path["b.txt"]["action"] == "DRY_RUN"


def test_approval_does_not_cover_another_candidate(tmp_path):
    _file(tmp_path, "a.txt", "a")
    _file(tmp_path, "a.txt.bak", "bak")
    plan = deletion_plan(tmp_path, ["a.txt", "a.txt.bak"], approvals=["a.txt"])
    by_path = {item["path"]: item for item in plan["candidates"]}
    assert by_path["a.txt"]["approved"] is True
    assert by_path["a.txt.bak"]["approved"] is False
    assert (tmp_path / "a.txt.bak").read_text() == "bak"


def test_wildcard_is_not_approval(tmp_path):
    _file(tmp_path, "a.txt", "a")
    plan = deletion_plan(tmp_path, ["a.txt"], approvals=["*"])
    assert plan["candidates"][0]["approved"] is False
    assert (tmp_path / "a.txt").is_file()


def test_no_approval_stays_unapproved(tmp_path):
    _file(tmp_path, "a.txt", "a")
    plan = deletion_plan(tmp_path, ["a.txt"], approvals=[])
    assert plan["candidates"][0]["approved"] is False
    assert plan["deleted"] == []


def test_gate_status_is_only_not_tested_or_test_passed():
    assert GATE_STATUSES == ("NOT TESTED", "TEST PASSED")
    assert gate_status(False) == "NOT TESTED"
    assert gate_status(True) == "TEST PASSED"
    assert gate_status("VERIFIED") == "NOT TESTED"
    assert "VERIFIED" not in GATE_STATUSES
