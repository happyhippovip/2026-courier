#!/usr/bin/env python3
"""Test suite for FruitKIDistributionPackager."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generate_fruitki_distribution_pack import FruitKIDistributionPackager


class TestFruitKIDistributionPackager(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="fruitki_pack_test_"))
        self.packager = FruitKIDistributionPackager(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_generate_distribution_bundle(self):
        """Generates distribution bundle manifest and commercial license."""
        res = self.packager.generate_distribution_bundle()
        self.assertEqual(res["status"], "DISTRIBUTION_PACK_GENERATED")
        self.assertEqual(res["capital_spent_eur"], 0.0)

        manifest_path = self.test_dir / res["manifest"]
        license_path = self.test_dir / res["license"]

        self.assertTrue(manifest_path.exists())
        self.assertTrue(license_path.exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["total_character_rigs"], 12)
        self.assertIn("Godot 4.x", manifest["engine_compatibility"])


if __name__ == "__main__":
    unittest.main()
