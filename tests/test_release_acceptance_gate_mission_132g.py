#!/usr/bin/env python3
"""Targeted unit tests for Mission 132G: Real Read Provenance + Release Acceptance Gate."""

from __future__ import annotations

import datetime
import hashlib
import json
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
from scripts.publication_approval import (
    AppendOnlyApprovalLedger,
    ApprovalRecord,
    ApprovalState,
    AudienceDecisionRecord,
    AudienceDecisionState,
    compute_metadata_revision_hash,
)
from scripts.publication_engine import (
    PublicationLedger,
    PublicationState,
)
from scripts.release_acceptance_gate import (
    AcceptanceResult,
    ReleaseAcceptanceGate,
    derive_approval_state,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestReleaseAcceptanceGateMission132G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_132g_test_"))
        self.gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_environment(
        self,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        media_bytes: bytes = b"mock_video_bytes_mission_132g",
        audience_decision: str = "NOT_MADE_FOR_KIDS",
        channel_age_seconds: float = 0.0,
        snapshot_age_seconds: float = 0.0,
        provenance_source: str = ProvenanceSource.ACTUAL_PROVIDER_READ.value,
        coverage_complete: bool = True,
        duplicate_match: bool = False,
    ) -> tuple[Path, AudienceDecisionRecord]:
        pkg_dir = self.test_dir / "golden_trophy_short"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        ev_dir = self.test_dir / "events" / "evidence"
        rcpt_dir = self.test_dir / "events" / "receipts"
        ev_dir.mkdir(parents=True, exist_ok=True)
        rcpt_dir.mkdir(parents=True, exist_ok=True)

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        ch_ts = (now_dt - datetime.timedelta(seconds=channel_age_seconds)).isoformat()
        snap_ts = (now_dt - datetime.timedelta(seconds=snapshot_age_seconds)).isoformat()

        # 1. Channel Evidence & Receipt
        if provenance_source == ProvenanceSource.ACTUAL_PROVIDER_READ.value:
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
        else:
            ch_ev, ch_rcpt = build_channel_evidence_package(
                channel_id=channel_id,
                channel_handle="@kifruchtefilme",
                channel_title="FruitKI",
                provenance_source=provenance_source,
                retrieved_at=ch_ts,
                started_at=ch_ts,
            )
        (ev_dir / "channel_evidence_fruitki.json").write_text(json.dumps(ch_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{ch_rcpt.receipt_id}.json").write_text(json.dumps(ch_rcpt.to_dict(), indent=2), encoding="utf-8")

        # 2. Upload Snapshot Evidence & Receipt
        if provenance_source == ProvenanceSource.ACTUAL_PROVIDER_READ.value:
            mock_fetch = lambda tok: {
                "kind": "youtube#playlistItemListResponse",
                "items": [{"contentDetails": {"videoId": "V1"}}, {"contentDetails": {"videoId": "V2"}}],
                "nextPageToken": None if coverage_complete else "PAGE_2",
            }
            snap_ev, snap_rcpt = TrustedYouTubeResponseAdapter.ingest_uploads_paginated_reader(
                fetch_page_fn=mock_fetch,
                channel_id=channel_id,
                uploads_playlist_id=f"UU{channel_id[2:]}",
                started_at=snap_ts,
                retrieved_at=snap_ts,
            )
        else:
            snap_ev, snap_rcpt = build_upload_snapshot_evidence_package(
                channel_id=channel_id,
                uploads_playlist_id=f"UU{channel_id[2:]}",
                video_ids=["V1", "V2"],
                provenance_source=provenance_source,
                coverage_complete=coverage_complete,
                retrieved_at=snap_ts,
                started_at=snap_ts,
            )
        (ev_dir / "youtube_uploads_snapshot_fruitki.json").write_text(json.dumps(snap_ev, indent=2), encoding="utf-8")
        (rcpt_dir / f"{snap_rcpt.receipt_id}.json").write_text(json.dumps(snap_rcpt.to_dict(), indent=2), encoding="utf-8")

        # 3. Media & QC
        media_path = pkg_dir / "render.mp4"
        media_path.write_bytes(media_bytes)
        media_sha = hashlib.sha256(media_bytes).hexdigest()

        qc_path = pkg_dir / "qc_report.json"
        qc_path.write_text(json.dumps({"verdict": "PASS", "source_hash": media_sha}), encoding="utf-8")

        # 4. Duplicate Preflight
        fp = compute_publication_dedupe_fingerprint(
            platform="YOUTUBE", target_channel_id=channel_id, media_sha256=media_sha
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
            coverage_complete=coverage_complete,
            duplicate_match=duplicate_match,
            checked_at=snap_ts,
        )
        dup_ev_path = ev_dir / f"duplicate_preflight_{fp[:16]}.json"
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2), encoding="utf-8")

        # 5. Audience Decision Record
        aud_record = AudienceDecisionRecord.create(
            content_id="golden_trophy_short",
            decision=audience_decision,
            decision_source="HUMAN_EXPLICIT_REVIEW",
            evidence_reference="strawberry_golden_trophy.gd",
            media_sha256=media_sha,
            publication_fingerprint=fp,
            decided_at=ch_ts,
        )

        # 6. Package
        pkg_path = pkg_dir / "publish_package.json"
        pkg_path.write_text(json.dumps({
            "schema_version": "2.2",
            "platform": "YOUTUBE",
            "target_channel_id": channel_id,
            "target_channel_handle": "@kifruchtefilme",
            "token_reference": "fruitki-test",
            "channel_evidence_path": str(ev_dir / "channel_evidence_fruitki.json"),
            "channel_evidence_hash": ch_ev["payload_evidence_hash"],
            "channel_verified_at": ch_ts,
            "duplicate_preflight_path": str(dup_ev_path),
            "duplicate_preflight_result": dup_rec["result"],
            "content_title": "Wer kriegt die goldene Trophäe? 🏆🍓🥝 #Shorts",
            "description_draft": "Test description draft",
            "tags": ["FruitKI", "Shorts"],
            "hashtags": ["#Shorts", "#FruitKI"],
            "category_id": "22",
            "audience_decision": audience_decision,
            "self_declared_made_for_kids": (audience_decision == "MADE_FOR_KIDS"),
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
            "prepared_at": ch_ts,
            "audience_decision_hash": aud_record.decision_hash if audience_decision != "DECISION_REQUIRED" else "",
        }), encoding="utf-8")

        return pkg_path, aud_record

    def test_fixture_ready_returns_ready_for_private_upload_approval(self):
        pkg_path, aud_record = self._create_mock_environment(audience_decision="NOT_MADE_FOR_KIDS")
        res = self.gate.evaluate_package(pkg_path, aud_record)
        self.assertEqual(res.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")
        self.assertTrue(res.acceptance_hash)
        self.assertEqual(res.expected_cost_eur, 0.0)

    def test_unresolved_audience_decision_blocks(self):
        pkg_path, _ = self._create_mock_environment(audience_decision="DECISION_REQUIRED")
        res = self.gate.evaluate_package(pkg_path, None)
        self.assertEqual(res.result, "AUDIENCE_DECISION_REQUIRED")

    def test_audience_asset_mismatch_blocks(self):
        pkg_path, aud_record = self._create_mock_environment(audience_decision="NOT_MADE_FOR_KIDS")
        mismatched_aud = AudienceDecisionRecord.create(
            content_id="other_content",
            decision="NOT_MADE_FOR_KIDS",
            decision_source="HUMAN",
            evidence_reference="test",
            media_sha256="wrong_media_sha",
            publication_fingerprint="wrong_fp",
        )
        res = self.gate.evaluate_package(pkg_path, mismatched_aud)
        self.assertEqual(res.result, "AUDIENCE_DECISION_ASSET_MISMATCH")

    def test_local_synthetic_provenance_rejected(self):
        pkg_path, aud_record = self._create_mock_environment(
            provenance_source=ProvenanceSource.LOCAL_DERIVED.value
        )
        strict_gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        res = strict_gate.evaluate_package(pkg_path, aud_record)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED")

    def test_stale_channel_evidence_blocks(self):
        pkg_path, aud_record = self._create_mock_environment(channel_age_seconds=90000.0)
        res = self.gate.evaluate_package(pkg_path, aud_record)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_STALE")

    def test_stale_duplicate_snapshot_blocks(self):
        pkg_path, aud_record = self._create_mock_environment(snapshot_age_seconds=1200.0)
        res = self.gate.evaluate_package(pkg_path, aud_record)
        self.assertEqual(res.result, "DUPLICATE_CHECK_STALE")

    def test_incomplete_coverage_blocks(self):
        pkg_path, aud_record = self._create_mock_environment(coverage_complete=False)
        res = self.gate.evaluate_package(pkg_path, aud_record)
        self.assertIn(res.result, {"DUPLICATE_CHECK_INCOMPLETE", "PLATFORM_METADATA_CHECK_INCOMPLETE"})

    def test_duplicate_metadata_match_blocks(self):
        pkg_path, aud_record = self._create_mock_environment(duplicate_match=True)
        res = self.gate.evaluate_package(pkg_path, aud_record)
        self.assertIn(res.result, {"DUPLICATE_METADATA_MATCH_FOUND", "PLATFORM_METADATA_MATCH_FOUND"})

    def test_prior_publication_conflict_blocks(self):
        pkg_path, aud_record = self._create_mock_environment()
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
        fp = pkg_data["publication_dedupe_fingerprint"]

        # Record prior publication in ledger
        self.gate.ledger.transition_state(fp, PublicationState.UPLOADED_PRIVATE, video_id="EXISTING_VID_1")
        res = self.gate.evaluate_package(pkg_path, aud_record)
        self.assertEqual(res.result, "PRIOR_PUBLICATION_CONFLICT")

    def test_acceptance_hash_determinism_and_sensitivity(self):
        pkg_path, aud_record = self._create_mock_environment()
        fixed_ts = "2026-08-31T11:00:00Z"
        res1 = self.gate.evaluate_package(pkg_path, aud_record, evaluated_at=fixed_ts)
        res2 = self.gate.evaluate_package(pkg_path, aud_record, evaluated_at=fixed_ts)
        self.assertEqual(res1.acceptance_hash, res2.acceptance_hash)

        # Modifying metadata changes acceptance hash
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
        pkg_data["content_title"] = "Modified Title #Shorts"
        pkg_path.write_text(json.dumps(pkg_data), encoding="utf-8")
        res_mod = self.gate.evaluate_package(pkg_path, aud_record, evaluated_at=fixed_ts)
        self.assertNotEqual(res1.acceptance_hash, res_mod.acceptance_hash)

    def test_ledger_derived_approval_state(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        approval_id = "app-test-derive-1"

        # Initially active
        state0 = derive_approval_state(approval_id, ledger, initial_record_state="ACTIVE")
        self.assertEqual(state0, "ACTIVE")

        # Consumed in ledger
        ledger.record_event(
            approval_id=approval_id,
            approval_state="CONSUMED",
            publication_fingerprint="fp-1",
            action="PRIVATE_UPLOAD",
            reason="Confirmed upload",
        )
        state1 = derive_approval_state(approval_id, ledger, initial_record_state="ACTIVE")
        self.assertEqual(state1, "CONSUMED")

        # Revoked in ledger
        ledger.record_event(
            approval_id=approval_id,
            approval_state="REVOKED",
            publication_fingerprint="fp-1",
            action="PRIVATE_UPLOAD",
            reason="User revoked",
        )
        state2 = derive_approval_state(approval_id, ledger, initial_record_state="ACTIVE")
        self.assertEqual(state2, "REVOKED")

    def test_real_packages_stop_at_audience_decision_required(self):
        real_gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT)

        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        gt_res = real_gate.evaluate_package(gt_pkg)
        self.assertEqual(gt_res.result, "AUDIENCE_DECISION_REQUIRED")

        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        mb_res = real_gate.evaluate_package(mb_pkg)
        self.assertEqual(mb_res.result, "AUDIENCE_DECISION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
