#!/usr/bin/env python3
"""Targeted unit tests for Mission 128G Safe Publication Execution Engine."""

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


class TestPublicationEngineMission128G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_engine_test_"))
        self.engine = PublicationEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_real_fruitki_packages_preflight_fail_closed(self):
        """Verify real Golden Trophy and Mystery Box packages fail closed at audience gate."""
        real_engine = PublicationEngine(repo_dir=REPO_ROOT)

        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        gt_res = real_engine.validate_package(gt_pkg)
        self.assertFalse(gt_res.valid)
        self.assertEqual(gt_res.code, "AUDIENCE_DECISION_REQUIRED")

        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        mb_res = real_engine.validate_package(mb_pkg)
        self.assertFalse(mb_res.valid)
        self.assertEqual(mb_res.code, "AUDIENCE_DECISION_REQUIRED")

    def _create_mock_package(
        self,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        media_content: bytes = b"mock_video_bytes",
        qc_verdict: str = "PASS",
        authorized: bool = True,
        title: str = "Test Title #Shorts",
        price: float = 0.0,
    ) -> tuple[Path, AuthorizationRecord]:
        pkg_dir = self.test_dir / "mock_pkg"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.test_dir / "events" / "evidence"
        rcpt_dir = self.test_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_content)
        media_sha = hashlib.sha256(media_content).hexdigest()

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({
            "verdict": qc_verdict,
            "source_hash": media_sha,
        }), encoding="utf-8")

        import datetime
        now_dt = datetime.datetime.now(datetime.timezone.utc).isoformat()

        ch_ev, ch_rcpt = build_channel_evidence_package(
            channel_id=channel_id,
            channel_handle="@kifruchtefilme",
            channel_title="FruitKI",
            retrieved_at=now_dt,
            started_at=now_dt,
        )
        (ev_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        snap_ev, snap_rcpt = build_upload_snapshot_evidence_package(
            channel_id=channel_id,
            uploads_playlist_id=f"UU{channel_id[2:]}",
            video_ids=["V1", "V2"],
            retrieved_at=now_dt,
            started_at=now_dt,
        )
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")

        fp = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE",
            target_channel_id=channel_id,
            media_sha256=media_sha,
        )

        dup_rec = build_package_duplicate_preflight(
            publication_fingerprint=fp,
            media_sha256=media_sha,
            target_channel_id=channel_id,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            channel_receipt_hash=ch_rcpt.receipt_hash,
            upload_snapshot_hash=snap_ev["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=2,
            page_count=1,
            coverage_complete=True,
            duplicate_match=False,
            checked_at=now_dt,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")

        pkg_path = pkg_dir / "publish_package.json"
        pkg_path.write_text(json.dumps({
            "schema_version": "2.2",
            "platform": "YOUTUBE",
            "target_channel_id": channel_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ev_dir / "channel_evidence_fruitki.json"),
            "channel_evidence_hash": ch_ev["payload_evidence_hash"],
            "channel_verified_at": now_dt,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": dup_rec["result"],
            "content_title": title,
            "description_draft": "Test description draft",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": "NOT_MADE_FOR_KIDS",
            "self_declared_made_for_kids": False,
            "intended_upload_privacy": "private",
            "intended_release_privacy": "public",
            "media_path": str(media_path),
            "media_sha256": media_sha,
            "qc_report_path": str(qc_path),
            "qc_status": qc_verdict,
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": authorized,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "prepared_at": now_dt,
        }), encoding="utf-8")

        auth_record = AuthorizationRecord(
            approval_id="test-approval-001",
            package_fingerprint=fp,
            approved_action="PRIVATE_UPLOAD",
            approved_channel=channel_id,
            approved_privacy="private",
            approved_at="2026-08-31T11:00:00Z",
            authorization_source="TEST_EXPLICIT_HUMAN_APPROVAL",
            max_cost_eur=price,
        )
        return pkg_path, auth_record

    def test_preflight_validates_clean_authorized_package(self):
        pkg_path, auth = self._create_mock_package(authorized=True)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertTrue(res.valid)
        self.assertEqual(res.code, "PASS")

    def test_target_channel_mismatch_rejected(self):
        pkg_path, auth = self._create_mock_package(channel_id="UC_WRONG_CHANNEL")
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "TARGET_CHANNEL_MISMATCH")

    def test_master_hash_mismatch_rejected(self):
        pkg_path, auth = self._create_mock_package()
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
        Path(pkg_data["media_path"]).write_bytes(b"tampered_bytes")
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "MASTER_HASH_MISMATCH")

    def test_qc_mismatch_rejected(self):
        pkg_path, auth = self._create_mock_package(qc_verdict="FAIL")
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "QC_VERDICT_NOT_PASS")

    def test_zero_spend_firewall_rejected(self):
        pkg_path, auth = self._create_mock_package(price=5.0)
        res = self.engine.validate_package(pkg_path, auth)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "PAYMENT_APPROVAL_REQUIRED")

    def test_atomic_reservation_and_duplicate_prevention(self):
        pkg_path, auth = self._create_mock_package()
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        fp = pkg["publication_dedupe_fingerprint"]

        # First reservation passes
        ok1, msg1, _ = self.engine.ledger.reserve(fp, pkg["target_channel_id"], pkg["media_sha256"], "tok-1")
        self.assertTrue(ok1)

        # Duplicate reservation fails
        ok2, msg2, _ = self.engine.ledger.reserve(fp, pkg["target_channel_id"], pkg["media_sha256"], "tok-2")
        self.assertFalse(ok2)
        self.assertEqual(msg2, "ALREADY_RESERVED")

    def test_private_upload_and_public_release_state_machine(self):
        pkg_path, upload_auth = self._create_mock_package()
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        fp = pkg["publication_dedupe_fingerprint"]

        mock_upload = lambda p: {"status": "SUCCESS", "video_id": "MOCK_VID_123"}
        res_upload = self.engine.execute_private_upload(pkg_path, upload_auth, execute_mock=mock_upload)
        self.assertEqual(res_upload["status"], "SUCCESS")
        self.assertEqual(res_upload["video_id"], "MOCK_VID_123")
        self.assertEqual(self.engine.ledger.get_state(fp), PublicationState.UPLOADED_PRIVATE)

        res_fail_release = self.engine.execute_public_release(pkg_path, upload_auth, "MOCK_VID_123")
        self.assertEqual(res_fail_release["status"], "BLOCKED")
        self.assertEqual(res_fail_release["code"], "RELEASE_NOT_APPROVED")

        release_auth = AuthorizationRecord(
            approval_id="release-app-001",
            package_fingerprint=fp,
            approved_action="PUBLIC_RELEASE",
            approved_channel=pkg["target_channel_id"],
            approved_privacy="public",
            approved_at="2026-08-31T11:05:00Z",
            authorization_source="HUMAN_EXPLICIT_RELEASE_APPROVAL",
        )
        mock_release = lambda p, vid: {"status": "SUCCESS"}
        res_release = self.engine.execute_public_release(pkg_path, release_auth, "MOCK_VID_123", execute_mock=mock_release)
        self.assertEqual(res_release["status"], "SUCCESS")
        self.assertEqual(self.engine.ledger.get_state(fp), PublicationState.RELEASED_PUBLIC)

    def test_crash_safety_and_uncertain_outcome_reconciliation(self):
        pkg_path, upload_auth = self._create_mock_package()
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        fp = pkg["publication_dedupe_fingerprint"]

        def mock_crash(p):
            raise ConnectionResetError("Socket reset during chunk transfer")

        res = self.engine.execute_private_upload(pkg_path, upload_auth, execute_mock=mock_crash)
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["code"], "EXTERNAL_OUTCOME_UNCERTAIN")
        self.assertTrue(res["reconciliation_required"])
        self.assertEqual(self.engine.ledger.get_state(fp), PublicationState.EXTERNAL_OUTCOME_UNCERTAIN)


if __name__ == "__main__":
    unittest.main()
