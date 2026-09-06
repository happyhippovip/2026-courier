#!/usr/bin/env python3
"""Test suite for execute_two_google_capacities."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.execute_two_google_capacities import execute_two_google_capacities


class TestExecuteTwoGoogleCapacities(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="exec_google_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_two_capacity_parallel_execution(self):
        """Verifies concurrent execution across GOOGLE_01 and GOOGLE_02 with temporal overlap."""
        res = execute_two_google_capacities(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "REAL_MULTI_ACCOUNT_EXECUTION_PASS")
        self.assertEqual(res["live_executable"], 2)
        self.assertEqual(res["auth_required"], 5)
        self.assertEqual(res["account_a"], "GOOGLE_01")
        self.assertEqual(res["account_b"], "GOOGLE_02")
        self.assertTrue(res["real_provider_a"])
        self.assertTrue(res["real_provider_b"])
        self.assertGreater(res["overlap_seconds"], 0.0)
        self.assertEqual(res["new_spend_eur"], 0.0)
        self.assertEqual(res["weiter_count"], 0)


if __name__ == "__main__":
    unittest.main()
