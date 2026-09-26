#!/usr/bin/env python3
"""Targeted unit tests for Courier Verifier boundary containment and fail-closed safety."""

import hashlib
from pathlib import Path
import pytest

from scripts.courier_verifier import verify_artifact, verify_artifacts


def test_verify_artifact_contained_success(tmp_path):
    f = tmp_path / "valid.txt"
    content = b"artifact content 123"
    f.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()

    assert verify_artifact("valid.txt", expected_hash, repo_root=tmp_path) is True


def test_verify_artifact_missing(tmp_path):
    assert verify_artifact("nonexistent.txt", "abc", repo_root=tmp_path) is False


def test_verify_artifact_hash_mismatch(tmp_path):
    f = tmp_path / "valid.txt"
    f.write_bytes(b"content")
    assert verify_artifact("valid.txt", "wrong_hash", repo_root=tmp_path) is False


def test_verify_artifact_path_traversal_rejected(tmp_path):
    # Path attempting to escape repo_root via ../
    assert verify_artifact("../../../../etc/hosts", "dummy", repo_root=tmp_path) is False


def test_verify_artifact_absolute_escape_rejected(tmp_path):
    # Absolute path outside repo_root
    assert verify_artifact("/etc/hosts", "dummy", repo_root=tmp_path) is False


def test_verify_artifacts_empty_artifacts_fails_closed():
    task = {"task_id": "T-1", "target_capability": "mac"}
    result = {"status": "SUCCESS", "artifacts": []}
    assert verify_artifacts(task, result) == "FAIL"


def test_verify_artifacts_non_dict_elements_fails_closed():
    task = {"task_id": "T-1", "target_capability": "mac"}
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": ["canary.txt"]}) == "FAIL"
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": [123]}) == "FAIL"
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": [None]}) == "FAIL"
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": None}) == "FAIL"
    assert verify_artifacts(task, "not a dict") == "FAIL"


def test_verify_artifacts_missing_or_invalid_fields_fails_closed():
    task = {"task_id": "T-1", "target_capability": "mac"}
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": [{"path": None, "sha256": "abc"}]}) == "FAIL"
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": [{"path": "file.txt"}]}) == "FAIL"
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": [{"sha256": "abc"}]}) == "FAIL"
    assert verify_artifacts(task, {"status": "SUCCESS", "artifacts": [{"path": "file.txt", "sha256": 123}]}) == "FAIL"
