#!/usr/bin/env python3
"""Targeted unit tests for Mission 133G: Approval Hardening + Private-Upload Executor Preparation."""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import multiprocessing
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    ProvenanceReceipt,
    ProvenanceSource,
    TrustedYouTubeResponseAdapter,
    build_channel_evidence_package,
    build_package_duplicate_preflight,
    build_upload_snapshot_evidence_package,
    compute_payload_hash,
)
from scripts.private_upload_executor import (
    ExecutionResult,
    PrivateUploadExecutor,
    ReconciliationOutcome,
)
from scripts.publication_approval import (
    AppendOnlyApprovalLedger,
    ApprovalAction,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalState,
    AudienceDecisionRecord,
    AudienceDecisionState,
    PublicationApprovalContract,
    ReleaseOperationLedger,
    compute_deterministic_operation_id,
    compute_metadata_revision_hash,
    derive_approval_state,
    validate_finite_exact_zero,
)
from scripts.publication_engine import (
    PublicationLedger,
    PublicationState,
)
from scripts.release_acceptance_gate import (
    AcceptanceResult,
    ReleaseAcceptanceGate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _concurrent_fenced_reserve_worker(
    ledger_dir_str: str,
    fingerprint: str,
    token: str,
    result_queue: multiprocessing.Queue,
):
    ledger = PublicationLedger(Path(ledger_dir_str))
    ok, code, data = ledger.reserve(
        fingerprint=fingerprint,
        target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
        media_sha256="test_sha",
        reservation_token=token,
    )
    result_queue.put({"ok": ok, "code": code, "token": token, "pid": os.getpid()})


class TestApprovalHardeningAndExecutorMission133G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_133g_test_"))
        self.executor = PrivateUploadExecutor(repo_dir=self.test_dir, allow_test_fixtures=True)
        self.approval_registry = ApprovalRegistry(self.test_dir / "events" / "approvals" / "registry")
        self.approval_ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        self.contract = PublicationApprovalContract(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ----------------------------------------------------
    # PHASE A: APPROVAL REGISTRY, MONEY & DETERMINISTIC ID
    # ----------------------------------------------------

    def test_approval_id_first_registration_and_idempotent_duplicate(self):
        rec = ApprovalRecord(
            approval_id="app-133-001",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_123",
            media_sha256="media_sha_123",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_hash_123",
            audience_decision_hash="aud_hash_123",
            channel_evidence_hash="ch_hash_123",
            duplicate_evidence_hash="dup_hash_123",
            acceptance_id="acc-001",
            acceptance_hash="acc_hash_123",
            maximum_allowed_cost_eur=0.0,
        )
        # 1. First registration
        ok1, code1, _ = self.approval_registry.register_approval(rec)
        self.assertTrue(ok1)
        self.assertEqual(code1, "APPROVAL_REGISTERED")

        # 2. Identical duplicate registration
        ok2, code2, _ = self.approval_registry.register_approval(rec)
        self.assertTrue(ok2)
        self.assertEqual(code2, "IDEMPOTENT_EXISTING_APPROVAL")

    def test_approval_id_conflict_detection(self):
        rec1 = ApprovalRecord(
            approval_id="app-133-conflict",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_123",
            media_sha256="media_sha_123",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_hash_123",
            audience_decision_hash="aud_hash_123",
            channel_evidence_hash="ch_hash_123",
            duplicate_evidence_hash="dup_hash_123",
            acceptance_id="acc-001",
            acceptance_hash="acc_hash_123",
            maximum_allowed_cost_eur=0.0,
        )
        self.approval_registry.register_approval(rec1)

        # Conflicting action
        rec_conflict_action = ApprovalRecord(
            approval_id="app-133-conflict",
            approved_action="PUBLIC_RELEASE",
            publication_fingerprint="fp_123",
            media_sha256="media_sha_123",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="public",
            metadata_revision_hash="meta_hash_123",
            audience_decision_hash="aud_hash_123",
            channel_evidence_hash="ch_hash_123",
            duplicate_evidence_hash="dup_hash_123",
            acceptance_id="acc-001",
            acceptance_hash="acc_hash_123",
            maximum_allowed_cost_eur=0.0,
        )
        ok, code, details = self.approval_registry.register_approval(rec_conflict_action)
        self.assertFalse(ok)
        self.assertEqual(code, "APPROVAL_ID_CONFLICT")
        self.assertIn("approved_action", details["conflicts"])

    def test_caller_active_vs_ledger_derived_state(self):
        app_id = "app-133-state-test"
        rec = ApprovalRecord(
            approval_id=app_id,
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_123",
            media_sha256="media_sha_123",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_hash_123",
            audience_decision_hash="aud_hash_123",
            channel_evidence_hash="ch_hash_123",
            duplicate_evidence_hash="dup_hash_123",
            acceptance_id="acc-001",
            acceptance_hash="acc_hash_123",
            state="ACTIVE",  # Caller claims active
        )
        self.approval_registry.register_approval(rec)

        # Mark consumed in ledger
        self.approval_ledger.record_event(
            approval_id=app_id,
            approval_state="CONSUMED",
            publication_fingerprint="fp_123",
            action="PRIVATE_UPLOAD",
            reason="Already uploaded",
        )

        # Validation derived from ledger must reject as APPROVAL_CONSUMED
        ok, code, _ = self.contract.validate_approval_for_execution(
            approval=rec,
            package_data={"platform": "YOUTUBE", "target_channel_id": "UCg0O_a10jsQ74ffS_HgFGqA", "media_sha256": "media_sha_123", "publication_dedupe_fingerprint": "fp_123"},
            requested_action="PRIVATE_UPLOAD",
        )
        self.assertFalse(ok)
        self.assertEqual(code, "APPROVAL_CONSUMED")

    def test_money_firewall_finite_exact_zero(self):
        # Valid
        self.assertEqual(validate_finite_exact_zero(0), (True, "ZERO_COST_VERIFIED"))
        self.assertEqual(validate_finite_exact_zero(0.0), (True, "ZERO_COST_VERIFIED"))

        # Invalid cases -> PAYMENT_APPROVAL_REQUIRED
        invalid_cases = [
            None,
            True,
            False,
            "0",
            "0.0",
            "UNKNOWN",
            float("nan"),
            float("inf"),
            float("-inf"),
            -0.01,
            -1.0,
            0.01,
            5.0,
        ]
        for val in invalid_cases:
            ok, code = validate_finite_exact_zero(val)
            self.assertFalse(ok, f"Value {val} should fail money firewall")
            self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_deterministic_operation_id(self):
        op1 = compute_deterministic_operation_id(
            approved_action="PRIVATE_UPLOAD",
            approval_id="app-1",
            publication_fingerprint="fp-1",
            target_channel_id="ch-1",
        )
        op2 = compute_deterministic_operation_id(
            approved_action="PRIVATE_UPLOAD",
            approval_id="app-1",
            publication_fingerprint="fp-1",
            target_channel_id="ch-1",
        )
        self.assertEqual(op1, op2)

        # Different parameters yield different operation IDs
        op_diff_app = compute_deterministic_operation_id(
            approved_action="PRIVATE_UPLOAD",
            approval_id="app-2",
            publication_fingerprint="fp-1",
            target_channel_id="ch-1",
        )
        self.assertNotEqual(op1, op_diff_app)

        op_diff_action = compute_deterministic_operation_id(
            approved_action="PUBLIC_RELEASE",
            approval_id="app-1",
            publication_fingerprint="fp-1",
            target_channel_id="ch-1",
        )
        self.assertNotEqual(op1, op_diff_action)

    # ----------------------------------------------------
    # PHASE B: EXECUTOR, CONCURRENCY & CRASH RECOVERY
    # ----------------------------------------------------

    def test_fenced_reservation_concurrency_2_and_6_workers(self):
        # Test with 2 workers
        queue2 = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_concurrent_fenced_reserve_worker, args=(str(self.test_dir / "events" / "publications"), "fp_race_2", "tok-1", queue2))
        p2 = multiprocessing.Process(target=_concurrent_fenced_reserve_worker, args=(str(self.test_dir / "events" / "publications"), "fp_race_2", "tok-2", queue2))
        p1.start()
        p2.start()
        p1.join(timeout=3)
        p2.join(timeout=3)
        res2 = [queue2.get(), queue2.get()]
        winners2 = [r for r in res2 if r["ok"] is True]
        self.assertEqual(len(winners2), 1)

        # Test with 6 workers
        queue6 = multiprocessing.Queue()
        procs6 = [
            multiprocessing.Process(target=_concurrent_fenced_reserve_worker, args=(str(self.test_dir / "events" / "publications"), "fp_race_6", f"tok-{i}", queue6))
            for i in range(6)
        ]
        for p in procs6:
            p.start()
        for p in procs6:
            p.join(timeout=5)
        res6 = [queue6.get() for _ in range(6)]
        winners6 = [r for r in res6 if r["ok"] is True]
        self.assertEqual(len(winners6), 1)

    def _setup_mock_fixture_package(self) -> tuple[Path, ApprovalRecord]:
        pkg_dir = self.test_dir / "golden_trophy_short"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.test_dir / "events" / "evidence"
        rcpt_dir = self.test_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        media_bytes = b"golden_video_content_mission_133g"
        media_sha = hashlib.sha256(media_bytes).hexdigest()
        ch_id = "UCg0O_a10jsQ74ffS_HgFGqA"

        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_bytes)

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({"verdict": "PASS", "source_hash": media_sha}), encoding="utf-8")

        mock_raw_ch = {
            "kind": "youtube#channelListResponse",
            "items": [{
                "kind": "youtube#channel",
                "id": ch_id,
                "snippet": {"title": "FruitKI", "customUrl": "@kifruchtefilme"},
                "contentDetails": {"relatedPlaylists": {"uploads": f"UU{ch_id[2:]}"}},
            }],
        }
        ch_ev, ch_rcpt = TrustedYouTubeResponseAdapter.ingest_channel_response(
            mock_raw_ch,
            started_at=now_ts,
            retrieved_at=now_ts,
        )
        (ev_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        mock_fetch = lambda tok: {
            "kind": "youtube#playlistItemListResponse",
            "items": [{"contentDetails": {"videoId": "V1"}}, {"contentDetails": {"videoId": "V2"}}],
            "nextPageToken": None,
        }
        snap_ev, snap_rcpt = TrustedYouTubeResponseAdapter.ingest_uploads_paginated_reader(
            fetch_page_fn=mock_fetch,
            channel_id=ch_id,
            uploads_playlist_id=f"UU{ch_id[2:]}",
            started_at=now_ts,
            retrieved_at=now_ts,
        )
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")

        fp = compute_publication_dedupe_fingerprint(platform="YOUTUBE", target_channel_id=ch_id, media_sha256=media_sha)
        dup_rec = build_package_duplicate_preflight(
            publication_fingerprint=fp,
            media_sha256=media_sha,
            target_channel_id=ch_id,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            channel_receipt_hash=ch_rcpt.receipt_hash,
            upload_snapshot_hash=snap_ev["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=2,
            page_count=1,
            coverage_complete=True,
            duplicate_match=False,
            checked_at=now_ts,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")

        aud_rec = AudienceDecisionRecord.create(
            content_id="golden_trophy_short",
            decision="NOT_MADE_FOR_KIDS",
            decision_source="HUMAN_REVIEW",
            evidence_reference="scene.gd",
            media_sha256=media_sha,
            publication_fingerprint=fp,
        )

        pkg_path = pkg_dir / "publish_package.json"
        pkg_dict = {
            "schema_version": "2.2",
            "platform": "YOUTUBE",
            "target_channel_id": ch_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ev_dir / "channel_evidence_fruitki.json"),
            "channel_evidence_hash": ch_ev["payload_evidence_hash"],
            "channel_verified_at": now_ts,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": "PLATFORM_METADATA_NO_MATCH_FOUND",
            "content_title": "Goldene Trophäe 🏆🍓 #Shorts",
            "description_draft": "FruitKI Short Description",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#FruitKI", "#Shorts"],
            "category_id": "22",
            "audience_decision": "NOT_MADE_FOR_KIDS",
            "self_declared_made_for_kids": False,
            "intended_upload_privacy": "private",
            "intended_release_privacy": "public",
            "media_path": str(media_path),
            "media_sha256": media_sha,
            "qc_report_path": str(qc_path),
            "qc_status": "PASS",
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": False,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "cost_eur": 0.0,
            "prepared_at": now_ts,
            "audience_decision_hash": aud_rec.decision_hash,
        }
        pkg_path.write_text(json.dumps(pkg_dict, indent=2), encoding="utf-8")

        meta_hash = compute_metadata_revision_hash(pkg_dict)
        app_record = ApprovalRecord(
            approval_id="app-133-fixture",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint=fp,
            media_sha256=media_sha,
            platform="YOUTUBE",
            target_channel_id=ch_id,
            approved_privacy="private",
            metadata_revision_hash=meta_hash,
            audience_decision_hash=aud_rec.decision_hash,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            duplicate_evidence_hash=snap_ev["payload_evidence_hash"],
            acceptance_id="acc-133-fix",
            acceptance_hash="",
            maximum_allowed_cost_eur=0.0,
        )
        self.approval_registry.register_approval(app_record)
        return pkg_path, app_record, aud_rec

    def test_executor_successful_private_upload_and_approval_consumption(self):
        pkg_path, app_rec, aud_rec = self._setup_mock_fixture_package()
        mock_upload = lambda p: {"status": "SUCCESS", "video_id": "VID_NEW_123"}

        res = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=app_rec,
            audience_record=aud_rec,
            upload_mutation_mock=mock_upload,
        )
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.code, "UPLOADED_PRIVATE")
        self.assertEqual(res.video_id, "VID_NEW_123")

        # Approval must be consumed in ledger
        eff_state = derive_approval_state(app_rec.approval_id, self.approval_ledger)
        self.assertEqual(eff_state, "CONSUMED")

    def test_crash_safety_and_reconciliation_unique_match(self):
        pkg_path, app_rec, aud_rec = self._setup_mock_fixture_package()
        res = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=app_rec,
            audience_record=aud_rec,
            simulate_crash_at="AFTER_DISPATCH",
        )
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.code, "EXTERNAL_OUTCOME_UNCERTAIN")

        # Reconciliation confirms unique video
        reconcile_provider = lambda op, fp: (True, {
            "videoId": "VID_RECONCILED_888",
            "privacyStatus": "private",
            "channelId": "UCg0O_a10jsQ74ffS_HgFGqA",
        })
        rec_ok, rec_code, vid = self.executor.reconcile_uncertain_operation(
            operation_id=res.operation_id,
            fingerprint=app_rec.publication_fingerprint,
            approval_id=app_rec.approval_id,
            reconciliation_provider=reconcile_provider,
        )
        self.assertTrue(rec_ok)
        self.assertEqual(rec_code, "RECONCILED_SUCCESS")
        self.assertEqual(vid, "VID_RECONCILED_888")

        # Approval consumed after reconciliation
        eff_state = derive_approval_state(app_rec.approval_id, self.approval_ledger)
        self.assertEqual(eff_state, "CONSUMED")

    def test_real_packages_stop_at_human_audience_gate(self):
        gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT)
        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        gt_res = gate.evaluate_package(gt_pkg)
        self.assertEqual(gt_res.result, "AUDIENCE_DECISION_REQUIRED")

        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        mb_res = gate.evaluate_package(mb_pkg)
        self.assertEqual(mb_res.result, "AUDIENCE_DECISION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
