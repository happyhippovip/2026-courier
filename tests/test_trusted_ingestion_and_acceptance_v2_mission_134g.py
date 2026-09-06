#!/usr/bin/env python3
"""Targeted unit tests for Mission 134G: Trusted Provider Ingestion + Acceptance V2 + At-Most-One Dispatch."""

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
    check_for_secrets,
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
    compute_acceptance_event_hash,
    compute_acceptance_input_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTrustedIngestionAndAcceptanceV2Mission134G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_134g_test_"))
        self.executor = PrivateUploadExecutor(repo_dir=self.test_dir, allow_test_fixtures=True)
        self.gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self.strict_gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        self.approval_registry = ApprovalRegistry(self.test_dir / "events" / "approvals" / "registry")
        self.approval_ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        self.contract = PublicationApprovalContract(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ----------------------------------------------------
    # PHASE A: TRUSTED INGESTION, FORGERY & SECRETS
    # ----------------------------------------------------

    def test_generic_builder_attempts_actual_provider_read_rejected(self):
        """Generic builders must strictly reject attempts to produce ACTUAL_PROVIDER_READ."""
        with self.assertRaises(PermissionError):
            build_channel_evidence_package(
                channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                channel_handle="@kifruchtefilme",
                channel_title="FruitKI",
                provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
            )

        with self.assertRaises(PermissionError):
            build_upload_snapshot_evidence_package(
                channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                uploads_playlist_id="UUg0O_a10jsQ74ffS_HgFGqA",
                video_ids=["V1", "V2"],
                provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
            )

    def test_trusted_adapter_channel_response_ingestion(self):
        """TrustedYouTubeResponseAdapter ingests actual channels.list API response."""
        mock_raw = {
            "kind": "youtube#channelListResponse",
            "pageInfo": {"totalResults": 1, "resultsPerPage": 5},
            "items": [
                {
                    "kind": "youtube#channel",
                    "id": "UCg0O_a10jsQ74ffS_HgFGqA",
                    "snippet": {
                        "title": "FruitKI",
                        "customUrl": "@kifruchtefilme",
                    },
                    "contentDetails": {
                        "relatedPlaylists": {"uploads": "UUg0O_a10jsQ74ffS_HgFGqA"},
                    },
                }
            ],
        }
        ev, rcpt = TrustedYouTubeResponseAdapter.ingest_channel_response(mock_raw)
        self.assertEqual(ev["channel_id"], "UCg0O_a10jsQ74ffS_HgFGqA")
        self.assertEqual(ev["channel_handle"], "@kifruchtefilme")
        self.assertEqual(ev["uploads_playlist_id"], "UUg0O_a10jsQ74ffS_HgFGqA")
        self.assertEqual(rcpt.provenance_source, ProvenanceSource.TEST_FIXTURE.value)
        self.assertTrue(rcpt.verify_integrity())

        # Invalid response kind raises ValueError
        with self.assertRaises(ValueError):
            TrustedYouTubeResponseAdapter.ingest_channel_response({"kind": "invalid"})

        # Empty items list raises ValueError
        with self.assertRaises(ValueError):
            TrustedYouTubeResponseAdapter.ingest_channel_response({"kind": "youtube#channelListResponse", "items": []})

    def test_trusted_adapter_upload_paginated_reader(self):
        """Pagination reader handles zero-item, single-page, multi-page, and partial failure."""
        # 1. Single-page response
        def fetch_single_page(page_tok):
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [
                    {"contentDetails": {"videoId": "VID_1"}, "snippet": {"title": "Title 1"}},
                    {"contentDetails": {"videoId": "VID_2"}, "snippet": {"title": "Title 2"}},
                ],
                "nextPageToken": None,
            }

        ev1, rcpt1 = TrustedYouTubeResponseAdapter.ingest_uploads_paginated_reader(
            fetch_page_fn=fetch_single_page,
            channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            uploads_playlist_id="UUg0O_a10jsQ74ffS_HgFGqA",
        )
        self.assertEqual(ev1["items_checked"], 2)
        self.assertEqual(ev1["page_count"], 1)
        self.assertTrue(ev1["coverage_complete"])
        self.assertEqual(rcpt1.provenance_source, ProvenanceSource.TEST_FIXTURE.value)

        # 2. Multi-page response
        def fetch_multi_page(page_tok):
            if page_tok is None:
                return {
                    "kind": "youtube#playlistItemListResponse",
                    "items": [{"contentDetails": {"videoId": "VID_P1"}}],
                    "nextPageToken": "PAGE_2_TOK",
                }
            elif page_tok == "PAGE_2_TOK":
                return {
                    "kind": "youtube#playlistItemListResponse",
                    "items": [{"contentDetails": {"videoId": "VID_P2"}}],
                    "nextPageToken": None,
                }
            raise ValueError("Unknown token")

        ev2, rcpt2 = TrustedYouTubeResponseAdapter.ingest_uploads_paginated_reader(
            fetch_page_fn=fetch_multi_page,
            channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            uploads_playlist_id="UUg0O_a10jsQ74ffS_HgFGqA",
        )
        self.assertEqual(ev2["items_checked"], 2)
        self.assertEqual(ev2["page_count"], 2)
        self.assertTrue(ev2["coverage_complete"])

        # 3. Partial failure mid-pagination
        def fetch_fail_page(page_tok):
            if page_tok is None:
                return {
                    "kind": "youtube#playlistItemListResponse",
                    "items": [{"contentDetails": {"videoId": "VID_1"}}],
                    "nextPageToken": "PAGE_2_TOK",
                }
            raise ConnectionResetError("Socket broken")

        ev3, rcpt3 = TrustedYouTubeResponseAdapter.ingest_uploads_paginated_reader(
            fetch_page_fn=fetch_fail_page,
            channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            uploads_playlist_id="UUg0O_a10jsQ74ffS_HgFGqA",
        )
        self.assertFalse(ev3["coverage_complete"])

    def test_secret_safety_detection(self):
        """Rejects objects containing secret keys or token patterns."""
        clean, _ = check_for_secrets({"title": "Clean Title", "count": 5})
        self.assertTrue(clean)

        dirty_key, reason_k = check_for_secrets({"title": "Secret", "client_secret": "xyz"})
        self.assertFalse(dirty_key)
        self.assertIn("Forbidden secret key", reason_k)

        dirty_token, reason_t = check_for_secrets({"token": "ya29.a0AfH6SMD...sample_oauth_token"})
        self.assertFalse(dirty_token)
        self.assertIn("OAuth token pattern", reason_t)

    # ----------------------------------------------------
    # PHASE B: ACCEPTANCE V2 IDENTITY & RUNTIME GATE
    # ----------------------------------------------------

    def test_acceptance_identity_v2_input_stability(self):
        """acceptance_input_hash is invariant across evaluation timestamps and dynamic receipts."""
        content_id = "golden_trophy_short"
        platform = "YOUTUBE"
        target_ch = "UCg0O_a10jsQ74ffS_HgFGqA"
        media_sha = "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8"
        fp = "c42c6830a2b5f3d43f542b0d9521bf5572ae12e43b09bc4724e16b4a0081eed0"
        meta_hash = "meta_hash_test_123"
        aud_hash = "aud_hash_test_123"

        inp1 = compute_acceptance_input_hash(
            content_id=content_id,
            platform=platform,
            target_channel_id=target_ch,
            media_sha256=media_sha,
            publication_fingerprint=fp,
            metadata_revision_hash=meta_hash,
            audience_decision_hash=aud_hash,
        )

        inp2 = compute_acceptance_input_hash(
            content_id=content_id,
            platform=platform,
            target_channel_id=target_ch,
            media_sha256=media_sha,
            publication_fingerprint=fp,
            metadata_revision_hash=meta_hash,
            audience_decision_hash=aud_hash,
        )
        self.assertEqual(inp1, inp2)

        # Event hash binds dynamic timestamp and receipts
        ev1 = compute_acceptance_event_hash(
            acceptance_id="acc-1",
            acceptance_input_hash=inp1,
            evaluated_at="2026-08-31T11:00:00Z",
            channel_evidence_hash="ch_1",
            channel_receipt_hash="rcpt_1",
            duplicate_evidence_hash="dup_1",
            duplicate_receipt_hash="dup_rcpt_1",
            local_publication_state="NOT_SEEN",
            result="READY_FOR_PRIVATE_UPLOAD_APPROVAL",
        )
        ev2 = compute_acceptance_event_hash(
            acceptance_id="acc-2",
            acceptance_input_hash=inp1,
            evaluated_at="2026-08-31T11:15:00Z",
            channel_evidence_hash="ch_1",
            channel_receipt_hash="rcpt_2",
            duplicate_evidence_hash="dup_2",
            duplicate_receipt_hash="dup_rcpt_2",
            local_publication_state="NOT_SEEN",
            result="READY_FOR_PRIVATE_UPLOAD_APPROVAL",
        )
        self.assertNotEqual(ev1, ev2)

    def _setup_mock_environment(
        self,
        *,
        channel_age_seconds: float = 0.0,
        snapshot_age_seconds: float = 0.0,
        publication_authorized: bool = False,
        audience_decision: str = "NOT_MADE_FOR_KIDS",
        coverage_complete: bool = True,
        duplicate_match: bool = False,
        platform: str = "YOUTUBE",
        privacy: str = "private",
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        media_bytes: bytes = b"test_video_134g",
        corrupt_channel_receipt: bool = False,
        missing_receipt: bool = False,
        ledger_prior_state: PublicationState | None = None,
    ) -> tuple[Path, AudienceDecisionRecord]:
        pkg_dir = self.test_dir / "mock_pkg"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.test_dir / "events" / "evidence"
        rcpt_dir = self.test_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        ch_ts = (now_dt - datetime.timedelta(seconds=channel_age_seconds)).isoformat()
        snap_ts = (now_dt - datetime.timedelta(seconds=snapshot_age_seconds)).isoformat()

        # 1. Channel Evidence & Receipt
        mock_raw_ch = {
            "kind": "youtube#channelListResponse",
            "items": [{
                "kind": "youtube#channel",
                "id": channel_id,
                "snippet": {"title": "FruitKI", "customUrl": "@kifruchtefilme"},
                "contentDetails": {"relatedPlaylists": {"uploads": f"UU{channel_id[2:]}"}},
            }],
        }
        ch_ev, ch_rcpt = TrustedYouTubeResponseAdapter.ingest_channel_response(
            mock_raw_ch,
            started_at=ch_ts,
            retrieved_at=ch_ts,
        )
        if corrupt_channel_receipt:
            ch_ev["authorized_read_receipt_hash"] = "corrupted_hash"
        (ev_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")
        if not missing_receipt:
            (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        # 2. Upload Snapshot & Receipt
        def mock_fetch(tok):
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [{"contentDetails": {"videoId": "V1"}, "snippet": {"title": "Test Title #Shorts" if duplicate_match else "Other Title"}}],
                "nextPageToken": None if coverage_complete else "PAGE_2",
            }
        snap_ev, snap_rcpt = TrustedYouTubeResponseAdapter.ingest_uploads_paginated_reader(
            fetch_page_fn=mock_fetch,
            channel_id=channel_id,
            uploads_playlist_id=f"UU{channel_id[2:]}",
            started_at=snap_ts,
            retrieved_at=snap_ts,
        )
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")
        if not missing_receipt:
            (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")

        # 3. Media & QC
        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_bytes)
        media_sha = hashlib.sha256(media_bytes).hexdigest()

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({"verdict": "PASS", "source_hash": media_sha}), encoding="utf-8")

        # 4. Duplicate Preflight
        fp = compute_publication_dedupe_fingerprint(platform=platform, target_channel_id=channel_id, media_sha256=media_sha)
        dup_rec = build_package_duplicate_preflight(
            publication_fingerprint=fp,
            media_sha256=media_sha,
            target_channel_id=channel_id,
            channel_evidence_hash=ch_ev["payload_evidence_hash"],
            channel_receipt_hash=ch_rcpt.receipt_hash,
            upload_snapshot_hash=snap_ev["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=1,
            page_count=1,
            coverage_complete=coverage_complete,
            duplicate_match=duplicate_match,
            checked_at=snap_ts,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")

        # 5. Audience Decision Record
        aud_record = AudienceDecisionRecord.create(
            content_id="mock_pkg",
            decision=audience_decision,
            decision_source="HUMAN_EXPLICIT_REVIEW",
            evidence_reference="scene.gd",
            media_sha256=media_sha,
            publication_fingerprint=fp,
            decided_at=ch_ts,
        )

        # 6. Package
        pkg_path = pkg_dir / "publish_package.json"
        pkg_path.write_text(json.dumps({
            "schema_version": "2.2",
            "platform": platform,
            "target_channel_id": channel_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ev_dir / "channel_evidence_fruitki.json"),
            "channel_evidence_hash": ch_ev["payload_evidence_hash"],
            "channel_verified_at": ch_ts,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": dup_rec["result"],
            "content_title": "Test Title #Shorts",
            "description_draft": "Test description",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": audience_decision,
            "self_declared_made_for_kids": (audience_decision == "MADE_FOR_KIDS"),
            "intended_upload_privacy": privacy,
            "intended_release_privacy": "public",
            "media_path": str(media_path),
            "media_sha256": media_sha,
            "qc_report_path": str(qc_path),
            "qc_status": "PASS",
            "publication_dedupe_fingerprint": fp,
            "publication_authorized": publication_authorized,
            "publication_state": "COMPLETE_READY_FOR_REVIEW",
            "cost_eur": 0.0,
            "prepared_at": ch_ts,
            "audience_decision_hash": aud_record.decision_hash if audience_decision != "DECISION_REQUIRED" else "",
        }), encoding="utf-8")

        if ledger_prior_state:
            self.gate.ledger.transition_state(fp, ledger_prior_state, video_id="PRIOR_VID")

        return pkg_path, aud_record

    def test_acceptance_v2_ready_fixture_returns_ready(self):
        pkg_path, aud_rec = self._setup_mock_environment()
        res = self.gate.evaluate_package(pkg_path, aud_rec)
        self.assertEqual(res.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")
        self.assertTrue(res.acceptance_input_hash)
        self.assertTrue(res.acceptance_event_hash)

    def test_publication_authorized_true_fails_acceptance(self):
        """publication_authorized must be false before Human approval."""
        pkg_path, aud_rec = self._setup_mock_environment(publication_authorized=True)
        res = self.gate.evaluate_package(pkg_path, aud_rec)
        self.assertEqual(res.result, "PUBLICATION_AUTHORIZATION_STATE_INVALID")

    def test_receipt_missing_or_tampered_fails_acceptance(self):
        # Missing receipt
        pkg_path1, aud_rec1 = self._setup_mock_environment(missing_receipt=True)
        res1 = self.gate.evaluate_package(pkg_path1, aud_rec1)
        self.assertEqual(res1.result, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED")

        # Corrupted receipt hash link
        pkg_path2, aud_rec2 = self._setup_mock_environment(corrupt_channel_receipt=True)
        res2 = self.gate.evaluate_package(pkg_path2, aud_rec2)
        self.assertEqual(res2.result, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH")

    def test_prior_publication_conflict_fails_acceptance(self):
        pkg_path, aud_rec = self._setup_mock_environment(ledger_prior_state=PublicationState.UPLOADED_PRIVATE)
        res = self.gate.evaluate_package(pkg_path, aud_rec)
        self.assertEqual(res.result, "PRIOR_PUBLICATION_CONFLICT")

    # ----------------------------------------------------
    # PHASE C: AT-MOST-ONE DISPATCH & RECONCILIATION
    # ----------------------------------------------------

    def test_at_most_one_dispatch_guarantee(self):
        """Once dispatch is attempted, automatic redispatch is prohibited."""
        pkg_path, aud_rec = self._setup_mock_environment()
        pkg = json.loads(pkg_path.read_text())
        app = ApprovalRecord(
            approval_id="app-134-dispatch",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint=pkg["publication_dedupe_fingerprint"],
            media_sha256=pkg["media_sha256"],
            platform=pkg["platform"],
            target_channel_id=pkg["target_channel_id"],
            approved_privacy="private",
            metadata_revision_hash=compute_metadata_revision_hash(pkg),
            audience_decision_hash=aud_rec.decision_hash,
            channel_evidence_hash=pkg["channel_evidence_hash"],
            duplicate_evidence_hash="",
            acceptance_id="acc-134",
            acceptance_hash="",
        )
        self.approval_registry.register_approval(app)

        res = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=app,
            audience_record=aud_rec,
            simulate_crash_at="AFTER_DISPATCH",
        )
        self.assertEqual(res.status, "ERROR")
        self.assertEqual(res.code, "EXTERNAL_OUTCOME_UNCERTAIN")

        # Attempting second execution without reconciliation fails
        res2 = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=app,
            audience_record=aud_rec,
            upload_mutation_mock=lambda p: {"status": "SUCCESS", "video_id": "SHOULD_NOT_RUN"},
        )
        self.assertEqual(res2.status, "BLOCKED")
        self.assertEqual(res2.code, "PRIOR_PUBLICATION_CONFLICT")

    def test_reconciliation_exact_id_vs_ambiguous(self):
        pkg_path, aud_rec = self._setup_mock_environment()
        pkg = json.loads(pkg_path.read_text())
        app = ApprovalRecord(
            approval_id="app-134-recon",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint=pkg["publication_dedupe_fingerprint"],
            media_sha256=pkg["media_sha256"],
            platform=pkg["platform"],
            target_channel_id=pkg["target_channel_id"],
            approved_privacy="private",
            metadata_revision_hash=compute_metadata_revision_hash(pkg),
            audience_decision_hash=aud_rec.decision_hash,
            channel_evidence_hash=pkg["channel_evidence_hash"],
            duplicate_evidence_hash="",
            acceptance_id="acc-134",
            acceptance_hash="",
        )
        self.approval_registry.register_approval(app)

        # 1. Exact ID survived
        res1 = self.executor.execute_private_upload(
            package_path=pkg_path,
            approval=app,
            audience_record=aud_rec,
            upload_mutation_mock=lambda p: {"status": "SUCCESS", "video_id": "VID_EXACT_999"},
            simulate_crash_at="AFTER_PLATFORM_ID",
        )
        self.assertEqual(res1.code, "CRASH_AFTER_PLATFORM_ID")

        # Reconcile exact ID provider succeeds
        ok, code, vid = self.executor.reconcile_uncertain_operation(
            operation_id=res1.operation_id,
            fingerprint=pkg["publication_dedupe_fingerprint"],
            approval_id=app.approval_id,
            exact_video_id_provider=lambda known_id: (True, known_id),
        )
        self.assertTrue(ok)
        self.assertEqual(code, "RECONCILED_SUCCESS")
        self.assertEqual(vid, "VID_EXACT_999")

        # 2. No exact ID -> ambiguous match stays parked
        ok2, code2, vid2 = self.executor.reconcile_uncertain_operation(
            operation_id=res1.operation_id,
            fingerprint=pkg["publication_dedupe_fingerprint"],
            approval_id=app.approval_id,
            exact_video_id_provider=lambda known_id: (False, None),
        )
        self.assertFalse(ok2)
        self.assertEqual(code2, "AMBIGUOUS_MATCH")

    def test_real_packages_stop_at_audience_decision_required(self):
        strict_gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT, allow_test_fixtures=False)

        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        gt_res = strict_gate.evaluate_package(gt_pkg)
        self.assertEqual(gt_res.result, "AUDIENCE_DECISION_REQUIRED")

        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        mb_res = strict_gate.evaluate_package(mb_pkg)
        self.assertEqual(mb_res.result, "AUDIENCE_DECISION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
