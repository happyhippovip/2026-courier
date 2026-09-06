#!/usr/bin/env python3
"""Test suite for Codex Black-Box Continuity Oracle."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_codex_black_box_oracle import run_codex_black_box_oracle


class TestRunCodexBlackBoxOracle(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="codex_oracle_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_codex_black_box_continuity(self):
        """Verifies end-to-end black box continuity across CLI1 and Gemini Brain Bridge."""
        res = run_codex_black_box_oracle(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["black_box_continuity_oracle"], "PASS")
        self.assertEqual(len(res["evidence_chain"]), 2)
        self.assertEqual(res["human_relay_count"], 0)
        self.assertEqual(res["weiter_count"], 0)
        self.assertEqual(res["duplicate_side_effects"], 0)


if __name__ == "__main__":
    unittest.main()
