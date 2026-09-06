#!/usr/bin/env python3
"""Test suite for GoogleCapacityFabricManager and Multi-Account Parallel Execution."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.google_capacity_fabric_manager import (
    GoogleAuthState,
    GoogleAvailability,
    GoogleCapacityFabricManager,
)
from scripts.run_multi_account_parallel_proof import run_multi_account_parallel_proof


class TestGoogleCapacityFabricManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="google_cap_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_seven_account_pool_initialization(self):
        """Verifies 7 authorized accounts initialized with total acquisition cost of 20 EUR."""
        mgr = GoogleCapacityFabricManager(repo_dir=self.test_dir)
        self.assertEqual(len(mgr.pool), 7)
        self.assertEqual(sum(a.acquisition_cost_eur for a in mgr.pool.values()), 20.0)

        metrics = mgr.update_productivity_metrics()
        self.assertEqual(metrics["authorized_google_capacity"], 7)
        self.assertEqual(metrics["available_google_capacity"], 7)
        self.assertEqual(metrics["marginal_spend_eur"], 0.0)

    def test_02_parallel_execution_proof(self):
        """Verifies two non-conflicting tasks execute in parallel without scope collision."""
        res = run_multi_account_parallel_proof(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "REAL_PARALLEL_EXECUTION_PASS")
        self.assertEqual(res["multi_account_fabric_live"], "PASS")
        self.assertFalse(res["scope_collision_detected"])
        self.assertEqual(res["marginal_spend_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
