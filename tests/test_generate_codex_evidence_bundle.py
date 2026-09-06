#!/usr/bin/env python3
"""Test suite for generate_codex_evidence_bundle."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generate_codex_evidence_bundle import generate_autonomy_evidence_bundle


class TestGenerateCodexEvidenceBundle(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="bundle_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_bundle_generation(self):
        """Verifies sanitized evidence bundle is generated with zero secrets and passing oracles."""
        res = generate_autonomy_evidence_bundle(repo_dir=self.test_dir)
        self.assertEqual(res["status"], "BUNDLE_GENERATED")
        self.assertEqual(res["oracle_results"]["black_box"], "PASS")
        self.assertEqual(res["oracle_results"]["crash_restart"], "PASS")

        bundle_path = self.test_dir / "events" / "reviews" / "AUTONOMY_EVIDENCE_BUNDLE.json"
        self.assertTrue(bundle_path.exists())
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.assertIn("runtime_identity", data)
        self.assertIn("black_box_continuity_oracle", data)
        self.assertIn("crash_restart_oracle", data)
        self.assertEqual(data["invariants_verified"]["unauthorized_spend_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
