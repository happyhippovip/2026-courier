#!/usr/bin/env python3
"""Test suite for Live Fabric Execution Proof."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_live_fabric_execution_proof import run_live_execution_proof


class TestRunLiveFabricExecutionProof(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="fabric_live_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_run_live_execution_proof(self):
        """Proves complete live flow: route -> claim -> execute -> envelope -> release -> controller decision."""
        res = run_live_execution_proof(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "LIVE_RUNTIME_VERIFIED")
        self.assertEqual(res["execution_type"], "LIVE_RUNTIME_VERIFIED")
        self.assertFalse(res["human_weiter_required"])
        self.assertEqual(res["human_copy_paste_count"], 0)
        self.assertIsNotNone(res["controller_decision_id"])


if __name__ == "__main__":
    unittest.main()
