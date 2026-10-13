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
