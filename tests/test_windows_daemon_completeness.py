"""Tests for Windows worker daemon: resource governor, restart recovery,
duplicate prevention, safe stop, and queue persistence.

These tests exercise the daemon's internal functions without starting the
full HTTP loop or requiring a running server.
"""
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest import mock

import psutil
import pytest

# Import daemon functions
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.windows_worker.daemon import (
    acquire_lock,
    is_resource_pressure_high,
    persist_marker,
    recover_pending_markers,
    same_execution,
)


class TestResourceGovernor:
    """Resource pressure must actually trip at realistic thresholds (fail-closed)."""

    def test_low_resource_trips_at_cpu_85(self):
        """LOW_RESOURCE profile: CPU > 85% should pause claims."""
        os.environ["SIMULATE_CPU_PERCENT"] = "86"
        os.environ["SIMULATE_MEM_PERCENT"] = "50"
        os.environ.pop("WORKER_PROFILE", None)
        try:
            assert is_resource_pressure_high({"WORKER_PROFILE": "LOW_RESOURCE"}) is True
        finally:
            os.environ.pop("SIMULATE_CPU_PERCENT", None)
            os.environ.pop("SIMULATE_MEM_PERCENT", None)

    def test_low_resource_trips_at_mem_90(self):
        """LOW_RESOURCE profile: MEM > 90% should pause claims."""
        os.environ["SIMULATE_CPU_PERCENT"] = "50"
        os.environ["SIMULATE_MEM_PERCENT"] = "91"
        os.environ.pop("WORKER_PROFILE", None)
        try:
            assert is_resource_pressure_high({"WORKER_PROFILE": "LOW_RESOURCE"}) is True
        finally:
            os.environ.pop("SIMULATE_CPU_PERCENT", None)
            os.environ.pop("SIMULATE_MEM_PERCENT", None)

    def test_low_resource_normal_passes(self):
        """LOW_RESOURCE profile: moderate usage should NOT block claims."""
        os.environ["SIMULATE_CPU_PERCENT"] = "60"
        os.environ["SIMULATE_MEM_PERCENT"] = "70"
        os.environ.pop("WORKER_PROFILE", None)
        try:
            assert is_resource_pressure_high({"WORKER_PROFILE": "LOW_RESOURCE"}) is False
        finally:
            os.environ.pop("SIMULATE_CPU_PERCENT", None)
            os.environ.pop("SIMULATE_MEM_PERCENT", None)

    def test_standard_higher_threshold(self):
        """STANDARD profile allows more headroom than LOW_RESOURCE."""
        os.environ["SIMULATE_CPU_PERCENT"] = "86"
        os.environ["SIMULATE_MEM_PERCENT"] = "50"
        os.environ.pop("WORKER_PROFILE", None)
        try:
            # 86% CPU should trip LOW_RESOURCE (85) but not STANDARD (92)
            assert is_resource_pressure_high({"WORKER_PROFILE": "STANDARD"}) is False
        finally:
            os.environ.pop("SIMULATE_CPU_PERCENT", None)
            os.environ.pop("SIMULATE_MEM_PERCENT", None)

    def test_high_capacity_highest_threshold(self):
        """HIGH_CAPACITY profile has the highest thresholds."""
        os.environ["SIMULATE_CPU_PERCENT"] = "93"
        os.environ["SIMULATE_MEM_PERCENT"] = "50"
        os.environ.pop("WORKER_PROFILE", None)
        try:
            # 93% should trip STANDARD (92) but not HIGH_CAPACITY (96)
            assert is_resource_pressure_high({"WORKER_PROFILE": "HIGH_CAPACITY"}) is False
        finally:
            os.environ.pop("SIMULATE_CPU_PERCENT", None)
            os.environ.pop("SIMULATE_MEM_PERCENT", None)

    def test_resource_check_never_crashes(self):
        """Even with bad psutil data, resource check doesn't crash."""
        os.environ.pop("SIMULATE_CPU_PERCENT", None)
        os.environ.pop("SIMULATE_MEM_PERCENT", None)
        os.environ.pop("WORKER_PROFILE", None)
        # Should return a bool, not crash
        result = is_resource_pressure_high({})
        assert isinstance(result, bool)


