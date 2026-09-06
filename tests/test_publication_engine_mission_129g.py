#!/usr/bin/env python3
"""Targeted unit tests for Mission 129G Publication Safety Remediation."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    build_channel_evidence_package,
    build_package_duplicate_preflight,
    build_upload_snapshot_evidence_package,
)
from scripts.publication_engine import (
    AuthorizationRecord,
    PublicationEngine,
    PublicationLedger,
    PublicationState,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPublicationEngineMission129G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_129g_test_"))
        self.engine = PublicationEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_immutable_fingerprint_title_invariance(self):
        """Title change must NOT alter upload identity."""
        media_sha = "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8"
        ch_id = "UCg0O_a10jsQ74ffS_HgFGqA"

        fp1 = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id=ch_id, media_sha256=media_sha
        )
        fp2 = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id=ch_id, media_sha256=media_sha
        )
        self.assertEqual(fp1, fp2)

        # Media change changes fingerprint
        fp_media = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id=ch_id, media_sha256="0610c35c3589e38f943de2bf3efca75f670852390b69814e77f8251ab91bba99"
        )
        self.assertNotEqual(fp1, fp_media)

        # Channel change changes fingerprint
        fp_ch = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id="UC_OTHER", media_sha256=media_sha
        )
        self.assertNotEqual(fp1, fp_ch)

    def test_real_packages_fail_closed_with_audience_decision_required(self):
        """Real FruitKI packages must fail closed on AUDIENCE_DECISION_REQUIRED before authorization."""
        real_engine = PublicationEngine(repo_dir=REPO_ROOT)

        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        gt_res = real_engine.validate_package(gt_pkg)
        self.assertFalse(gt_res.valid)
        self.assertEqual(gt_res.code, "AUDIENCE_DECISION_REQUIRED")

        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        mb_res = real_engine.validate_package(mb_pkg)
        self.assertFalse(mb_res.valid)
        self.assertEqual(mb_res.code, "AUDIENCE_DECISION_REQUIRED")

    def _create_mock_environment(
        self,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        media_bytes: bytes = b"test_video_payload_bytes",
        audience_decision: str = "NOT_MADE_FOR_KIDS",
        self_declared_made_for_kids: bool = False,
        coverage_complete: bool = True,
        duplicate_match: bool = False,
        evidence_age_seconds: float = 0.0,
        authorized: bool = True,
    ) -> tuple[Path, AuthorizationRecord]:
        pkg_dir = self.test_dir / "mock_pkg"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.test_dir / "events" / "evidence"
        rcpt_dir = self.test_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        # 1. Media & QC
        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_bytes)
        media_sha = hashlib.sha256(media_bytes).hexdigest()

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({"verdict": "PASS", "source_hash": media_sha}), encoding="utf-8")

        # 2. Channel Evidence & Receipt
        import datetime
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        retrieved_dt = (now_dt - datetime.timedelta(seconds=evidence_age_seconds)).isoformat()

        ch_ev, ch_rcpt = build_channel_evidence_package(
            channel_id=channel_id,
            channel_handle="@kifruchtefilme",
            channel_title="FruitKI",
            retrieved_at=retrieved_dt,
            started_at=retrieved_dt,
        )
        (ev_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        # 3. Upload Snapshot Evidence & Receipt
        snap_ev, snap_rcpt = build_upload_snapshot_evidence_package(
            channel_id=channel_id,
            uploads_playlist_id=f"UU{channel_id[2:]}",
            video_ids=["V1", "V2"],
            coverage_complete=coverage_complete,
            retrieved_at=retrieved_dt,
            started_at=retrieved_dt,
        )
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")

        # 4. Duplicate Preflight
        fp = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id=channel_id, media_sha256=media_sha
        )
        dup_raw = build_package_duplicate_preflight(
            publication_fingerprint=fp,
            media_sha256=media_sha,
            target_channel_id=channel_id,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            channel_receipt_hash=ch_rcpt.receipt_hash,
            upload_snapshot_hash=snap_ev["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=2,
            page_count=1,
            coverage_complete=coverage_complete,
            duplicate_match=duplicate_match,
            checked_at=retrieved_dt,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_raw, indent=2), encoding="utf-8")

        # 5. Package
        pkg_path = pkg_dir / "publish_package.json"
        pkg_path.write_text(json.dumps({
            "schema_version": "2.2",
            "platform": "YOUTUBE",
            "target_channel_id": channel_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ev_dir / "channel_evidence_fruitki.json"),
            "channel_evidence_hash": ch_ev["payload_evidence_hash"],
            "channel_verified_at": retrieved_dt,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": dup_raw["result"],
            "content_title": "Test Title #Shorts",
            "description_draft": "Test description draft",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": audience_decision,
            "self_declared_made_for_kids": self_declared_made_for_kids,
            "intended_upload_privacy": "private",
            "intended_release_privacy": "public",
            "media_path": str(media_path),
            "media_sha256": media_sha,
            "qc_report_path": str(qc_path),
            "qc_status": "PASS",
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": authorized,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "prepared_at": retrieved_dt,
        }), encoding="utf-8")

        auth_record = AuthorizationRecord(
            approval_id="test-app-001",
            package_fingerprint=fp,
            approved_action="PRIVATE_UPLOAD",
            approved_channel=channel_id,
            approved_privacy="private",
            approved_at=retrieved_dt,
            authorization_source="EXPLICIT_HUMAN_APPROVAL",
        )
        return pkg_path, auth_record

    def test_resolved_audience_decision_passes(self):
        pkg_path, auth = self._create_mock_environment(
            audience_decision="NOT_MADE_FOR_KIDS",
            self_declared_made_for_kids=False,
            authorized=True,
        )
        res = self.engine.validate_package(pkg_path, auth)
        self.assertTrue(res.valid)
        self.assertEqual(res.code, "PASS")

    def test_unresolved_audience_decision_blocks(self):
        pkg_path, auth = self._create_mock_environment(
            audience_decision="DECISION_REQUIRED",
            self_declared_made_for_kids=None,
            authorized=True,
        )
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "AUDIENCE_DECISION_REQUIRED")

    def test_stale_channel_evidence_blocks(self):
        engine = PublicationEngine(repo_dir=self.test_dir, channel_freshness_seconds=3600.0)
        pkg_path, auth = self._create_mock_environment(evidence_age_seconds=7200.0)
        res = engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "CHANNEL_EVIDENCE_STALE")

    def test_incomplete_duplicate_coverage_blocks(self):
        pkg_path, auth = self._create_mock_environment(coverage_complete=False)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "DUPLICATE_CHECK_INCOMPLETE")

    def test_duplicate_match_blocks(self):
        pkg_path, auth = self._create_mock_environment(duplicate_match=True)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "DUPLICATE_MATCH_FOUND")

    def test_title_edit_cannot_bypass_duplicate_reservation(self):
        pkg_path, auth = self._create_mock_environment()
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        fp = pkg["publication_dedupe_fingerprint"]

        # Reserve once
        ok1, msg1, _ = self.engine.ledger.reserve(fp, pkg["target_channel_id"], pkg["media_sha256"], "tok-1")
        self.assertTrue(ok1)

        # Title changed in package, but media remains identical -> same immutable fingerprint
        pkg["content_title"] = "Completely New Changed Title #Shorts"
        same_fp = compute_publication_dedupe_fingerprint(
            platform=pkg["platform"],
            target_channel_id=pkg["target_channel_id"],
            media_sha256=pkg["media_sha256"],
        )
        self.assertEqual(fp, same_fp)

        # Attempt duplicate reservation with new title fails
        ok2, msg2, _ = self.engine.ledger.reserve(same_fp, pkg["target_channel_id"], pkg["media_sha256"], "tok-2")
        self.assertFalse(ok2)
        self.assertEqual(msg2, "ALREADY_RESERVED")


if __name__ == "__main__":
    unittest.main()
