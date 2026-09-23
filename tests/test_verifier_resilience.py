"""Verifier resilience and edge-case handling tests.

Verifies:
1. verify_artifact handles None, empty, directory, non-string, missing, and valid files safely.
2. Hash comparisons are case-insensitive and whitespace-trimmed.
3. Verification gracefully sets verdict=FAIL for malformed artifacts without crashing the verifier loop.
"""

import hashlib
import os
from pathlib import Path
import pytest

from scripts.courier_verifier import verify_artifact


def test_verify_artifact_none_path():
    assert verify_artifact(None, "dummy_hash") is False


def test_verify_artifact_empty_path():
    assert verify_artifact("", "dummy_hash") is False
    assert verify_artifact("   ", "dummy_hash") is False


def test_verify_artifact_non_string_path():
    assert verify_artifact(12345, "dummy_hash") is False
    assert verify_artifact(["path.txt"], "dummy_hash") is False
    assert verify_artifact({"path": "x"}, "dummy_hash") is False


def test_verify_artifact_directory_path(tmp_path):
    # Must not raise IsADirectoryError
    assert verify_artifact(str(tmp_path), "dummy_hash") is False


def test_verify_artifact_missing_file(tmp_path):
    missing = tmp_path / "absent.txt"
    assert verify_artifact(str(missing), "dummy_hash") is False


def test_verify_artifact_valid_file_and_hash(tmp_path):
    target = tmp_path / "valid.txt"
    content = b"hello world 2026-courier"
    target.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()
    
    # Exact match
    assert verify_artifact(str(target), expected_hash) is True
    # Case insensitivity
    assert verify_artifact(str(target), expected_hash.upper()) is True
    # Whitespace resilience
    assert verify_artifact(str(target), f"  {expected_hash}  ") is True


def test_verify_artifact_mismatched_hash(tmp_path):
    target = tmp_path / "valid.txt"
    target.write_bytes(b"actual content")
    wrong_hash = hashlib.sha256(b"different content").hexdigest()
    assert verify_artifact(str(target), wrong_hash) is False


def test_verify_artifact_none_expected_hash_checks_existence(tmp_path):
    target = tmp_path / "valid.txt"
    target.write_bytes(b"any content")
    assert verify_artifact(str(target), None) is True
    assert verify_artifact(str(target), "") is True


def test_verify_artifact_with_pathlib_object(tmp_path):
    target = tmp_path / "file.bin"
    target.write_bytes(b"binary data")
    expected_hash = hashlib.sha256(b"binary data").hexdigest()
    assert verify_artifact(target, expected_hash) is True
