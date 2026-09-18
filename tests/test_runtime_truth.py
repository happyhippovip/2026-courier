"""Bounded runtime-truth collection: no single query may hang the worker."""

import subprocess
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import runtime_truth


def test_get_sha_matches_repo_head():
    repo = Path(__file__).parent.parent.resolve()
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), timeout=15
    ).decode().strip()
    assert runtime_truth.get_sha(str(repo)) == expected


def test_get_sha_without_git_or_sha_file():
    assert (
        runtime_truth.get_sha("/nonexistent-dir-xyz") == "UNKNOWN_NO_GIT_NO_SHA_FILE"
    )


def test_remote_sha_call_is_time_bounded():
    seen = {}

    def fake_check_output(*args, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired("git", 25)

    with mock.patch.object(runtime_truth.subprocess, "check_output", fake_check_output):
        assert runtime_truth.get_remote_sha(".") == "UNKNOWN"
    assert seen.get("timeout") == 25


def test_runtime_info_completes_with_all_keys():
    info = runtime_truth.get_runtime_info()
    for key in (
        "CANONICAL_HEAD_SHA",
        "REMOTE_HEAD_SHA",
        "TESTED_SHA",
        "DEPLOYED_SHA",
        "ACTUAL_SERVING_RUNTIME_SHA",
        "ACCEPTANCE_BOUND_SHA",
        "RUNTIME_PROCESS_IDENTITY",
    ):
        assert key in info
