#!/usr/bin/env python3
"""Targeted unit tests for Mission 126B YouTube Pre-Publish Readiness Check."""

import hashlib
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestYouTubePrePublishReadinessMission126B(unittest.TestCase):
    def test_golden_trophy_package_integrity(self):
        pkg_dir = REPO_ROOT / "runtime" / "content" / "golden_trophy_short"
        media_path = pkg_dir / "render.mp4"
        qc_path = pkg_dir / "qc_report.json"
        pub_path = pkg_dir / "publish_package.json"

        self.assertTrue(media_path.is_file(), "Golden Trophy MP4 master missing")
        self.assertTrue(qc_path.is_file(), "Golden Trophy QC report missing")
        self.assertTrue(pub_path.is_file(), "Golden Trophy publish package missing")

        with open(media_path, "rb") as f:
            calculated_sha = hashlib.sha256(f.read()).hexdigest()

        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        pub = json.loads(pub_path.read_text(encoding="utf-8"))

        self.assertEqual(qc.get("verdict"), "PASS")
        self.assertEqual(qc.get("source_hash"), calculated_sha)
        pub_state = pub.get("publication_state") or pub.get("status")
        self.assertIn(pub_state, {"READY_FOR_PUBLICATION", "COMPLETE_READY_FOR_REVIEW"})
        self.assertFalse(pub.get("publication_authorized", True), "Publication must not be pre-authorized without human approval")

    def test_mystery_box_package_integrity(self):
        pkg_dir = REPO_ROOT / "runtime" / "content" / "mystery_box_short"
        media_path = pkg_dir / "fruitki_strawberry_mystery_box.mp4"
        qc_path = pkg_dir / "qc_report.json"
        pub_path = pkg_dir / "publish_package.json"

        self.assertTrue(media_path.is_file(), "Mystery Box MP4 master missing")
        self.assertTrue(qc_path.is_file(), "Mystery Box QC report missing")
        self.assertTrue(pub_path.is_file(), "Mystery Box publish package missing")

        with open(media_path, "rb") as f:
            calculated_sha = hashlib.sha256(f.read()).hexdigest()

        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        pub = json.loads(pub_path.read_text(encoding="utf-8"))

        self.assertEqual(qc.get("verdict"), "PASS")
        self.assertEqual(qc.get("source_hash"), calculated_sha)
        pub_state = pub.get("publication_state") or pub.get("status")
        self.assertIn(pub_state, {"READY_FOR_PUBLICATION", "COMPLETE_READY_FOR_REVIEW"})
        self.assertFalse(pub.get("publication_authorized", True), "Publication must not be pre-authorized without human approval")

    def test_youtube_pilot_scripts_exist(self):
        pilot_dir = REPO_ROOT.parent / "2026-Projektzentrale" / "02-YouTube-Operations" / "youtube-oauth-pilot"
        self.assertTrue(pilot_dir.is_dir(), "YouTube pilot directory missing")
        upload_script = pilot_dir / "youtube_upload.py"
        self.assertTrue(upload_script.is_file(), "youtube_upload.py script missing")


if __name__ == "__main__":
    unittest.main()
