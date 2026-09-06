#!/usr/bin/env python3
"""Focused Acceptance Test Suite for Disaster Recovery Bundle Sync (Mission Infinite Life).

Verifies:
1. Creation of valid tar.gz snapshot bundle archives
2. Integrity manifest generation with cryptographic sha256 digests
3. Verification of bundle manifest against extracted contents
"""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.disaster_recovery_bundle_sync import DisasterRecoveryBundleSync, compute_file_sha256


class TestDisasterRecoveryBundleSync(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dr_bundle_test_"))
        self.events_dir = self.test_dir / "events"
        self.brain_dir = self.events_dir / "chief-brain"
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        (self.brain_dir / "memories.json").write_text(json.dumps({"memories": ["test"]}), encoding="utf-8")

        self.syncer = DisasterRecoveryBundleSync(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_create_snapshot_bundle_and_verify_manifest(self):
        """Creates snapshot bundle tar.gz and verifies integrity manifest contents."""
        tar_path, digest, manifest = self.syncer.create_snapshot_bundle("test-bundle-01")

        self.assertTrue(tar_path.exists())
        self.assertTrue(tar_path.stat().st_size > 0)
        self.assertEqual(manifest["bundle_id"], "test-bundle-01")
        self.assertEqual(manifest["autonomous_spend_limit_eur"], 0.0)
        self.assertIn("events/chief-brain/memories.json", manifest["files_included"])

        # Check tarball readability and verify method
        with tarfile.open(tar_path, "r:gz") as tar:
            names = tar.getnames()
            self.assertIn("events/chief-brain/memories.json", names)

        manifest_file = self.test_dir / "events" / "disaster-recovery" / "bundles" / "test-bundle-01_manifest.json"
        self.assertTrue(manifest_file.exists())
        ok, msg = self.syncer.verify_snapshot_bundle(tar_path, manifest_file)
        self.assertTrue(ok)
        self.assertEqual(msg, "VERIFIED")

    def test_02_compute_file_sha256(self):
        """Validates sha256 checksum computation."""
        test_file = self.test_dir / "sample.txt"
        test_file.write_text("hello-world-dr-test", encoding="utf-8")
        h = compute_file_sha256(test_file)
        self.assertEqual(len(h), 64)


if __name__ == "__main__":
    unittest.main()
