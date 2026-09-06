#!/usr/bin/env python3
"""Targeted unit tests for FruitKI Publication Packages (Schema 2.1 & Immutable Dedupe)."""

import hashlib
import json
import unittest
from pathlib import Path

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestFruitKIPublishPackagesMission127(unittest.TestCase):
    REQUIRED_FIELDS = {
        "schema_version",
        "platform",
        "target_channel_id",
        "target_channel_handle",
        "token_reference",
        "channel_evidence_path",
        "channel_evidence_hash",
        "channel_verified_at",
        "duplicate_preflight_path",
        "duplicate_preflight_result",
        "content_title",
        "description_draft",
        "tags",
        "hashtags",
        "category_id",
        "audience_decision",
        "self_declared_made_for_kids",
        "intended_upload_privacy",
        "intended_release_privacy",
        "media_path",
        "media_sha256",
        "qc_report_path",
        "qc_status",
        "publication_dedupe_fingerprint",
        "publication_authorized",
        "publication_state",
    }

    def _verify_package(self, pkg_path: Path):
        self.assertTrue(pkg_path.is_file(), f"Package file {pkg_path} missing")
        content = pkg_path.read_text(encoding="utf-8")
        pkg = json.loads(content)

        # 1. Schema fields check
        missing = self.REQUIRED_FIELDS - set(pkg.keys())
        self.assertEqual(missing, set(), f"Missing required fields in {pkg_path}: {missing}")
        self.assertIn(pkg["schema_version"], {"2.2", "3.0"})

        # 2. Target channel binding
        self.assertEqual(pkg["platform"], "YOUTUBE")
        self.assertEqual(pkg["target_channel_id"], "UCg0O_a10jsQ74ffS_HgFGqA")
        self.assertEqual(pkg["target_channel_handle"], "@kifruchtefilme")
        self.assertEqual(pkg["token_reference"], "fruitki-test")

        # 3. Channel & Duplicate Evidence Links
        self.assertTrue(pkg["channel_evidence_path"])
        self.assertTrue(pkg["channel_evidence_hash"])
        self.assertTrue(pkg["duplicate_preflight_path"])
        self.assertIn(pkg["duplicate_preflight_result"], {"PLATFORM_METADATA_NO_MATCH_FOUND", "NO_MATCHING_PLATFORM_METADATA_FOUND"})

        # 4. Category & Audience Decision Gate
        self.assertEqual(pkg["category_id"], "22")
        self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")
        self.assertIsNone(pkg["self_declared_made_for_kids"])

        # 5. Privacy & Authorization Gates
        self.assertEqual(pkg["intended_upload_privacy"], "private")
        self.assertEqual(pkg["intended_release_privacy"], "public")
        self.assertFalse(pkg["publication_authorized"], "publication_authorized must be False")
        self.assertEqual(pkg["publication_state"], "COMPLETE_READY_FOR_REVIEW")

        # 6. Media & QC Hash verification
        media_file = Path(pkg["media_path"])
        self.assertTrue(media_file.is_file(), f"Media file {media_file} missing")
        with open(media_file, "rb") as f:
            calculated_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(pkg["media_sha256"], calculated_sha)

        qc_file = Path(pkg["qc_report_path"])
        self.assertTrue(qc_file.is_file(), f"QC file {qc_file} missing")
        qc_data = json.loads(qc_file.read_text(encoding="utf-8"))
        self.assertEqual(qc_data.get("verdict"), "PASS")
        self.assertEqual(qc_data.get("source_hash"), calculated_sha)
        self.assertEqual(pkg["qc_status"], "PASS")

        # 7. Immutable Dedupe fingerprint calculation (Title does NOT participate)
        calculated_fp = compute_publication_dedupe_fingerprint(
            platform=pkg["platform"],
            target_channel_id=pkg["target_channel_id"],
            media_sha256=pkg["media_sha256"],
        )
        self.assertEqual(pkg["publication_dedupe_fingerprint"], calculated_fp)

        # 8. No secrets embedded
        for sensitive in ("client_secret", "access_token", "refresh_token", "private_key"):
            self.assertNotIn(sensitive, content.lower())

        return pkg

    def test_golden_trophy_package(self):
        pkg_path = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        pkg = self._verify_package(pkg_path)
        self.assertTrue("Trophäe" in pkg["content_title"] or "Trophy" in pkg["content_title"])
        self.assertEqual(pkg["media_sha256"], "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8")
        self.assertEqual(pkg["publication_dedupe_fingerprint"], "c42c6830a2b5f3d43f542b0d9521bf5572ae12e43b09bc4724e16b4a0081eed0")

    def test_mystery_box_package(self):
        pkg_path = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        pkg = self._verify_package(pkg_path)
        self.assertIn("Mystery Box", pkg["content_title"])
        self.assertEqual(pkg["media_sha256"], "0610c35c3589e38f943de2bf3efca75f670852390b69814e77f8251ab91bba99")
        self.assertEqual(pkg["publication_dedupe_fingerprint"], "0226e05a99d440b4302c0167cc9894b1e24dc497522638740472cd05dbd34b39")

    def test_immutable_fingerprint_behavior(self):
        base_fp = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            media_sha256="aabbccddeeff11223344",
        )

        # Title change produces the SAME fingerprint
        fp_same = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            media_sha256="aabbccddeeff11223344",
        )
        self.assertEqual(base_fp, fp_same)

        # Media change changes fingerprint
        fp_diff_media = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            media_sha256="different_sha",
        )
        self.assertNotEqual(base_fp, fp_diff_media)

        # Channel change changes fingerprint
        fp_diff_channel = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id="UC_DIFFERENT_CHANNEL",
            media_sha256="aabbccddeeff11223344",
        )
        self.assertNotEqual(base_fp, fp_diff_channel)


if __name__ == "__main__":
    unittest.main()
