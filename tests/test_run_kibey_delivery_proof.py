#!/usr/bin/env python3
"""Test suite for run_kibey_delivery_proof."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_kibey_delivery_proof import KibeyDeliveryEngine


class TestRunKibeyDeliveryProof(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="kibey_delivery_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_kibey_dogfood_delivery_proof(self):
        """Verifies end-to-end buyer task execution and delivery ZIP generation."""
        engine = KibeyDeliveryEngine(repo_dir=self.test_dir)
        res = engine.execute_dogfood_delivery_proof()
        self.assertEqual(res["status"], "KIBEY_DELIVERY_PROOF_READY")
        self.assertTrue(res["ready_for_immediate_fulfillment"])
        self.assertEqual(res["capital_spent_eur"], 0.0)

        dist_zip = self.test_dir / res["archive_path"]
        self.assertTrue(dist_zip.exists())
        self.assertGreater(dist_zip.stat().st_size, 500)


if __name__ == "__main__":
    unittest.main()
