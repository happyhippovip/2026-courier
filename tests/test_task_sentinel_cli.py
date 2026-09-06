#!/usr/bin/env python3
"""Test suite for TaskSentinel CLI."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.task_sentinel_cli import TaskSentinel


class TestTaskSentinel(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="sentinel_test_"))
        self.sentinel = TaskSentinel(heartbeat_max_gap_seconds=10.0)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pid_truth_verification(self):
        """Validates current process PID is alive and dead PID is not."""
        my_pid = os.getpid()
        self.assertTrue(self.sentinel.check_pid_alive(my_pid))
        self.assertFalse(self.sentinel.check_pid_alive(99999999))
        self.assertFalse(self.sentinel.check_pid_alive(None))

    def test_02_worker_health_evaluation(self):
        """Accurately classifies HEALTHY, STALLED_HEARTBEAT, and ORPHANED_DEAD_PID."""
        now = dt.datetime.now(dt.timezone.utc)
        fresh_hb = now.isoformat()
        stale_hb = (now - dt.timedelta(seconds=45)).isoformat()

        # Healthy
        h = self.sentinel.inspect_worker_health("w1", os.getpid(), fresh_hb)
        self.assertEqual(h["status"], "HEALTHY")

        # Stalled heartbeat with live PID
        s = self.sentinel.inspect_worker_health("w2", os.getpid(), stale_hb)
        self.assertEqual(s["status"], "STALLED_HEARTBEAT")

        # Dead PID
        d = self.sentinel.inspect_worker_health("w3", 99999999, fresh_hb)
        self.assertEqual(d["status"], "ORPHANED_DEAD_PID")

    def test_03_posix_flock_lease_acquisition(self):
        """Acquires lock exclusively and prevents duplicate concurrent acquisition."""
        lock_file = self.test_dir / "worker.lock"
        ok1, fd1 = self.sentinel.try_acquire_flock_lease(lock_file)
        self.assertTrue(ok1)
        self.assertIsNotNone(fd1)

        ok2, fd2 = self.sentinel.try_acquire_flock_lease(lock_file)
        self.assertFalse(ok2)
        self.assertIsNone(fd2)

        os.close(fd1)


if __name__ == "__main__":
    unittest.main()
