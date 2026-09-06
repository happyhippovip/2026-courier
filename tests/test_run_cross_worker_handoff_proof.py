#!/usr/bin/env python3
"""Test suite for Cross-Worker Autonomous Handoff & Continuation Proof."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_cross_worker_handoff_proof import run_cross_worker_handoff_proof


class TestRunCrossWorkerHandoffProof(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cross_worker_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_cross_worker_handoff_chain(self):
        """Verifies multi-worker loop (CLI1 -> Antigravity -> CLI1) with zero WEITER and zero copy/paste."""
        res = run_cross_worker_handoff_proof(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "AUTONOMOUS_MULTI_WORKER_LOOP_LIVE_VERIFIED")
        self.assertEqual(len(res["handoff_steps"]), 3)
        self.assertEqual(res["cross_worker_handoff"], "PASS")
        self.assertEqual(res["result_to_next_task"], "PASS")
        self.assertEqual(res["human_copy_paste_count"], 0)
        self.assertEqual(res["weiter_count"], 0)


if __name__ == "__main__":
    unittest.main()
