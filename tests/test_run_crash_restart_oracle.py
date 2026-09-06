#!/usr/bin/env python3
"""Test suite for Crash & Restart Acceptance Oracle."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_crash_restart_oracle import run_crash_restart_oracle


class TestRunCrashRestartOracle(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="crash_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_crash_restart_oracle_recovery(self):
        """Verifies claim boundary recovery, fencing generation monotonicity, and result idempotency."""
        res = run_crash_restart_oracle(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["crash_restart_oracle"], "PASS")
        self.assertEqual(res["claim_boundary_recovery"], "VERIFIED_RECLAIMED")
        self.assertTrue(res["fencing_generation_monotonic"])
        self.assertTrue(res["result_boundary_idempotent"])
        self.assertEqual(res["duplicate_side_effects"], 0)


if __name__ == "__main__":
    unittest.main()
