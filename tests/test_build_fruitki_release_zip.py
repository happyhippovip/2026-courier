#!/usr/bin/env python3
"""Test suite for FruitKIReleaseBuilder."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_fruitki_release_zip import FruitKIReleaseBuilder


class TestFruitKIReleaseBuilder(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="fruitki_release_test_"))
        pack_dir = self.test_dir / "events" / "digital-assets" / "fruitki_commercial_pack"
        pack_dir.mkdir(parents=True, exist_ok=True)

        (pack_dir / "bundle_manifest.json").write_text(json.dumps({"total_character_rigs": 12}))
        (pack_dir / "COMMERCIAL_LICENSE_AGREEMENT.md").write_text("# License Agreement")
        (pack_dir / "STORE_LISTING_SPECIFICATION.md").write_text("# Store Listing")

        self.builder = FruitKIReleaseBuilder(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_build_release_archive(self):
        """Builds valid .zip archive with bundle manifest, license, and README."""
        res = self.builder.build_release_archive()
        self.assertEqual(res["status"], "RELEASE_ARCHIVE_BUILT")
        self.assertEqual(res["capital_spent_eur"], 0.0)

        zip_path = self.test_dir / res["archive"]
        self.assertTrue(zip_path.exists())

        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.namelist()
            self.assertIn("bundle_manifest.json", files)
            self.assertIn("COMMERCIAL_LICENSE_AGREEMENT.md", files)
            self.assertIn("STORE_LISTING_SPECIFICATION.md", files)
            self.assertIn("README.md", files)


if __name__ == "__main__":
    unittest.main()
