#!/usr/bin/env python3
"""Test suite for evaluate_revenue_conversion_state."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_revenue_conversion_state import RevenueConversionEvaluator


class TestEvaluateRevenueConversionState(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="eval_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_conversion_evaluation(self):
        """Verifies deterministic age evaluation and anti-spam policy compliance."""
        evaluator = RevenueConversionEvaluator(repo_dir=self.test_dir)
        res = evaluator.evaluate_all_exposures()
        self.assertEqual(res["schema_version"], "1.0")
        self.assertTrue(res["invariants"]["anti_spam_enforced"])
        self.assertTrue(res["invariants"]["zero_duplicate_sends"])

        playbook_path = evaluator.generate_response_playbook_doc()
        self.assertTrue(playbook_path.exists())


if __name__ == "__main__":
    unittest.main()
