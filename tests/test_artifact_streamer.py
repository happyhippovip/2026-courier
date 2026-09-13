"""
test_artifact_streamer.py - Test suite for TASK-WIN-62
Certifies Cross-Host Remote Artifact Streaming & Cryptographic Diff Sync:
- Local manifest calculation (SHA-256 and size)
- Delta diff computation (to_download, to_upload, identical)
- Remote manifest retrieval from /api/courier/sync/artifacts/manifest
- Streaming artifact download with inline SHA-256 integrity verification
- Idempotent delta synchronization (no redundant re-downloads)
- Path traversal confinement (strict fail-closed 403 on traversal attempt)
- Strict 0.00 EUR spend firewall validation
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
import urllib.request
import urllib.error

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
BASE_URL = "http://127.0.0.1:8088"

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.sync.artifact_streamer import ArtifactStreamer
from courier.tests.server_fixture import CourierServerTestCase

class TestArtifactStreamer(CourierServerTestCase):
    def setUp(self):
        self.streamer = ArtifactStreamer(peer_url=self.base_url)
        self.temp_dir = tempfile.mkdtemp(prefix="test_artifact_streamer_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_local_manifest_scanning(self):
        """Verify scan_local_manifest calculates valid SHA-256 hashes and sizes."""
        f1 = os.path.join(self.temp_dir, "test1.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("HELLO_COURIER_ARTIFACT_STREAM")
        
        subdir = os.path.join(self.temp_dir, "nested")
        os.makedirs(subdir, exist_ok=True)
        f2 = os.path.join(subdir, "test2.bin")
        with open(f2, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04")

        manifest = ArtifactStreamer.scan_local_manifest(self.temp_dir)
        self.assertEqual(len(manifest), 2)
        self.assertIn("test1.txt", manifest)
        self.assertIn("nested/test2.bin", manifest)
        self.assertEqual(len(manifest["test1.txt"]["sha256"]), 64)
        self.assertEqual(manifest["nested/test2.bin"]["size_bytes"], 5)

    def test_02_diff_calculation_logic(self):
        """Verify compute_diff accurately separates new, modified, and identical artifacts."""
        local_m = {
            "file_identical.txt": {"sha256": "aaaa" * 16, "size_bytes": 10},
            "file_modified.txt": {"sha256": "1111" * 16, "size_bytes": 10},
            "file_local_only.txt": {"sha256": "2222" * 16, "size_bytes": 10}
        }
        remote_m = {
            "file_identical.txt": {"sha256": "aaaa" * 16, "size_bytes": 10},
            "file_modified.txt": {"sha256": "9999" * 16, "size_bytes": 15},
            "file_remote_only.txt": {"sha256": "3333" * 16, "size_bytes": 20}
        }
        diff = ArtifactStreamer.compute_diff(local_m, remote_m)
        self.assertEqual(diff["identical"], ["file_identical.txt"])
        self.assertEqual(sorted(diff["to_download"]), ["file_modified.txt", "file_remote_only.txt"])
        self.assertEqual(diff["to_upload"], ["file_local_only.txt"])

    def test_03_remote_manifest_and_streaming_download(self):
        """Verify remote manifest query and streaming download with header checksum verification."""
        manifest = self.streamer.fetch_remote_manifest("distribution_ready")
        self.assertGreater(len(manifest), 0, "Remote manifest must contain distribution assets")
        
        sample_key = "agent_control_plane/DISTRIBUTION_MANIFEST.json"
        self.assertIn(sample_key, manifest)
        
        ok, out_path, sha256 = self.streamer.stream_download("distribution_ready", sample_key, self.temp_dir)
        self.assertTrue(ok, f"Streaming download failed: {sha256}")
        self.assertTrue(os.path.exists(out_path))
        self.assertEqual(sha256, manifest[sample_key]["sha256"])

    def test_04_path_traversal_confinement(self):
        """Verify path traversal attempts are rejected fail-closed with HTTP 403."""
        traversal_url = f"{self.base_url}/api/courier/sync/artifacts/download?scope=distribution_ready&file=../../../../Windows/win.ini"
        req = urllib.request.Request(traversal_url)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 403)

    def test_05_idempotent_delta_sync(self):
        """Verify sync_scope downloads missing files, then subsequent sync skips identical files."""
        # Create a small dedicated test scope directory inside evidence
        test_scope_dir = os.path.join(WORKSPACE_ROOT, "evidence", f"test_scope_{int(time.time())}")
        os.makedirs(test_scope_dir, exist_ok=True)
        try:
            with open(os.path.join(test_scope_dir, "sample.txt"), "w") as f:
                f.write("SAMPLE_ARTIFACT_DATA")

            # First sync: downloads sample.txt into temp_dir
            res1 = self.streamer.sync_scope("evidence", self.temp_dir)
            self.assertTrue(res1.get("success"), f"Sync 1 failed: {res1}")
            self.assertGreaterEqual(res1.get("downloaded_count", 0), 1)

            # Second sync: identical, zero downloads
            res2 = self.streamer.sync_scope("evidence", self.temp_dir)
            self.assertTrue(res2.get("success"), f"Sync 2 failed: {res2}")
            self.assertEqual(res2.get("downloaded_count"), 0)
            self.assertGreaterEqual(res2.get("identical_count", 0), 1)
        finally:
            shutil.rmtree(test_scope_dir, ignore_errors=True)

    def test_06_zero_spend_invariant(self):
        """Verify all artifact streaming and sync operations preserve 0.00 EUR spend."""
        res = self.streamer.sync_scope("distribution_ready", self.temp_dir)
        self.assertEqual(float(res.get("spend_eur", 0.0)), 0.0)

if __name__ == "__main__":
    unittest.main()
