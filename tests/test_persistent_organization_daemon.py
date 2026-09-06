#!/usr/bin/env python3
"""Test suite for PersistentOrganizationDaemon."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.persistent_organization_daemon import PersistentOrganizationDaemon


class TestPersistentOrganizationDaemon(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="daemon_test_"))
        self.daemon = PersistentOrganizationDaemon(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_single_instance_lock_acquisition(self):
        """Verifies single instance lock acquisition and second instance rejection."""
        acquired = self.daemon.acquire_single_instance_lock()
        self.assertTrue(acquired)

        # Second instance should fail
        daemon2 = PersistentOrganizationDaemon(repo_dir=self.test_dir)
        acquired2 = daemon2.acquire_single_instance_lock()
        self.assertFalse(acquired2)

    def test_02_heartbeat_emission(self):
        """Emits atomic heartbeat and verifies content on disk."""
        self.daemon.emit_heartbeat(status="TEST_RUNNING", next_action="TEST_ACTION")
        hb_file = self.test_dir / "events" / "runtime-state" / "daemon_heartbeat.json"
        self.assertTrue(hb_file.exists())
        data = json.loads(hb_file.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "TEST_RUNNING")
        self.assertEqual(data["next_action"], "TEST_ACTION")
        self.assertTrue(data["process_alive"])
        self.assertFalse(data["human_weiter_required"])

    def test_03_safe_idle_cycles_bounded(self):
        """Runs bounded cycles in SAFE_IDLE without exiting abruptly."""
        self.daemon.run_loop(max_cycles=2, idle_sleep_seconds=0.01)
        self.assertEqual(self.daemon.cycle_count, 2)


if __name__ == "__main__":
    unittest.main()
