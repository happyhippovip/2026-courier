#!/usr/bin/env python3
"""Acceptance Test Suite for Task Sentinel CLI."""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import sys

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from task_sentinel.cli import (
    LockManager,
    TaskSentinel,
    is_pid_alive,
)


class TestTaskSentinelCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="sentinel_test_"))
        self.sentinel = TaskSentinel()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pid_liveness_check(self):
        # Current PID must be alive
        my_pid = os.getpid()
        self.assertTrue(is_pid_alive(my_pid))
        res = self.sentinel.check_pid(my_pid)
        self.assertTrue(res["alive"])
        self.assertEqual(res["status"], "HEALTHY")

        # Inactive PID must be dead
        dead_pid = 99999999
        self.assertFalse(is_pid_alive(dead_pid))
        res_dead = self.sentinel.check_pid(dead_pid)
        self.assertFalse(res_dead["alive"])
        self.assertEqual(res_dead["status"], "DEAD")

    def test_02_lock_acquisition_and_release(self):
        lock_file = self.test_dir / "app.lock"
        mgr = LockManager(lock_file)
        
        # Initial acquisition
        self.assertTrue(mgr.acquire(timeout_seconds=0.1))
        self.assertTrue(lock_file.exists())
        
        # Second acquire by another instance on same file must fail non-blocking
        mgr2 = LockManager(lock_file)
        self.assertFalse(mgr2.acquire(timeout_seconds=0.05))

        # Release first lock
        mgr.release()

        # Now mgr2 should acquire successfully
        self.assertTrue(mgr2.acquire(timeout_seconds=0.1))
        mgr2.release()

    def test_03_heartbeat_freshness_and_stall_detection(self):
        hb_file = self.test_dir / "worker_heartbeat.json"
        
        # 1. Update heartbeat
        self.sentinel.update_heartbeat(hb_file, meta={"task": "BATCH_01"})
        self.assertTrue(hb_file.is_file())

        # 2. Verify fresh heartbeat
        res = self.sentinel.verify_heartbeat(hb_file, stall_timeout=10.0)
        self.assertFalse(res["stalled"])
        self.assertEqual(res["status"], "HEALTHY")

        # 3. Simulate stale heartbeat by rewriting timestamp to past
        data = json.loads(hb_file.read_text(encoding="utf-8"))
        data["timestamp"] = time.time() - 45.0  # 45 seconds ago
        hb_file.write_text(json.dumps(data), encoding="utf-8")

        res_stale = self.sentinel.verify_heartbeat(hb_file, stall_timeout=30.0)
        self.assertTrue(res_stale["stalled"])
        self.assertEqual(res_stale["status"], "STALLED_HEARTBEAT_GAP")

    def test_04_orphaned_process_dead_detection(self):
        hb_file = self.test_dir / "orphan_heartbeat.json"
        data = {
            "pid": 99999999,  # Dead PID
            "timestamp": time.time(),
            "iso_time": "2026-09-01T00:00:00Z",
        }
        hb_file.write_text(json.dumps(data), encoding="utf-8")

        res = self.sentinel.verify_heartbeat(hb_file, stall_timeout=60.0)
        self.assertTrue(res["stalled"])
        self.assertEqual(res["status"], "ORPHANED_PROCESS_DEAD")


if __name__ == "__main__":
    unittest.main()
