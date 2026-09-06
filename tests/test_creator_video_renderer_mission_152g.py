#!/usr/bin/env python3
"""Unit tests for Extended Creator Video Production Pipeline (Mission 152G)."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_CONTENT_DIR = COURIER_DIR / "runtime" / "content"
BATCH_DIR = RUNTIME_CONTENT_DIR / "mission_152g_creator_batch"

SLUGS = [
    "mystery_portal_apple_short",
    "cherry_catapult_target_short",
    "micro_fruit_grand_prix_short",
    "giant_pineapple_anvil_short",
    "wrong_potion_lemon_short",
    "three_door_mystery_vault_short",
    "orange_laser_heist_short",
    "banana_skateboard_loop_short",
    "watermelon_ice_crush_short",
    "kiwi_time_freeze_stopwatch_short",
]


class TestCreatorVideoRendererMission152G(unittest.TestCase):
    """Test suite validating all 10 rendered packages, safety invariants, and manifest."""

    def test_01_manifest_counts_and_targets(self):
        manifest_path = BATCH_DIR / "mission_152g_batch_manifest.json"
        self.assertTrue(manifest_path.is_file(), "Mission 152G batch manifest must exist")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(data["mission_id"], "MISSION_152G")
        self.assertEqual(data["target_count"], 8)
        self.assertEqual(data["stretch_target_count"], 10)
        self.assertEqual(data["videos_attempted"], 10)
        self.assertEqual(data["videos_completed"], 10)
        self.assertEqual(data["videos_incomplete"], 0)
        self.assertEqual(data["pipeline_stability"], "STABLE")
        self.assertGreater(data["total_output_bytes"], 1_000_000)
        self.assertEqual(len(data["packages"]), 10)

    def test_02_all_10_packages_exist_and_conform_schema(self):
        for slug in SLUGS:
            pkg_dir = RUNTIME_CONTENT_DIR / slug
            self.assertTrue((pkg_dir / "render.mp4").is_file(), f"{slug} render.mp4 missing")
            self.assertTrue((pkg_dir / "qc_report.json").is_file(), f"{slug} qc_report.json missing")
            self.assertTrue((pkg_dir / "publish_package.json").is_file(), f"{slug} publish_package.json missing")
            self.assertTrue((pkg_dir / "render_metadata.json").is_file(), f"{slug} render_metadata.json missing")

            pkg = json.loads((pkg_dir / "publish_package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg["schema_version"], "2.2")
            self.assertEqual(pkg["publication_authorized"], False)
            self.assertEqual(pkg["upload_authorized"], False)
            self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")
            self.assertEqual(pkg["cost_eur"], 0.0)
            self.assertEqual(pkg["qc_status"], "PASS")

    def test_03_all_qc_reports_are_pass(self):
        for slug in SLUGS:
            qc_file = RUNTIME_CONTENT_DIR / slug / "qc_report.json"
            qc = json.loads(qc_file.read_text(encoding="utf-8"))
            self.assertEqual(qc["verdict"], "PASS")
            self.assertEqual(qc["video"]["width"], 720)
            self.assertEqual(qc["video"]["height"], 1280)
            self.assertEqual(qc["video"]["codec_name"], "h264")
            self.assertTrue(qc["audio"]["present"])
            self.assertEqual(qc["duration_seconds"], 8.0)
            self.assertEqual(qc["publication_authorized"], False)

    def test_04_sha256_uniqueness_and_integrity(self):
        seen_hashes = set()
        for slug in SLUGS:
            mp4_path = RUNTIME_CONTENT_DIR / slug / "render.mp4"
            hasher = hashlib.sha256()
            hasher.update(mp4_path.read_bytes())
            actual_sha = hasher.hexdigest()

            pkg = json.loads((RUNTIME_CONTENT_DIR / slug / "publish_package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg["media_sha256"], actual_sha)
            seen_hashes.add(actual_sha)

        self.assertEqual(len(seen_hashes), 10, "All 10 MP4s must have unique SHA-256 digests")

    def test_05_future_backlog_seeds_present(self):
        manifest_path = BATCH_DIR / "mission_152g_batch_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        seeds = data.get("future_backlog_seeds", [])
        self.assertEqual(len(seeds), 15, "Manifest must contain 15 future concept seeds")
        for s in seeds:
            self.assertIn("title", s)
            self.assertIn("concept", s)
            self.assertIn("hook", s)
            self.assertIn("mechanic", s)
            self.assertIn("difficulty", s)

    def test_06_contact_sheet_exists(self):
        contact_sheet = BATCH_DIR / "mission_152g_contact_sheet.png"
        self.assertTrue(contact_sheet.is_file(), "Contact sheet must exist")
        self.assertGreater(contact_sheet.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
