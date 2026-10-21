"""Verifier receipts bind a PR head to a real run. Acceptance is fail-closed."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from courier_core.verifier_receipt import (  # noqa: E402
    issue,
    verify,
    main,
    _safe_rel,
    _pytest_skipped,
)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "effect.txt").write_text("effect\n")
    _git(root, "add", "effect.txt")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return root


def _issued(repo, **overrides):
    receipt = issue(
        repo,
        test_command="python3 -m pytest -q tests/test_verifier_receipt.py",
        exit_code=overrides.pop("exit_code", 0),
        skipped=overrides.pop("skipped", 0),
        artifacts=overrides.pop("artifacts", ["effect.txt"]),
        now=datetime(2026, 10, 13, 15, 30, tzinfo=timezone.utc),
    )
    receipt.update(overrides)
    return receipt


def test_matching_checkout_is_accepted(repo):
    receipt = _issued(repo)
    assert receipt["result"] == "RESULT_ACCEPTED"
    assert receipt["pr_head_sha"] == receipt["source_sha"]
    assert len(receipt["pr_head_sha"]) == 40
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_ACCEPTED"
    assert check["reason"] == ""


def test_sha_mismatch_is_rejected(repo):
    receipt = _issued(repo)
    receipt["pr_head_sha"] = "a" * 40
    receipt["source_sha"] = "a" * 40
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "sha_mismatch"


def test_source_sha_must_match_pr_head(repo):
    receipt = _issued(repo)
    receipt["source_sha"] = "b" * 40
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "sha_mismatch"


def test_uppercase_sha_is_not_the_checkout(repo):
    receipt = _issued(repo)
    receipt["pr_head_sha"] = receipt["pr_head_sha"].upper()
    receipt["source_sha"] = receipt["source_sha"].upper()
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "sha_mismatch"


def test_changed_artifact_hash_is_rejected(repo):
    receipt = _issued(repo)
    (repo / "effect.txt").write_text("tampered\n")
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "artifact_hash"


def test_nonzero_exit_is_rejected(repo):
    receipt = _issued(repo, exit_code=1)
    assert receipt["result"] == "RESULT_REJECTED"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "exit_nonzero"


def test_accepted_with_nonzero_exit_is_rejected(repo):
    receipt = _issued(repo)
    receipt["exit_code"] = 2
    receipt["result"] = "RESULT_ACCEPTED"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "exit_nonzero"


def test_missing_field_is_rejected(repo):
    receipt = _issued(repo)
    del receipt["timestamp"]
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "missing_field"


def test_skip_is_not_success(repo):
    receipt = _issued(repo, skipped=1)
    assert receipt["result"] == "RESULT_REJECTED"
    forged = dict(receipt, result="RESULT_ACCEPTED")
    check = verify(forged, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "skip_as_success"


def test_skip_token_is_not_success(repo):
    receipt = _issued(repo)
    receipt["result"] = "SKIPPED"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "skip_as_success"


def test_unknown_state_is_rejected(repo):
    receipt = _issued(repo)
    receipt["result"] = "VERIFIED"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "unknown_state"


def test_dishonest_platform_is_rejected(repo):
    receipt = _issued(repo)
    receipt["platform"] = "windows" if receipt["platform"] != "windows" else "linux"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "unknown_state"


def test_later_head_mismatches_until_revision_is_the_attested_commit(repo):
    receipt = _issued(repo)
    (repo / "later.txt").write_text("later\n")
    _git(repo, "add", "later.txt")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "later")
    assert verify(receipt, repo)["reason"] == "sha_mismatch"
    check = verify(receipt, repo, revision=receipt["pr_head_sha"])
    assert check["result"] == "RESULT_ACCEPTED"
    assert check["reason"] == ""


def test_cli_verify_rejects_and_accepts(repo, tmp_path):
    receipt = _issued(repo)
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    assert main(["verify", str(path), "--repo", str(repo)]) == 0
    receipt["exit_code"] = 1
    receipt["result"] = "RESULT_ACCEPTED"
    path.write_text(json.dumps(receipt))
    assert main(["verify", str(path), "--repo", str(repo)]) == 1


def test_safe_rel_rejects_backslashes_and_traversals():
    assert _safe_rel("foo/bar.txt") == "foo/bar.txt"
    assert _safe_rel("") is None
    assert _safe_rel("   ") is None
    assert _safe_rel("/foo/bar.txt") is None
    assert _safe_rel(r"\foo\bar.txt") is None
    assert _safe_rel(r"foo\bar.txt") is None
    assert _safe_rel("../bar.txt") is None
    assert _safe_rel("foo/../../bar.txt") is None
    assert _safe_rel("C:/foo/bar.txt") is None
    assert _safe_rel(123) is None


def test_issue_rejects_empty_artifacts_or_missing_files(repo):
    rec_empty = issue(repo, test_command="pytest", exit_code=0, skipped=0, artifacts=[])
    assert rec_empty["result"] == "RESULT_REJECTED"

    rec_missing = issue(repo, test_command="pytest", exit_code=0, skipped=0, artifacts=["nonexistent.txt"])
    assert rec_missing["result"] == "RESULT_REJECTED"

    rec_backslash = issue(repo, test_command="pytest", exit_code=0, skipped=0, artifacts=[r"dir\file.txt"])
    assert rec_backslash["result"] == "RESULT_REJECTED"

    rec_empty_cmd = issue(repo, test_command="  ", exit_code=0, skipped=0, artifacts=["effect.txt"])
    assert rec_empty_cmd["result"] == "RESULT_REJECTED"


def test_verify_rejects_extra_fields_or_duplicate_artifacts(repo):
    receipt = _issued(repo)
    receipt["extra_field"] = "surprise"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "unknown_state"

    receipt2 = _issued(repo)
    receipt2["artifacts"] = receipt2["artifacts"] + receipt2["artifacts"]
    check2 = verify(receipt2, repo)
    assert check2["result"] == "RESULT_REJECTED"
    assert check2["reason"] == "artifact_hash"

    receipt3 = _issued(repo)
    receipt3["artifacts"][0]["sha256"] = "invalid-hex-length"
    check3 = verify(receipt3, repo)
    assert check3["result"] == "RESULT_REJECTED"
    assert check3["reason"] == "artifact_hash"


def test_verify_rejects_naive_timestamp_or_invalid_counts(repo):
    receipt = _issued(repo)
    receipt["timestamp"] = "2026-10-13T15:30:00"
    check = verify(receipt, repo)
    assert check["result"] == "RESULT_REJECTED"
    assert check["reason"] == "unknown_state"

    receipt2 = _issued(repo)
    receipt2["exit_code"] = "0"
    check2 = verify(receipt2, repo)
    assert check2["result"] == "RESULT_REJECTED"
    assert check2["reason"] == "unknown_state"

    receipt3 = _issued(repo)
    receipt3["skipped"] = -1
    check3 = verify(receipt3, repo)
    assert check3["result"] == "RESULT_REJECTED"
    assert check3["reason"] == "unknown_state"


def test_pytest_skipped_parser_contract():
    assert _pytest_skipped("14 passed in 0.50s") == 0
    assert _pytest_skipped("12 passed, 2 skipped in 1.23s") == 2
    assert _pytest_skipped("no summary line here") is None


def test_cli_issue_success_and_failure(repo, tmp_path):
    out_file = tmp_path / "out_receipt.json"
    res0 = main([
        "issue",
        "--repo", str(repo),
        "--command", "pytest",
        "--artifact", "effect.txt",
        "--exit-code", "0",
        "--skipped", "0",
        "--out", str(out_file),
    ])
    assert res0 == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text())
    assert data["result"] == "RESULT_ACCEPTED"

    res1 = main([
        "issue",
        "--repo", str(repo),
        "--command", "pytest",
        "--artifact", "effect.txt",
        "--exit-code", "1",
        "--skipped", "0",
    ])
    assert res1 == 1

    res2 = main([
        "issue",
        "--repo", str(repo),
        "--command", "pytest",
        "--artifact", "effect.txt",
    ])
    assert res2 == 2
