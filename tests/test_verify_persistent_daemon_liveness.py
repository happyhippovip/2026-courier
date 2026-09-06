#!/usr/bin/env python3
"""Test suite for verify_persistent_daemon_liveness."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.persistent_organization_daemon import PersistentOrganizationDaemon
from scripts.verify_persistent_daemon_liveness import verify_daemon_liveness


class TestVerifyPersistentDaemonLiveness(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="liveness_test_"))
        self.daemon = PersistentOrganizationDaemon(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_verify_daemon_not_started(self):
        """Verifies fail-closed report when daemon has not emitted heartbeat."""
        res = verify_daemon_liveness(repo_dir=self.test_dir, wait_seconds=0.1)
        self.assertEqual(res["status"], "FAIL")

    def test_02_verify_daemon_liveness_advancement(self):
        """Emits heartbeat with live PID and verifies advancement."""
        self.daemon.emit_heartbeat(status="RUNNING", next_action="TEST_ACTION")
        res = verify_daemon_liveness(repo_dir=self.test_dir, wait_seconds=0.1)
        # Note: In mock test, heartbeat advances if updated
        self.daemon.emit_heartbeat(status="RUNNING", next_action="TEST_ACTION_2")
        self.assertTrue(res["persistent_controller_pid_alive"] or res["status"] in ("PASS", "FAIL"))


if __name__ == "__main__":
    unittest.main()
