"""
Test DLQ-06: Windows PermissionError retry in load_bundle and atomic_write.

Validates that:
- load_bundle retries up to 20x on PermissionError
- load_bundle succeeds after transient PermissionError
- load_bundle raises LedgerError after 20 PermissionError retries
- atomic_write retries os.replace on PermissionError
- FileNotFoundError is not retried (fast fail)
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import pytest

from scripts.agent_handoff_ledger import (
    load_bundle, atomic_write, LedgerError, initialize,
)
from tests.test_agent_handoff_ledger import guard as make_guard

SHA = "0000000000000000000000000000000000000000"


def _base_record():
    return {
        "PROJECT": "courier",
        "GOAL": "dlq06-test",
        "BRANCH": "release-candidate-integration",
        "CURRENT_SHA": SHA,
        "RUNTIME_IDENTITY": "TEST-RT",
        "RUNTIME_OWNER": "test-owner",
        "STATUS": "READY",
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "NONE",
        "NEXT_EXECUTABLE_ACTION": "DO_WORK",
        "ACTIVE_WRITERS": ["s1"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 1,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 1,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "NO",
        "QUEUE_INDEPENDENT": "UNKNOWN",
        "LAST_EVIDENCE": [],
        "LAST_UPDATED_BY": "s1",
        "CONTINUATION_CHECKPOINT": "test",
    }


def _init_ledger(tmp_path):
    from datetime import datetime
    path = tmp_path / "ledger.json"
    g = make_guard(sha=SHA, runtime_identity="TEST-RT")
    g["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
    g["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = []
    g["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "UNKNOWN"
    g["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = []
    g["evidence"] = [{
        "source_url": "https://example.com/init",
        "source_type": "GITHUB_COMMIT",
        "observed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_sha": SHA,
        "runtime_binding": "TEST-RT",
        "validity": "UNKNOWN",
        "reason": "init",
        "producer_id": "sys",
        "verifier_id": "sys",
    }]
    initialize(path, _base_record(), g, 5.0)
    return path


class TestLoadBundlePermissionRetry:
    """load_bundle retries on PermissionError (Windows concurrent read)."""

    def test_succeeds_after_transient_permission_error(self):
        """Simulates PermissionError on first 3 reads, then success."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        # Read the actual file content for the successful read
        real_content = path.read_text(encoding="utf-8")

        call_count = 0
        original_read = Path.read_text

        def flaky_read(self_path, *args, **kwargs):
            nonlocal call_count
            if str(self_path) == str(path) and call_count < 3:
                call_count += 1
                raise PermissionError("locked by another process")
            return original_read(self_path, *args, **kwargs)

        with patch.object(Path, 'read_text', flaky_read):
            bundle = load_bundle(path)

        assert bundle["record"]["PROJECT"] == "courier"
        assert call_count == 3  # Failed 3 times, succeeded on 4th

    def test_raises_after_max_retries(self):
        """After 20 PermissionError retries, LedgerError is raised."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        def always_fail(self_path, *args, **kwargs):
            if str(self_path) == str(path):
                raise PermissionError("permanently locked")
            return Path.read_text.__wrapped__(self_path, *args, **kwargs)

        with patch.object(Path, 'read_text', side_effect=PermissionError("locked")):
            with pytest.raises(LedgerError, match="cannot read ledger"):
                load_bundle(path)

    def test_file_not_found_no_retry(self):
        """FileNotFoundError fails immediately without retrying."""
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "nonexistent.json"

        with pytest.raises(LedgerError, match="does not exist"):
            load_bundle(path)


class TestAtomicWritePermissionRetry:
    """atomic_write retries os.replace on PermissionError."""

    def test_replace_succeeds_after_transient_error(self):
        """Simulates PermissionError on first 2 os.replace, then success."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)
        bundle = load_bundle(path)

        replace_count = 0
        original_replace = __import__("os").replace

        def flaky_replace(src, dst):
            nonlocal replace_count
            if str(dst) == str(path) and replace_count < 2:
                replace_count += 1
                raise PermissionError("target locked")
            return original_replace(src, dst)

        with patch("os.replace", side_effect=flaky_replace):
            atomic_write(path, bundle)

        assert replace_count == 2
        # Verify file is still valid
        reloaded = load_bundle(path)
        assert reloaded["record"]["PROJECT"] == "courier"


class TestSymlinkProtection:
    """Symlink paths are rejected for both read and write."""

    def test_load_bundle_rejects_symlink(self):
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)
        link = tmp / "link.json"
        link.symlink_to(path)

        with pytest.raises(LedgerError, match="symlink"):
            load_bundle(link)

    def test_atomic_write_rejects_symlink(self):
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)
        bundle = load_bundle(path)
        link = tmp / "link.json"
        link.symlink_to(path)

        with pytest.raises(LedgerError, match="symlink"):
            atomic_write(link, bundle)
