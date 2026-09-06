#!/usr/bin/env python3
"""Test suite for run_real_multi_capacity_execution."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_real_multi_capacity_execution import run_real_multi_capacity_execution


class TestRunRealMultiCapacityExecution(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="multi_cap_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_real_parallel_execution(self):
        """Verifies concurrent execution across GOOGLE_01 and GOOGLE_02 with temporal overlap."""
        res = run_real_multi_capacity_execution(repo_dir=self.test_dir)
        self.assertEqual(res["real_parallel_execution"], "PASS")
        self.assertEqual(res["account_alias_a"], "GOOGLE_01")
        self.assertEqual(res["account_alias_b"], "GOOGLE_02")
        self.assertGreater(res["overlap_seconds"], 0.0)
        self.assertEqual(res["new_spend_eur"], 0.0)
        self.assertEqual(res["human_copy_paste_count"], 0)
        self.assertEqual(res["weiter_count"], 0)


if __name__ == "__main__":
    unittest.main()
