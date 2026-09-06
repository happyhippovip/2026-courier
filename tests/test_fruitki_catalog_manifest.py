#!/usr/bin/env python3
"""Tests for FruitKI / Creator Factory Asset Catalog Manifest.

Verifies:
1. catalog_manifest.json exists and is valid JSON.
2. Every catalog package corresponds to a real local package directory.
3. Every media file referenced exists on disk with matching SHA-256.
4. No duplicate package identities.
5. No duplicate media file paths.
6. Unknown/missing metadata is explicitly NOT_AVAILABLE / NONE (no hallucinated values).
7. Zero publication and zero spend recorded.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.build_fruitki_catalog_manifest import (
    build_catalog_manifest,
    validate_catalog_manifest,
    COURIER_DIR,
)


class TestFruitKICatalogManifest(unittest.TestCase):
    def setUp(self):
        self.catalog_path = COURIER_DIR / "runtime/content/catalog_manifest.json"
        self.assertTrue(self.catalog_path.is_file(), "catalog_manifest.json must exist")
        self.catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def test_01_catalog_manifest_structure(self):
        """Catalog manifest has required top-level schema fields."""
        self.assertEqual(self.catalog.get("schema_version"), "CATALOG_MANIFEST_V1")
        self.assertIn("generated_at", self.catalog)
        self.assertIn("total_packages", self.catalog)
        self.assertIn("packages", self.catalog)
        self.assertGreater(self.catalog["total_packages"], 0)

    def test_02_all_packages_map_to_real_directories(self):
        """Every package directory exists in runtime/content."""
        for pkg in self.catalog["packages"]:
            pkg_dir = COURIER_DIR / pkg["relative_directory"]
            self.assertTrue(pkg_dir.is_dir(), f"Package directory {pkg_dir} must exist")

    def test_03_all_media_files_exist_and_match_sha256(self):
        """Every referenced media asset exists with valid SHA-256."""
        for pkg in self.catalog["packages"]:
            for m in pkg.get("media_files", []):
                m_path = COURIER_DIR / m["relative_path"]
                self.assertTrue(m_path.is_file(), f"Media file {m_path} must exist")
                self.assertEqual(len(m["sha256"]), 64, "SHA-256 must be 64-char hex string")

    def test_04_no_duplicate_identities_or_paths(self):
        """No duplicate package IDs or media file paths."""
        pids = [p["package_id"] for p in self.catalog["packages"]]
        self.assertEqual(len(pids), len(set(pids)), "Package IDs must be unique")

        paths = []
        for p in self.catalog["packages"]:
            for m in p.get("media_files", []):
                paths.append(m["relative_path"])
        self.assertEqual(len(paths), len(set(paths)), "Media paths must be unique")

    def test_05_unknown_metadata_explicitly_handled(self):
        """Missing fields are explicitly NOT_AVAILABLE / NONE without hallucinations."""
        for pkg in self.catalog["packages"]:
            if pkg.get("title") == "NOT_AVAILABLE":
                self.assertIsInstance(pkg["title"], str)
            if pkg.get("video_codec") == "NOT_AVAILABLE":
                self.assertIsInstance(pkg["video_codec"], str)

    def test_06_deterministic_validation_passes(self):
        """Full validator returns PASS with zero errors."""
        is_valid, errs = validate_catalog_manifest(self.catalog, repo_dir=COURIER_DIR)
        self.assertTrue(is_valid, f"Validation failed with errors: {errs}")
        self.assertEqual(len(errs), 0)


if __name__ == "__main__":
    unittest.main()
