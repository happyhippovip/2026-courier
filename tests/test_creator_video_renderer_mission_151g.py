#!/usr/bin/env python3
"""Unit tests for Autonomous Creator Video Production Pipeline (Mission 151G)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_CONTENT_DIR = COURIER_DIR / "runtime" / "content"


class TestCreatorVideoRendererMission151G(unittest.TestCase):
    """Test suite validating the 3 rendered packages and batch manifest."""

    def test_01_batch_manifest_structure_and_completeness(self):
        manifest_path = RUNTIME_CONTENT_DIR / "mission_151g_creator_batch" / "mission_151g_batch_manifest.json"
        self.assertTrue(manifest_path.is_file(), "Batch manifest must exist")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(data["mission_id"], "MISSION_151G")
        self.assertEqual(data["video_count"], 3)
        self.assertEqual(data["complete_count"], 3)
        self.assertEqual(data["incomplete_count"], 0)
        self.assertIn("VIDEO_A", data["best_video"])
        self.assertEqual(len(data["packages"]), 3)

    def test_02_video_a_package_invariants(self):
        pkg_dir = RUNTIME_CONTENT_DIR / "watermelon_super_bounce_short"
        self.assertTrue((pkg_dir / "render.mp4").is_file())
        self.assertTrue((pkg_dir / "qc_report.json").is_file())
        self.assertTrue((pkg_dir / "publish_package.json").is_file())
        self.assertTrue((pkg_dir / "render_metadata.json").is_file())

        pkg = json.loads((pkg_dir / "publish_package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["schema_version"], "2.2")
        self.assertEqual(pkg["publication_authorized"], False)
        self.assertEqual(pkg["upload_authorized"], False)
        self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")
        self.assertEqual(pkg["cost_eur"], 0.0)
        self.assertEqual(pkg["qc_status"], "PASS")
        self.assertIn("Melone", pkg["content_title"])

    def test_03_video_b_package_invariants(self):
        pkg_dir = RUNTIME_CONTENT_DIR / "banana_ninja_escape_short"
        self.assertTrue((pkg_dir / "render.mp4").is_file())
        self.assertTrue((pkg_dir / "qc_report.json").is_file())
        self.assertTrue((pkg_dir / "publish_package.json").is_file())
        self.assertTrue((pkg_dir / "render_metadata.json").is_file())

        pkg = json.loads((pkg_dir / "publish_package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["schema_version"], "2.2")
        self.assertEqual(pkg["publication_authorized"], False)
        self.assertEqual(pkg["upload_authorized"], False)
        self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")
        self.assertEqual(pkg["cost_eur"], 0.0)
        self.assertEqual(pkg["qc_status"], "PASS")
        self.assertIn("Banane", pkg["content_title"])

    def test_04_video_c_package_invariants(self):
        pkg_dir = RUNTIME_CONTENT_DIR / "disco_berry_dance_battle_short"
        self.assertTrue((pkg_dir / "render.mp4").is_file())
        self.assertTrue((pkg_dir / "qc_report.json").is_file())
        self.assertTrue((pkg_dir / "publish_package.json").is_file())
        self.assertTrue((pkg_dir / "render_metadata.json").is_file())

        pkg = json.loads((pkg_dir / "publish_package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["schema_version"], "2.2")
        self.assertEqual(pkg["publication_authorized"], False)
        self.assertEqual(pkg["upload_authorized"], False)
        self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")
        self.assertEqual(pkg["cost_eur"], 0.0)
        self.assertEqual(pkg["qc_status"], "PASS")
        self.assertIn("Tanz", pkg["content_title"])

    def test_05_technical_qc_reports_pass(self):
        for slug in ["watermelon_super_bounce_short", "banana_ninja_escape_short", "disco_berry_dance_battle_short"]:
            qc_file = RUNTIME_CONTENT_DIR / slug / "qc_report.json"
            qc = json.loads(qc_file.read_text(encoding="utf-8"))
            self.assertEqual(qc["verdict"], "PASS")
            self.assertEqual(qc["video"]["width"], 720)
            self.assertEqual(qc["video"]["height"], 1280)
            self.assertEqual(qc["video"]["codec_name"], "h264")
            self.assertTrue(qc["audio"]["present"])
            self.assertEqual(qc["duration_seconds"], 8.0)
            self.assertEqual(qc["publication_authorized"], False)

    def test_06_unique_sha256_hashes_across_all_packages(self):
        hashes = set()
        for slug in ["watermelon_super_bounce_short", "banana_ninja_escape_short", "disco_berry_dance_battle_short"]:
            pkg = json.loads((RUNTIME_CONTENT_DIR / slug / "publish_package.json").read_text(encoding="utf-8"))
            hashes.add(pkg["media_sha256"])
        self.assertEqual(len(hashes), 3, "All 3 rendered MP4s must have distinct SHA-256 hashes")


if __name__ == "__main__":
    unittest.main()
