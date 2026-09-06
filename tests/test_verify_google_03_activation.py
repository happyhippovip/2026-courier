#!/usr/bin/env python3
"""Test suite for verify_google_03_activation."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.verify_google_03_activation import run_google_03_followup_assets


class TestGoogle03Activation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="google03_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_google_03_activation_and_followup_assets(self):
        """Verifies GOOGLE_03 execution and 3 high-value follow-up assets."""
        res = run_google_03_followup_assets(repo_dir=self.test_dir)
        self.assertEqual(res["account_alias"], "GOOGLE_03")
        self.assertEqual(res["real_provider_execution"], "PASS")
        self.assertEqual(res["spend_eur"], 0.0)
        self.assertEqual(len(res["output"]), 3)
        self.assertIn("P-01", res["output"])
        self.assertIn("P-AUDIT-02", res["output"])
        self.assertIn("P-KIBEY-02", res["output"])


if __name__ == "__main__":
    unittest.main()
