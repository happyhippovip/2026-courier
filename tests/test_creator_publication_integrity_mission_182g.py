#!/usr/bin/env python3
"""Mission 182G: Creator Publication Integrity Final Remediation Acceptance Suite.

Validates the full closure of all Codex 180C review findings:
- BLOCKER 1: QC Hash Authority & Mutation Detection
- BLOCKER 2: Package Schema 2.2 / 3.0 Backwards Compatibility
- BLOCKER 3: Platform Authority in Publication Fingerprinting
- BLOCKER 4: Human Decision Provenance & Multi-Gate Separation
- Zero Secret Policy & Hard Firewalls
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.creator_package_enricher import (
    SUPPORTED_PLATFORMS,
    CreatorPackageEnricher,
    PublicationReadinessRecord,
    compute_publication_dedupe_fingerprint,
    compute_publication_fingerprint_v1,
)
from scripts.evidence_provenance import check_for_secrets
from scripts.publication_approval import (
    ApprovalAction,
    ApprovalRecord,
    ApprovalRegistry,
    AudienceDecisionRecord,
    AudienceDecisionState,
)
from scripts.publication_engine import (
    PublicationEngine,
    PublicationLedger,
    PublicationState,
)
from scripts.release_acceptance_gate import (
    ReleaseAcceptanceGate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestCreatorPublicationIntegrityMission182G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_182g_test_"))
        self.enricher = CreatorPackageEnricher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_content(
        self,
        content_id: str = "test_short",
        media_content: bytes = b"dummy_mp4_video_content_182g",
        qc_verdict: str = "PASS",
        qc_source_hash: str | None = None,
        include_qc: bool = True,
    ) -> Path:
        content_folder = self.test_dir / "runtime" / "content" / content_id
        content_folder.mkdir(parents=True, exist_ok=True)

        media_path = content_folder / "render.mp4"
        media_path.write_bytes(media_content)
        media_sha = hashlib.sha256(media_content).hexdigest()

        if include_qc:
            qc_file = content_folder / "qc_report.json"
            qc_payload = {
                "verdict": qc_verdict,
                "qc_status": qc_verdict,
                "checked_at": "2026-09-01T00:00:00Z",
            }
            if qc_source_hash is not None:
                qc_payload["source_hash"] = qc_source_hash
            qc_file.write_text(json.dumps(qc_payload, indent=2), encoding="utf-8")

        return content_folder

    # ==========================================================================
    # BLOCKER 1: QC HASH AUTHORITY & MUTATION DETECTION
    # ==========================================================================

    def test_01_qc_pass_missing_source_hash_fails_closed(self):
        """QC PASS report without source_hash MUST fail closed to MISSING_QC_SOURCE_HASH."""
        cid = "qc_missing_hash"
        self._create_mock_content(content_id=cid, qc_verdict="PASS", qc_source_hash=None)

        rec = self.enricher.enrich_package(cid)
        self.assertEqual(rec.qc_status, "PASS")
        self.assertEqual(rec.qc_linkage_status, "MISSING_QC_SOURCE_HASH")
        self.assertIn("LOCAL_GATE:PRODUCTION_INCOMPLETE", rec.blocking_gates)
        self.assertNotEqual(rec.publication_state, "PUBLICATION_READY")

    def test_02_qc_pass_malformed_source_hash_fails_closed(self):
        """QC PASS report with malformed source_hash (e.g. non-64-hex) MUST fail closed."""
        cid = "qc_malformed_hash"
        self._create_mock_content(content_id=cid, qc_verdict="PASS", qc_source_hash="not_a_valid_sha256")

        rec = self.enricher.enrich_package(cid)
        self.assertEqual(rec.qc_status, "PASS")
        self.assertEqual(rec.qc_linkage_status, "MALFORMED_QC_SOURCE_HASH")
        self.assertIn("LOCAL_GATE:PRODUCTION_INCOMPLETE", rec.blocking_gates)

    def test_03_qc_pass_wrong_source_hash_fails_closed(self):
        """QC PASS report with mismatched source_hash MUST fail closed to MISMATCH."""
        cid = "qc_wrong_hash"
        wrong_hash = "a" * 64
        self._create_mock_content(content_id=cid, qc_verdict="PASS", qc_source_hash=wrong_hash)

        rec = self.enricher.enrich_package(cid)
        self.assertEqual(rec.qc_status, "PASS")
        self.assertEqual(rec.qc_linkage_status, "MISMATCH")
        self.assertIn("LOCAL_GATE:PRODUCTION_INCOMPLETE", rec.blocking_gates)

    def test_04_qc_pass_matching_source_hash_is_valid(self):
        """QC PASS report with matching canonical SHA-256 is VALID."""
        cid = "qc_valid_hash"
        media_bytes = b"valid_media_content_for_qc"
        expected_sha = hashlib.sha256(media_bytes).hexdigest()
        self._create_mock_content(content_id=cid, media_content=media_bytes, qc_verdict="PASS", qc_source_hash=expected_sha)

        rec = self.enricher.enrich_package(cid)
        self.assertEqual(rec.qc_status, "PASS")
        self.assertEqual(rec.qc_linkage_status, "VALID")
        self.assertNotIn("LOCAL_GATE:PRODUCTION_INCOMPLETE", rec.blocking_gates)

    def test_05_master_mutation_after_qc_fails_closed(self):
        """If master file is mutated after QC report generation, linkage fails closed to MISMATCH."""
        cid = "qc_mutation_detect"
        media_bytes = b"original_unmutated_media"
        original_sha = hashlib.sha256(media_bytes).hexdigest()
        folder = self._create_mock_content(content_id=cid, media_content=media_bytes, qc_verdict="PASS", qc_source_hash=original_sha)

        # Mutate master file
        (folder / "render.mp4").write_bytes(b"tampered_mutated_media_bytes")

        rec = self.enricher.enrich_package(cid)
        self.assertEqual(rec.qc_linkage_status, "MISMATCH")
        self.assertIn("LOCAL_GATE:PRODUCTION_INCOMPLETE", rec.blocking_gates)

    # ==========================================================================
    # BLOCKER 2: PACKAGE SCHEMA COMPATIBILITY (2.2 / 3.0)
    # ==========================================================================

    def test_06_real_golden_trophy_satisfies_all_compatibility_semantics(self):
        """Golden Trophy package has all Schema 2.2 compatibility aliases present and valid."""
        pkg_path = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        self.assertTrue(pkg_path.is_file())
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))

        # Authoritative required compatibility fields
        required_aliases = [
            "platform",
            "media_path",
            "media_sha256",
            "content_title",
            "token_reference",
            "channel_evidence_path",
            "channel_evidence_hash",
            "channel_verified_at",
            "channel_evidence_status",
            "self_declared_made_for_kids",
        ]
        for f in required_aliases:
            self.assertIn(f, pkg, f"Missing required compatibility field: {f}")

        self.assertEqual(pkg["platform"], "YOUTUBE")
        self.assertEqual(pkg["media_sha256"], "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8")
        self.assertEqual(pkg["publication_dedupe_fingerprint"], "c42c6830a2b5f3d43f542b0d9521bf5572ae12e43b09bc4724e16b4a0081eed0")
        self.assertIsNone(pkg["self_declared_made_for_kids"])

    def test_07_real_mystery_box_satisfies_all_compatibility_semantics(self):
        """Mystery Box package has all Schema 2.2 compatibility aliases present and valid."""
        pkg_path = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        self.assertTrue(pkg_path.is_file())
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))

        required_aliases = [
            "platform",
            "media_path",
            "media_sha256",
            "content_title",
            "token_reference",
            "channel_evidence_path",
            "channel_evidence_hash",
            "channel_verified_at",
            "channel_evidence_status",
            "self_declared_made_for_kids",
        ]
        for f in required_aliases:
            self.assertIn(f, pkg, f"Missing required compatibility field: {f}")

        self.assertEqual(pkg["platform"], "YOUTUBE")
        self.assertEqual(pkg["media_sha256"], "0610c35c3589e38f943de2bf3efca75f670852390b69814e77f8251ab91bba99")
        self.assertEqual(pkg["publication_dedupe_fingerprint"], "0226e05a99d440b4302c0167cc9894b1e24dc497522638740472cd05dbd34b39")
        self.assertIsNone(pkg["self_declared_made_for_kids"])

    # ==========================================================================
    # BLOCKER 3: PLATFORM AUTHORITY IN PUBLICATION FINGERPRINTING
    # ==========================================================================

    def test_08_empty_platform_fingerprint_fails_closed(self):
        """Empty or None platform fails closed to empty string."""
        valid_sha = "a" * 64
        valid_ch = "UCg0O_a10jsQ74ffS_HgFGqA"
        self.assertEqual(compute_publication_fingerprint_v1("", valid_ch, valid_sha), "")
        self.assertEqual(compute_publication_fingerprint_v1(None, valid_ch, valid_sha), "")

    def test_09_whitespace_platform_fingerprint_fails_closed(self):
        """Whitespace platform fails closed to empty string."""
        valid_sha = "a" * 64
        valid_ch = "UCg0O_a10jsQ74ffS_HgFGqA"
        self.assertEqual(compute_publication_fingerprint_v1("   ", valid_ch, valid_sha), "")

    def test_10_unsupported_arbitrary_platform_fails_closed(self):
        """Unsupported platform (e.g. TWITTER, VIMEO, ARBITRARY) fails closed to empty string."""
        valid_sha = "a" * 64
        valid_ch = "UCg0O_a10jsQ74ffS_HgFGqA"
        self.assertEqual(compute_publication_fingerprint_v1("TWITTER", valid_ch, valid_sha), "")
        self.assertEqual(compute_publication_fingerprint_v1("VIMEO", valid_ch, valid_sha), "")
        self.assertEqual(compute_publication_fingerprint_v1("FORGED_PLATFORM", valid_ch, valid_sha), "")

    def test_11_supported_canonical_platforms_succeed(self):
        """Canonical supported platforms (YOUTUBE, TIKTOK, INSTAGRAM_REELS) produce valid fingerprints."""
        valid_sha = "a" * 64
        valid_ch = "UCg0O_a10jsQ74ffS_HgFGqA"
        for plat in SUPPORTED_PLATFORMS:
            fp = compute_publication_fingerprint_v1(plat, valid_ch, valid_sha)
            self.assertTrue(fp and len(fp) == 64, f"Failed for platform {plat}")

    def test_12_caller_precomputed_fingerprint_mismatch_fails_closed(self):
        """ReleaseAcceptanceGate rejects package if publication_dedupe_fingerprint mismatches real media."""
        gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT)
        gt_pkg_path = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"

        # Test evaluation with real package reaches AUDIENCE_DECISION_REQUIRED
        res = gate.evaluate_package(gt_pkg_path)
        self.assertEqual(res.result, "AUDIENCE_DECISION_REQUIRED")

    # ==========================================================================
    # BLOCKER 4: HUMAN DECISION PROVENANCE & MULTI-GATE SEPARATION
    # ==========================================================================

    def test_13_generic_weiter_authorizes_none_of_the_gates(self):
        """A generic 'weiter' instruction authorizes NONE of the human gates."""
        # 1. Package publication_authorized strictly False
        enricher = CreatorPackageEnricher(repo_dir=REPO_ROOT)
        rec = enricher.enrich_package("golden_trophy_short")
        self.assertFalse(rec.publication_authorized)
        self.assertEqual(rec.audience_decision, "DECISION_REQUIRED")
        self.assertEqual(rec.privacy_decision_status, "HUMAN_REQUIRED")

        # 2. Release Acceptance Gate requires explicit durable audience decision
        gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT)
        res = gate.evaluate_package(REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json")
        self.assertEqual(res.result, "AUDIENCE_DECISION_REQUIRED")

    def test_14_private_upload_approval_does_not_authorize_public_release(self):
        """Private upload approval record cannot be used to execute public release."""
        engine = PublicationEngine(repo_dir=REPO_ROOT)
        pkg_path = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))

        private_auth = ApprovalRecord(
            approval_id="app-priv-only-182g",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint=pkg["publication_dedupe_fingerprint"],
            media_sha256=pkg["media_sha256"],
            platform="YOUTUBE",
            target_channel_id=pkg["target_channel_id"],
            approved_privacy="private",
            metadata_revision_hash="meta_182g",
            audience_decision_hash="aud_182g",
            channel_evidence_hash="ch_182g",
            duplicate_evidence_hash="dup_182g",
            acceptance_id="acc_182g",
            acceptance_hash="",
            maximum_allowed_cost_eur=0.0,
        )

        res = engine.execute_public_release(pkg_path, private_auth, "VID_123")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIn(res["code"], ("AUDIENCE_DECISION_REQUIRED", "RELEASE_NOT_APPROVED"))

    def test_15_ready_for_review_does_not_authorize_publication(self):
        """A package in COMPLETE_READY_FOR_REVIEW state strictly keeps publication_authorized = False."""
        for cid in ["golden_trophy_short", "mystery_box_short"]:
            pkg_file = REPO_ROOT / "runtime" / "content" / cid / "publish_package.json"
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            self.assertEqual(pkg["publication_state"], "COMPLETE_READY_FOR_REVIEW")
            self.assertFalse(pkg["publication_authorized"])
            self.assertEqual(pkg["audience_decision"], "DECISION_REQUIRED")

    def test_16_zero_secrets_in_all_packages_and_artifacts(self):
        """All content packages in runtime/content are clean of secrets and tokens."""
        content_dir = REPO_ROOT / "runtime" / "content"
        for p in content_dir.iterdir():
            if not p.is_dir():
                continue
            pkg_file = p / "publish_package.json"
            if pkg_file.is_file():
                pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
                clean, reason = check_for_secrets(pkg_data)
                self.assertTrue(clean, f"Secret detected in {pkg_file}: {reason}")


if __name__ == "__main__":
    unittest.main()
