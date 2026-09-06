#!/usr/bin/env python3
"""Test suite for DossierBatchGenerator."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_content_transformation_dossiers import DossierBatchGenerator


class TestDossierBatchGenerator(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dossier_test_"))
        self.generator = DossierBatchGenerator(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_generate_prospect_dossiers(self):
        """Generates pre-transformed deliverable dossiers for CP-01 and CP-02."""
        res = self.generator.generate_prospect_dossiers()
        self.assertEqual(res["status"], "DOSSIERS_GENERATED")
        self.assertEqual(res["total_dossiers"], 2)
        self.assertEqual(res["capital_spent_eur"], 0.0)

        manifest_path = self.test_dir / res["manifest"]
        self.assertTrue(manifest_path.exists())
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("CP-01", data["prospect_dossiers"])
        self.assertIn("CP-02", data["prospect_dossiers"])


if __name__ == "__main__":
    unittest.main()