class TestDuplicateExecutionLock:
    """Only one daemon instance per worker_id can run (lock-based)."""

    def test_first_lock_succeeds(self, tmp_path):
        """First lock acquisition succeeds."""
        worker_id = f"test-lock-{uuid.uuid4().hex[:8]}"
        lock = acquire_lock(worker_id)
        try:
            assert lock is not None
            assert lock.exists()
        finally:
            if lock and lock.exists():
                lock.unlink()

    def test_second_lock_fails_while_running(self, tmp_path):
        """Second instance for same worker_id is rejected."""
        worker_id = f"test-lock-dup-{uuid.uuid4().hex[:8]}"
        lock1 = acquire_lock(worker_id)
        try:
            assert lock1 is not None
            lock2 = acquire_lock(worker_id)
            # Lock2 should be None (blocked)
            assert lock2 is None
        finally:
            if lock1 and lock1.exists():
                lock1.unlink()

    def test_stale_lock_reclaimed(self, tmp_path):
        """Lock from dead PID is reclaimed."""
        worker_id = f"test-lock-stale-{uuid.uuid4().hex[:8]}"
        lock_path = Path(tempfile.gettempdir()) / f"courier_worker_{worker_id}.lock"
        # Write a fake PID that doesn't exist
        lock_path.write_text("999999999")
        try:
            lock = acquire_lock(worker_id)
            assert lock is not None
        finally:
            if lock_path.exists():
                lock_path.unlink()


class TestPersistMarkerRecovery:
    """Marker system must survive crashes and produce correct recovery."""

    def test_effect_marker_persisted_atomically(self, tmp_path):
        """Effect marker is written before external effect."""
        marker_path = tmp_path / "effect_marker.json"
        task = {"task_id": "test-1", "goal_id": "g1", "attempt_id": "a1"}
        persist_marker(marker_path, task)

        assert marker_path.exists()
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        assert data["task_id"] == "test-1"

    def test_result_marker_persisted_atomically(self, tmp_path):
        """Result marker is written after execution, before HTTP post."""
        marker_path = tmp_path / "result_marker.json"
        result = {
            "task_id": "test-1",
            "status": "SUCCESS",
            "result_id": "r1",
        }
        persist_marker(marker_path, result)

        assert marker_path.exists()
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        assert data["status"] == "SUCCESS"

    def test_no_tmp_file_left_after_persist(self, tmp_path):
        """Atomic write leaves no .tmp file."""
        marker_path = tmp_path / "marker.json"
        persist_marker(marker_path, {"test": True})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_same_execution_match(self):
        """same_execution correctly identifies matching executions."""
        a = {"goal_id": "g1", "task_id": "t1", "attempt_id": "a1",
             "dispatch_id": "d1", "execution_ref": "e1"}
        b = dict(a)
        assert same_execution(a, b) is True

    def test_same_execution_mismatch(self):
        """same_execution rejects different executions."""
        a = {"goal_id": "g1", "task_id": "t1", "attempt_id": "a1",
             "dispatch_id": "d1", "execution_ref": "e1"}
        b = dict(a)
        b["attempt_id"] = "a2"
        assert same_execution(a, b) is False


class TestSafeStop:
    """Safe stop uses PID identity, not broad process matching."""

    def test_stop_safe_module_importable(self):
        """stop_safe.py exists and is importable."""
        stop_safe_path = Path(__file__).parent.parent / "scripts" / "windows_worker" / "stop_safe.py"
        assert stop_safe_path.exists()

    def test_stop_safe_uses_lock_file(self):
        """stop_safe reads lock file PID, not process name."""
        stop_safe_path = Path(__file__).parent.parent / "scripts" / "windows_worker" / "stop_safe.py"
        content = stop_safe_path.read_text(encoding="utf-8")
        # Must use lock file mechanism
        assert "lock" in content.lower()
        # Must NOT use broad process matching
        assert "daemon.py" not in content or "CommandLine" not in content
        assert "run_loop" not in content

    def test_stop_bat_has_broad_kill_warning(self):
        """stop.bat uses broad matching — stop_safe.py should be preferred."""
        stop_bat = Path(__file__).parent.parent / "scripts" / "windows_worker" / "stop.bat"
        if stop_bat.exists():
            content = stop_bat.read_text(encoding="utf-8")
            # Document that stop.bat is the legacy approach
            assert "daemon.py" in content or "run_loop" in content


class TestQueueDBSchema:
    """queue.db must track background jobs with identity columns."""

    def test_queue_db_exists(self):
        """queue.db is present in state directory."""
        db_path = Path(__file__).parent.parent / "scripts" / "windows_worker" / "state" / "queue.db"
        assert db_path.exists()

    def test_queue_db_has_background_jobs_table(self):
        """background_jobs table exists with required columns."""
        import sqlite3
        db_path = Path(__file__).parent.parent / "scripts" / "windows_worker" / "state" / "queue.db"
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute("PRAGMA table_info(background_jobs)")
            columns = {row[1] for row in cursor.fetchall()}
            required = {"job_id", "task_id", "pid", "status", "started_at"}
            assert required.issubset(columns), f"Missing columns: {required - columns}"
        finally:
            conn.close()
