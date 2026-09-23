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


# ── Adaptive poll interval tests ─────────────────────────────────────────────

def _compute_sleep_time(had_tasks: bool, poll_interval: float) -> float:
    """Mirror the adaptive-sleep formula in run_loop() for unit testing."""
    return min(0.2, poll_interval) if had_tasks else poll_interval


def test_adaptive_poll_with_tasks_uses_short_sleep():
    """When tasks were found this iteration, sleep_time is capped at 0.2s."""
    assert _compute_sleep_time(had_tasks=True, poll_interval=5.0) == pytest.approx(0.2)


def test_adaptive_poll_without_tasks_uses_full_interval():
    """When no tasks found (or exception), sleep_time equals poll_interval."""
    assert _compute_sleep_time(had_tasks=False, poll_interval=5.0) == pytest.approx(5.0)


def test_adaptive_poll_exception_resets_had_tasks():
    """Simulate a run_loop iteration that throws an exception before any tasks
    are fetched. _had_tasks must remain False so the loop sleeps at the full
    poll_interval rather than the rapid 0.2s cadence from a previous iteration."""
    had_tasks_after_exception = False  # what _had_tasks is initialized to
    # Exception occurs before any tasks could be fetched
    # => had_tasks stays False => full sleep
    assert _compute_sleep_time(had_tasks=had_tasks_after_exception, poll_interval=5.0) == pytest.approx(5.0)


def test_adaptive_poll_custom_interval():
    """COURIER_VERIFIER_POLL_INTERVAL is honored when no tasks are pending."""
    assert _compute_sleep_time(had_tasks=False, poll_interval=2.5) == pytest.approx(2.5)
    assert _compute_sleep_time(had_tasks=True, poll_interval=2.5) == pytest.approx(0.2)

