#!/usr/bin/env python3
"""Unit tests for Mission 155G 30-Minute Creator Factory Production Shift."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
CONTENT_DIR = RUNTIME_DIR / "content"
AUTONOMY_DIR = RUNTIME_DIR / "autonomy"
ASSETS_DIR = RUNTIME_DIR / "assets" / "creator_library"
BATCH_DIR = CONTENT_DIR / "mission_155g_creator_batch"

SLUGS = [
    "mystery_portal_apple_v2_short",
    "watermelon_super_bounce_v2_short",
    "banana_skateboard_loop_v2_short",
    "dragonfruit_volcano_eruption_short",
    "strawberry_quantum_teleport_short",
]


class TestCreatorProductionShiftMission155G(unittest.TestCase):
    """Test suite validating the 30-minute shift lease, 1080p outputs, assets, and safety."""

    def test_01_lease_invariants(self):
        lease_path = AUTONOMY_DIR / "mission_155g_30min_lease.json"
        self.assertTrue(lease_path.is_file(), "Shift lease file must exist")
        data = json.loads(lease_path.read_text(encoding="utf-8"))

        self.assertEqual(data["mission_id"], "155G")
        self.assertEqual(data["target_duration_seconds"], 1800)
        self.assertEqual(data["status"], "COMPLETE")
        for cp in ["CHECKPOINT_05", "CHECKPOINT_10", "CHECKPOINT_15", "CHECKPOINT_20", "CHECKPOINT_25", "CHECKPOINT_30"]:
            self.assertIn(cp, data["checkpoints"], f"{cp} must be recorded in lease")

    def test_02_all_upgraded_and_new_packages_exist(self):
        for slug in SLUGS:
            pkg_dir = CONTENT_DIR / slug
            self.assertTrue((pkg_dir / "render.mp4").is_file(), f"{slug} render.mp4 missing")
            self.assertTrue((pkg_dir / "qc_report.json").is_file(), f"{slug} qc_report.json missing")
            self.assertTrue((pkg_dir / "publish_package.json").is_file(), f"{slug} publish_package.json missing")
            self.assertTrue((pkg_dir / "render_metadata.json").is_file(), f"{slug} render_metadata.json missing")
            self.assertTrue((pkg_dir / "qc_keyframes" / "opening.png").is_file(), f"{slug} opening keyframe missing")
            self.assertTrue((pkg_dir / "qc_keyframes" / "middle.png").is_file(), f"{slug} middle keyframe missing")
            self.assertTrue((pkg_dir / "qc_keyframes" / "payoff.png").is_file(), f"{slug} payoff keyframe missing")

    def test_03_resolution_is_native_1080p_fhd(self):
        for slug in SLUGS:
            qc_file = CONTENT_DIR / slug / "qc_report.json"
            qc = json.loads(qc_file.read_text(encoding="utf-8"))
            self.assertEqual(qc["verdict"], "PASS")
            self.assertEqual(qc["visual_verdict"], "VISUAL_PASS")
            self.assertEqual(qc["video"]["width"], 1080)
            self.assertEqual(qc["video"]["height"], 1920)
            self.assertEqual(qc["video"]["codec_name"], "h264")
            self.assertTrue(qc["audio"]["present"])
            self.assertEqual(qc["duration_seconds"], 8.0)

    def test_04_publication_and_audience_safety(self):
        for slug in SLUGS:
            pkg_file = CONTENT_DIR / slug / "publish_package.json"
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            self.assertEqual(pkg["schema_version"], "2.2")
            self.assertEqual(pkg["publication_authorized"], False)
            self.assertEqual(pkg["upload_authorized"], False)
            self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")
            self.assertEqual(pkg["cost_eur"], 0.0)

    def test_05_reusable_assets_manifest_and_files(self):
        asset_manifest_file = ASSETS_DIR / "asset_manifest.json"
        self.assertTrue(asset_manifest_file.is_file())
        data = json.loads(asset_manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(data["total_assets"], 7)
        for exp in data["expression_pack"]:
            self.assertTrue((ASSETS_DIR / "expression_pack" / exp).is_file())
        self.assertTrue((ASSETS_DIR / "lighting_presets.json").is_file())

    def test_06_master_contact_sheet_and_manifest(self):
        self.assertTrue((BATCH_DIR / "mission_155g_master_contact_sheet.png").is_file())
        self.assertTrue((BATCH_DIR / "mission_155g_batch_manifest.json").is_file())
        manifest = json.loads((BATCH_DIR / "mission_155g_batch_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mission_id"], "MISSION_155G")
        self.assertEqual(manifest["total_videos_completed"], 5)
        self.assertEqual(manifest["resolution_tier"], "1080x1920_NATIVE_FHD")


if __name__ == "__main__":
    unittest.main()
