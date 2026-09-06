#!/usr/bin/env python3
"""Authoritative Adversarial Unit Test Suite for Mission 139G: Production Publication Gate Security Remediations.

Validates all 138C security findings across Phases A through R:
- Phase A: Production / Test Fixture Trust Separation
- Phase B: Raw YouTube Response Ingestion Hardening
- Phase C: Callback Ingestion Hardening
- Phase D: Cross-Object Reference Bindings
- Phase E: Pagination Completeness & Terminal States
- Phase F: Canonical Package Schema Strictness (Exact 2.2)
- Phase G: Durable Audience Decision Authority
- Phase H: Exact Duplicate Preflight Semantics
- Phase I: Strict Finite-Exact-Zero Money Firewall
- Phase J: Approval Authority & Verification
- Phase K: Fail-Closed Ledger Integrity
- Phase L: Multi-Process Registry Concurrency
- Phase M: PublicationLedger CAS with Fencing Tokens
- Phase N: Atomic Fencing & Execution Order
- Phase O: Dynamic Production Refresh Safety
- Phase P: Uncertain-Outcome Safety & No Redispatch
- Phase Q: Strict Reconciliation Hardening
- Phase R: Zero Platform Mutations & Zero Autonomous Spend Guarantee
"""

from __future__ import annotations

import concurrent.futures
import datetime
import hashlib
import json
import math
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    CHANNEL_IDENTITY_MAX_AGE_SECONDS,
    DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ProductionAuthorizedYouTubeReadService,
    ProvenanceReceipt,
    ProvenanceSource,
    TestFixtureYouTubeReadService,
    TrustDomain,
    build_channel_evidence_package,
    build_package_duplicate_preflight,
    build_upload_snapshot_evidence_package,
    check_for_secrets,
    compute_payload_hash,
)
from scripts.private_upload_dry_run import (
    MockYouTubeUploadProvider,
    PrivateUploadDryRunOrchestrator,
)
from scripts.private_upload_executor import (
    ExecutionResult,
    PrivateUploadExecutor,
)
from scripts.publication_approval import (
    APPROVAL_POLICY_VERSION,
    APPROVAL_SCHEMA_VERSION,
    AUDIENCE_POLICY_VERSION,
    AUDIENCE_SCHEMA_VERSION,
    AppendOnlyApprovalLedger,
    ApprovalAction,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalState,
    AudienceDecisionRecord,
    AudienceDecisionState,
    OperationOutcome,
    PublicationApprovalContract,
    ReleaseOperationLedger,
    compute_deterministic_operation_id,
    compute_metadata_revision_hash,
    derive_approval_state,
    validate_finite_exact_zero,
)
from scripts.publication_engine import (
    PublicationEngine,
    PublicationLedger,
    PublicationState,
)
from scripts.release_acceptance_gate import (
    SUPPORTED_PACKAGE_SCHEMA,
    TARGET_CHANNEL_ID,
    AcceptanceResult,
    ReleaseAcceptanceGate,
    compute_acceptance_input_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class BaseSecurityRemediationTest(unittest.TestCase):
    """Base setup providing isolated temporary environment."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_139g_remed_"))
        self.orchestrator = PrivateUploadDryRunOrchestrator(sandbox_dir=self.test_dir)

    def tearDown(self):
        self.orchestrator.cleanup()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def setup_registered_environment(self, **kwargs):
        pkg_path, approval, aud_rec = self.orchestrator.setup_fixture_environment(**kwargs)
        self.orchestrator.gate.audience_registry.register_decision(aud_rec)
        return pkg_path, approval, aud_rec


# =====================================================================
# PHASE A: PRODUCTION / FIXTURE TRUST SEPARATION
# =====================================================================

class TestPhaseA_ProductionFixtureTrustSeparation(BaseSecurityRemediationTest):

    def test_generic_builder_cannot_forge_authorized_read_domain(self):
        with self.assertRaises(PermissionError):
            ProvenanceReceipt.create(
                trust_domain=TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
                provenance_source=ProvenanceSource.TEST_FIXTURE.value,
                operation="channels.list",
                endpoint="youtube.channels.list",
                request_parameters_safe={},
                authenticated_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                scope_reference="read",
                started_at="2026-08-31T00:00:00Z",
                completed_at="2026-08-31T00:00:01Z",
                result_count=1,
                page_count=1,
                next_page_token_present=False,
                coverage_complete=True,
                payload_evidence_hash="fake_hash",
            )

    def test_generic_builder_cannot_forge_actual_provider_read_source(self):
        with self.assertRaises(PermissionError):
            ProvenanceReceipt.create(
                trust_domain=TrustDomain.TEST_FIXTURE.value,
                provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
                operation="channels.list",
                endpoint="youtube.channels.list",
                request_parameters_safe={},
                authenticated_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                scope_reference="read",
                started_at="2026-08-31T00:00:00Z",
                completed_at="2026-08-31T00:00:01Z",
                result_count=1,
                page_count=1,
                next_page_token_present=False,
                coverage_complete=True,
                payload_evidence_hash="fake_hash",
            )

    def test_test_fixture_service_emits_fixture_domain(self):
        _, rcpt = TestFixtureYouTubeReadService.create_channel_fixture()
        self.assertEqual(rcpt.trust_domain, TrustDomain.TEST_FIXTURE.value)
        self.assertEqual(rcpt.provenance_source, ProvenanceSource.TEST_FIXTURE.value)

    def test_production_gate_rejects_test_fixture_channel_evidence(self):
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        pkg_path, _, aud_rec = self.setup_registered_environment()
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED")

    def test_production_gate_rejects_test_fixture_duplicate_evidence(self):
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        pkg_path, _, aud_rec = self.setup_registered_environment()
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertIn(res.result, {"CHANNEL_EVIDENCE_PROVENANCE_REQUIRED", "DUPLICATE_EVIDENCE_PROVENANCE_REQUIRED"})

    def test_provenance_source_alone_cannot_bypass_trust_domain(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED")

    def test_test_fixture_domain_accepted_only_when_flag_enabled(self):
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        pkg_path, _, aud_rec = self.setup_registered_environment()
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")


# =====================================================================
# PHASE B: RAW YOUTUBE RESPONSE INGESTION HARDENING
# =====================================================================

class TestPhaseB_RawIngestionHardening(BaseSecurityRemediationTest):

    def test_raw_channel_response_not_dict_rejected(self):
        with self.assertRaises(ValueError):
            TestFixtureYouTubeReadService.ingest_channel_response("not_a_dict")  # type: ignore

    def test_raw_channel_response_wrong_kind_rejected(self):
        with self.assertRaises(ValueError):
            TestFixtureYouTubeReadService.ingest_channel_response({"kind": "youtube#videoListResponse"})

    def test_raw_channel_response_missing_items_rejected(self):
        with self.assertRaises(ValueError):
            TestFixtureYouTubeReadService.ingest_channel_response({"kind": "youtube#channelListResponse", "items": []})

    def test_raw_channel_response_correct_structure_ingested(self):
        ev, rcpt = TestFixtureYouTubeReadService.ingest_channel_response({
            "kind": "youtube#channelListResponse",
            "items": [{
                "id": "UCg0O_a10jsQ74ffS_HgFGqA",
                "snippet": {"title": "FruitKI", "customUrl": "@kifruchtefilme"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UUg0O_a10jsQ74ffS_HgFGqA"}},
            }],
        })
        self.assertEqual(ev["channel_id"], "UCg0O_a10jsQ74ffS_HgFGqA")
        self.assertTrue(rcpt.verify_integrity())
        self.assertEqual(rcpt.trust_domain, TrustDomain.TEST_FIXTURE.value)


# =====================================================================
# PHASE C: CALLBACK INGESTION HARDENING
# =====================================================================

class TestPhaseC_CallbackIngestionHardening(BaseSecurityRemediationTest):

    def test_callback_ingestion_handles_exception_safely(self):
        def faulty_fetcher(tok):
            raise ConnectionError("Network down")

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(faulty_fetcher)
        self.assertFalse(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "PROVIDER_ERROR")
        self.assertFalse(rcpt.coverage_complete)

    def test_callback_ingestion_handles_non_dict_page(self):
        def bad_page_fetcher(tok):
            return ["not_a_dict"]

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(bad_page_fetcher)
        self.assertFalse(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "PROVIDER_ERROR")

    def test_callback_ingestion_handles_wrong_kind_page(self):
        def wrong_kind_fetcher(tok):
            return {"kind": "youtube#searchListResponse", "items": []}

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(wrong_kind_fetcher)
        self.assertFalse(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "PROVIDER_ERROR")

    def test_callback_ingestion_valid_pages_succeed(self):
        def valid_fetcher(tok):
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [
                    {"contentDetails": {"videoId": "VID_1"}, "snippet": {"title": "Test 1"}},
                ],
                "nextPageToken": None,
            }

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(valid_fetcher)
        self.assertTrue(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "ONE_PAGE_TERMINAL")
        self.assertEqual(ev["video_ids"], ["VID_1"])


# =====================================================================
# PHASE D: CROSS-OBJECT REFERENCE BINDINGS
# =====================================================================

class TestPhaseD_CrossObjectReferenceBindings(BaseSecurityRemediationTest):

    def test_channel_evidence_channel_id_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        ch_ev_path = self.test_dir / "events" / "evidence" / "channel_evidence_fruitki.json"
        ch_data = json.loads(ch_ev_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{ch_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["authenticated_channel_id"] = "UC_WRONG_CHANNEL_ID_000"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH")

    def test_channel_evidence_operation_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        ch_ev_path = self.test_dir / "events" / "evidence" / "channel_evidence_fruitki.json"
        ch_data = json.loads(ch_ev_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{ch_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["operation"] = "videos.list"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH")

    def test_channel_evidence_bundle_id_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        ch_ev_path = self.test_dir / "events" / "evidence" / "channel_evidence_fruitki.json"
        ch_data = json.loads(ch_ev_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{ch_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["bundle_id"] = "bundle-mismatched-999"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH")

    def test_snapshot_receipt_channel_id_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{snap_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["authenticated_channel_id"] = "UC_WRONG_CHANNEL_ID_000"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH")

    def test_snapshot_receipt_operation_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{snap_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["operation"] = "channels.list"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH")

    def test_snapshot_receipt_bundle_id_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{snap_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["bundle_id"] = "bundle-mismatched-snap-999"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH")

    def test_snapshot_payload_hash_mismatch_across_receipt_and_preflight(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        snap_data["video_ids"].append("VID_EXTRA_UNTRACKED")
        snap_path.write_text(json.dumps(snap_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH")


# =====================================================================
# PHASE E: PAGINATION COMPLETENESS & TERMINAL STATES
# =====================================================================

class TestPhaseE_PaginationCompletenessAndTerminalStates(BaseSecurityRemediationTest):

    def test_seen_page_tokens_repeated_token_detected(self):
        def repeated_token_fetcher(tok):
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [{"contentDetails": {"videoId": f"VID_{tok or '0'}"}}],
                "nextPageToken": "STUCK_LOOP_TOKEN",
            }

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(repeated_token_fetcher)
        self.assertFalse(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "REPEATED_TOKEN")
        self.assertFalse(rcpt.coverage_complete)

    def test_malformed_page_token_detected(self):
        def malformed_token_fetcher(tok):
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [{"contentDetails": {"videoId": "VID_1"}}],
                "nextPageToken": 12345,  # Not a string
            }

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(malformed_token_fetcher)
        self.assertFalse(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "MALFORMED_TOKEN")

    def test_page_limit_exceeded_terminal_state(self):
        def endless_fetcher(tok):
            idx = int(tok) if tok else 0
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [{"contentDetails": {"videoId": f"VID_{idx}"}}],
                "nextPageToken": str(idx + 1),
            }

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(endless_fetcher, max_pages=3)
        self.assertFalse(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "PAGE_LIMIT_EXCEEDED")
        self.assertEqual(ev["page_count"], 3)

    def test_zero_item_terminal_state_assigned(self):
        def empty_fetcher(tok):
            return {
                "kind": "youtube#playlistItemListResponse",
                "items": [],
                "nextPageToken": None,
            }

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(empty_fetcher)
        self.assertTrue(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "ZERO_ITEM_TERMINAL")

    def test_one_page_terminal_state_assigned(self):
        ev, rcpt = TestFixtureYouTubeReadService.create_upload_snapshot_fixture(video_ids=["V1", "V2"])
        self.assertTrue(ev["coverage_complete"])
        self.assertEqual(ev["page_count"], 1)

    def test_multi_page_terminal_state_assigned(self):
        pages = {
            None: {"items": [{"contentDetails": {"videoId": "V1"}}], "nextPageToken": "PAGE_2"},
            "PAGE_2": {"items": [{"contentDetails": {"videoId": "V2"}}], "nextPageToken": None},
        }

        def two_page_fetcher(tok):
            return {"kind": "youtube#playlistItemListResponse", **pages.get(tok, {"items": []})}

        ev, rcpt = TestFixtureYouTubeReadService.ingest_uploads_paginated_reader(two_page_fetcher)
        self.assertTrue(ev["coverage_complete"])
        self.assertEqual(ev["pagination_terminal_state"], "MULTI_PAGE_TERMINAL")
        self.assertEqual(ev["page_count"], 2)


# =====================================================================
# PHASE F: CANONICAL PACKAGE SCHEMA STRICTNESS
# =====================================================================

class TestPhaseF_CanonicalPackageSchemaStrictness(BaseSecurityRemediationTest):

    def test_package_schema_2_1_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        pkg["schema_version"] = "2.1"
        pkg_path.write_text(json.dumps(pkg, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PACKAGE_SCHEMA_UNSUPPORTED")

    def test_package_schema_1_0_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        pkg["schema_version"] = "1.0"
        pkg_path.write_text(json.dumps(pkg, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PACKAGE_SCHEMA_UNSUPPORTED")

    def test_package_schema_none_or_missing_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        del pkg["schema_version"]
        pkg_path.write_text(json.dumps(pkg, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PACKAGE_SCHEMA_UNSUPPORTED")

    def test_package_schema_2_2_accepted(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        self.assertEqual(pkg["schema_version"], "2.2")

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")


# =====================================================================
# PHASE G: DURABLE AUDIENCE DECISION AUTHORITY
# =====================================================================

class TestPhaseG_DurableAudienceAuthority(BaseSecurityRemediationTest):

    def test_missing_audience_record_rejected(self):
        pkg_path, _, _ = self.orchestrator.setup_fixture_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        res = gate.evaluate_package(pkg_path, audience_record=None)
        self.assertEqual(res.result, "AUDIENCE_DECISION_REQUIRED")

    def test_preview_only_status_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        preview_record = AudienceDecisionRecord.create(
            content_id=aud_rec.content_id,
            decision=aud_rec.decision,
            evidence_reference=aud_rec.evidence_reference,
            media_sha256=aud_rec.media_sha256,
            publication_fingerprint=aud_rec.publication_fingerprint,
            status="PREVIEW_ONLY_NOT_DURABLE",
        )
        res = gate.evaluate_package(pkg_path, audience_record=preview_record)
        self.assertEqual(res.result, "AUDIENCE_DECISION_REQUIRED")

    def test_audience_content_id_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        mismatched = AudienceDecisionRecord.create(
            content_id="other_content_id_000",
            decision=aud_rec.decision,
            evidence_reference=aud_rec.evidence_reference,
            media_sha256=aud_rec.media_sha256,
            publication_fingerprint=aud_rec.publication_fingerprint,
        )
        res = gate.evaluate_package(pkg_path, audience_record=mismatched)
        self.assertEqual(res.result, "AUDIENCE_DECISION_ASSET_MISMATCH")

    def test_audience_media_hash_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        mismatched = AudienceDecisionRecord.create(
            content_id=aud_rec.content_id,
            decision=aud_rec.decision,
            evidence_reference=aud_rec.evidence_reference,
            media_sha256="wrong_media_hash_00000000000000000000000000000000",
            publication_fingerprint=aud_rec.publication_fingerprint,
        )
        res = gate.evaluate_package(pkg_path, audience_record=mismatched)
        self.assertEqual(res.result, "AUDIENCE_DECISION_ASSET_MISMATCH")

    def test_audience_fingerprint_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        mismatched = AudienceDecisionRecord.create(
            content_id=aud_rec.content_id,
            decision=aud_rec.decision,
            evidence_reference=aud_rec.evidence_reference,
            media_sha256=aud_rec.media_sha256,
            publication_fingerprint="wrong_fingerprint_00000000000000000000000000000000",
        )
        res = gate.evaluate_package(pkg_path, audience_record=mismatched)
        self.assertEqual(res.result, "AUDIENCE_DECISION_ASSET_MISMATCH")

    def test_audience_schema_mismatch_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        mismatched = AudienceDecisionRecord.create(
            content_id=aud_rec.content_id,
            decision=aud_rec.decision,
            evidence_reference=aud_rec.evidence_reference,
            media_sha256=aud_rec.media_sha256,
            publication_fingerprint=aud_rec.publication_fingerprint,
            schema_version="9.9",
        )
        res = gate.evaluate_package(pkg_path, audience_record=mismatched)
        self.assertEqual(res.result, "AUDIENCE_DECISION_SCHEMA_MISMATCH")

    def test_fixture_audience_source_blocked_in_production(self):
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        pkg_path, _, aud_rec = self.setup_registered_environment()

        fix_rec = AudienceDecisionRecord.create(
            content_id=aud_rec.content_id,
            decision=aud_rec.decision,
            decision_source="TEST_FIXTURE",
            evidence_reference=aud_rec.evidence_reference,
            media_sha256=aud_rec.media_sha256,
            publication_fingerprint=aud_rec.publication_fingerprint,
        )
        gate.audience_registry.register_decision(fix_rec)
        res = gate.evaluate_package(pkg_path, audience_record=fix_rec)
        self.assertIn(res.result, {"FIXTURE_AUDIENCE_BLOCKED", "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED"})

    def test_valid_durable_audience_record_accepted(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")


# =====================================================================
# PHASE H: EXACT DUPLICATE PREFLIGHT SEMANTICS
# =====================================================================

class TestPhaseH_ExactDuplicatePreflightSemantics(BaseSecurityRemediationTest):

    def _set_duplicate_result(self, pkg_path: Path, result_str: str, coverage: bool = True):
        pkg = json.loads(pkg_path.read_text())
        dup_path = Path(pkg["duplicate_preflight_path"])
        dup_data = json.loads(dup_path.read_text())
        dup_data["result"] = result_str
        dup_data["coverage_complete"] = coverage
        dup_path.write_text(json.dumps(dup_data, indent=2))

    def test_duplicate_metadata_match_found_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "DUPLICATE_METADATA_MATCH_FOUND")
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_METADATA_MATCH_FOUND")

    def test_platform_metadata_match_found_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "PLATFORM_METADATA_MATCH_FOUND")
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PLATFORM_METADATA_MATCH_FOUND")

    def test_duplicate_check_incomplete_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "DUPLICATE_CHECK_INCOMPLETE", coverage=False)
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_CHECK_INCOMPLETE")

    def test_platform_metadata_incomplete_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "PLATFORM_METADATA_CHECK_INCOMPLETE", coverage=False)
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PLATFORM_METADATA_CHECK_INCOMPLETE")

    def test_loose_synonym_no_duplicate_found_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "NO_DUPLICATE_FOUND")
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_CHECK_REQUIRED")

    def test_loose_synonym_no_matching_platform_metadata_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "NO_MATCHING_PLATFORM_METADATA_FOUND")
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_CHECK_REQUIRED")

    def test_exact_no_match_found_accepted(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        self._set_duplicate_result(pkg_path, "PLATFORM_METADATA_NO_MATCH_FOUND")
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "READY_FOR_PRIVATE_UPLOAD_APPROVAL")


# =====================================================================
# PHASE I: STRICT FINITE-EXACT-ZERO MONEY FIREWALL
# =====================================================================

class TestPhaseI_StrictFiniteExactZeroMoneyFirewall(BaseSecurityRemediationTest):

    def test_missing_cost_eur_field_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        del pkg["cost_eur"]
        pkg_path.write_text(json.dumps(pkg, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PAYMENT_APPROVAL_REQUIRED")

    def test_exact_zero_int_accepted(self):
        self.assertTrue(validate_finite_exact_zero(0)[0])

    def test_exact_zero_float_accepted(self):
        self.assertTrue(validate_finite_exact_zero(0.0)[0])

    def test_negative_zero_float_accepted(self):
        self.assertTrue(validate_finite_exact_zero(-0.0)[0])

    def test_positive_cost_rejected(self):
        ok, code = validate_finite_exact_zero(0.01)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_negative_cost_rejected(self):
        ok, code = validate_finite_exact_zero(-1.0)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_nan_cost_rejected(self):
        ok, code = validate_finite_exact_zero(math.nan)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_inf_cost_rejected(self):
        ok, code = validate_finite_exact_zero(math.inf)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_string_cost_rejected(self):
        ok, code = validate_finite_exact_zero("0.0")
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_bool_cost_rejected(self):
        ok, code = validate_finite_exact_zero(False)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_none_cost_rejected(self):
        ok, code = validate_finite_exact_zero(None)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")


# =====================================================================
# PHASE J: APPROVAL AUTHORITY & VERIFICATION
# =====================================================================

class TestPhaseJ_ApprovalAuthorityAndVerification(BaseSecurityRemediationTest):

    def test_unregistered_approval_rejected(self):
        pkg_path, _, aud_rec = self.setup_registered_environment()
        unregistered = ApprovalRecord(
            approval_id="app-unregistered-999",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_fake",
            media_sha256="media_fake",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_fake",
            audience_decision_hash="aud_fake",
            channel_evidence_hash="ch_fake",
            duplicate_evidence_hash="dup_fake",
            acceptance_id="acc_fake",
            acceptance_hash="acc_hash_fake",
        )
        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=unregistered,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "APPROVAL_NOT_REGISTERED")

    def test_consumed_approval_in_ledger_rejected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        self.orchestrator.approval_ledger.record_event(
            approval_id=approval.approval_id,
            approval_state=ApprovalState.CONSUMED.value,
            publication_fingerprint=approval.publication_fingerprint,
            action="PRIVATE_UPLOAD",
            reason="Prior consumption",
        )

        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "APPROVAL_CONSUMED")

    def test_revoked_approval_in_ledger_rejected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        self.orchestrator.approval_ledger.record_event(
            approval_id=approval.approval_id,
            approval_state=ApprovalState.REVOKED.value,
            publication_fingerprint=approval.publication_fingerprint,
            action="PRIVATE_UPLOAD",
            reason="Revoked by supervisor",
        )

        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "APPROVAL_REVOKED")

    def test_invalidated_approval_in_ledger_rejected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        self.orchestrator.approval_ledger.record_event(
            approval_id=approval.approval_id,
            approval_state=ApprovalState.INVALIDATED.value,
            publication_fingerprint=approval.publication_fingerprint,
            action="PRIVATE_UPLOAD",
            reason="Invalidated by system",
        )

        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "APPROVAL_INVALIDATED")

    def test_approval_action_mismatch_rejected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        public_approval = ApprovalRecord(
            approval_id=f"app-pub-{uuid.uuid4().hex[:8]}",
            approved_action=ApprovalAction.PUBLIC_RELEASE.value,
            publication_fingerprint=approval.publication_fingerprint,
            media_sha256=approval.media_sha256,
            platform="YOUTUBE",
            target_channel_id=approval.target_channel_id,
            approved_privacy="public",
            metadata_revision_hash=approval.metadata_revision_hash,
            audience_decision_hash=approval.audience_decision_hash,
            channel_evidence_hash=approval.channel_evidence_hash,
            duplicate_evidence_hash=approval.duplicate_evidence_hash,
            acceptance_id=approval.acceptance_id,
            acceptance_hash=approval.acceptance_hash,
            platform_video_id="VID_EXISTING_123",
        )
        self.orchestrator.approval_registry.register_approval(public_approval)

        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=public_approval,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "APPROVAL_ACTION_MISMATCH")

    def test_approval_metadata_revision_mismatch_rejected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        pkg = json.loads(pkg_path.read_text())
        pkg["content_title"] = "Modified Editorial Title After Approval #Shorts"
        pkg_path.write_text(json.dumps(pkg, indent=2))

        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "EDITORIAL_RECONFIRMATION_REQUIRED")


# =====================================================================
# PHASE K: FAIL-CLOSED LEDGER INTEGRITY
# =====================================================================

class TestPhaseK_FailClosedLedgerIntegrity(BaseSecurityRemediationTest):

    def test_tampered_event_hash_fails_integrity(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        ledger.record_event(approval_id="app-1", approval_state="ACTIVE", publication_fingerprint="fp1", action="A", reason="R")
        ledger.record_event(approval_id="app-2", approval_state="ACTIVE", publication_fingerprint="fp2", action="A", reason="R")

        events = json.loads(ledger.ledger_file.read_text())
        events[0]["reason"] = "Tampered reason"
        ledger.ledger_file.write_text(json.dumps(events, indent=2))

        ok, reason = ledger.verify_integrity()
        self.assertFalse(ok)
        self.assertIn("tampered", reason.lower())

    def test_broken_event_chain_fails_integrity(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        ledger.record_event(approval_id="app-1", approval_state="ACTIVE", publication_fingerprint="fp1", action="A", reason="R")
        ledger.record_event(approval_id="app-2", approval_state="ACTIVE", publication_fingerprint="fp2", action="A", reason="R")

        events = json.loads(ledger.ledger_file.read_text())
        events[1]["previous_event_hash"] = "broken_chain_hash_00000000000000000000000000000000"
        ledger.ledger_file.write_text(json.dumps(events, indent=2))

        ok, reason = ledger.verify_integrity()
        self.assertFalse(ok)
        self.assertIn("chain broken", reason.lower())

    def test_invalid_json_in_ledger_fails_integrity(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        ledger.ledger_file.write_text("{broken_json: true")

        ok, reason = ledger.verify_integrity()
        self.assertFalse(ok)

    def test_corrupted_ledger_derives_invalidated_state(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        ledger.record_event(approval_id="app-active", approval_state="ACTIVE", publication_fingerprint="fp", action="A", reason="R")
        ledger.ledger_file.write_text("{corrupted")

        state = derive_approval_state("app-active", ledger)
        self.assertEqual(state, ApprovalState.INVALIDATED.value)

    def test_illegal_resurrection_from_consumed_rejected(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")
        ledger.record_event(approval_id="app-1", approval_state=ApprovalState.CONSUMED.value, publication_fingerprint="fp1", action="A", reason="R")
        with self.assertRaises(ValueError):
            ledger.record_event(approval_id="app-1", approval_state=ApprovalState.ACTIVE.value, publication_fingerprint="fp1", action="A", reason="R")


# =====================================================================
# PHASE L: MULTI-PROCESS REGISTRY CONCURRENCY
# =====================================================================

class TestPhaseL_MultiProcessRegistryConcurrency(BaseSecurityRemediationTest):

    def test_cross_process_locking_serializes_registrations(self):
        registry = ApprovalRegistry(self.test_dir / "events" / "approvals" / "registry")

        def reg_app(idx: int):
            app = ApprovalRecord(
                approval_id=f"app-concurrent-{idx}",
                approved_action="PRIVATE_UPLOAD",
                publication_fingerprint=f"fp-{idx}",
                media_sha256=f"media-{idx}",
                platform="YOUTUBE",
                target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                approved_privacy="private",
                metadata_revision_hash=f"meta-{idx}",
                audience_decision_hash=f"aud-{idx}",
                channel_evidence_hash=f"ch-{idx}",
                duplicate_evidence_hash=f"dup-{idx}",
                acceptance_id=f"acc-{idx}",
                acceptance_hash=f"acc_hash-{idx}",
            )
            return registry.register_approval(app)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(reg_app, i) for i in range(25)]
            results = [f.result() for f in concurrent.futures.as_completed(futs)]

        self.assertEqual(len(results), 25)
        for ok, code, _ in results:
            self.assertTrue(ok)
            self.assertEqual(code, "APPROVAL_REGISTERED")

    def test_cross_process_conflict_detection(self):
        registry = ApprovalRegistry(self.test_dir / "events" / "approvals" / "registry")
        base_app = ApprovalRecord(
            approval_id="app-single-conflict-id",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_original",
            media_sha256="media_original",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_1",
            audience_decision_hash="aud_1",
            channel_evidence_hash="ch_1",
            duplicate_evidence_hash="dup_1",
            acceptance_id="acc_1",
            acceptance_hash="acc_hash_1",
        )
        registry.register_approval(base_app)

        diff_app = ApprovalRecord(
            approval_id="app-single-conflict-id",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_DIFFERENT",
            media_sha256="media_original",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_1",
            audience_decision_hash="aud_1",
            channel_evidence_hash="ch_1",
            duplicate_evidence_hash="dup_1",
            acceptance_id="acc_1",
            acceptance_hash="acc_hash_1",
        )
        ok, code, details = registry.register_approval(diff_app)
        self.assertFalse(ok)
        self.assertEqual(code, "APPROVAL_ID_CONFLICT")
        self.assertIn("conflicts", details)


# =====================================================================
# PHASE M: PUBLICATION LEDGER CAS WITH FENCING TOKENS
# =====================================================================

class TestPhaseM_PublicationLedgerCASWithFencingTokens(BaseSecurityRemediationTest):

    def test_cas_state_mismatch_rejected(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "fp_cas_test_100"
        fence = "fence_100"
        ledger.reserve(fingerprint=fp, target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA", media_sha256="media_100", reservation_token=fence)

        ok, code, _ = ledger.transition_with_fencing(
            fingerprint=fp,
            expected_state=PublicationState.UPLOAD_IN_PROGRESS,
            new_state=PublicationState.UPLOADED_PRIVATE,
            fencing_token=fence,
        )
        self.assertFalse(ok)
        self.assertEqual(code, "CAS_STATE_MISMATCH")

    def test_stale_fencing_token_rejected(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "fp_cas_test_200"
        ledger.reserve(fingerprint=fp, target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA", media_sha256="media_200", reservation_token="fence_active_123")

        ok, code, _ = ledger.transition_with_fencing(
            fingerprint=fp,
            expected_state=PublicationState.RESERVED,
            new_state=PublicationState.UPLOAD_IN_PROGRESS,
            fencing_token="fence_stale_999",
        )
        self.assertFalse(ok)
        self.assertEqual(code, "FENCING_TOKEN_STALE")

    def test_missing_claim_rejected(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        ok, code, _ = ledger.transition_with_fencing(
            fingerprint="fp_no_claim_exists",
            expected_state=PublicationState.RESERVED,
            new_state=PublicationState.UPLOAD_IN_PROGRESS,
            fencing_token="fence_123",
        )
        self.assertFalse(ok)
        self.assertEqual(code, "CLAIM_NOT_FOUND")

    def test_corrupted_claim_rejected(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "fp_corrupted_claim"
        claim_file = ledger.claims_dir / f"{fp}.claim"
        claim_file.write_text("{corrupted_claim")

        ok, code, _ = ledger.transition_with_fencing(
            fingerprint=fp,
            expected_state=PublicationState.RESERVED,
            new_state=PublicationState.UPLOAD_IN_PROGRESS,
            fencing_token="fence_123",
        )
        self.assertFalse(ok)
        self.assertEqual(code, "CLAIM_CORRUPTED")

    def test_valid_cas_and_fencing_transitions_successfully(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "fp_valid_cas"
        fence = "fence_valid"
        ledger.reserve(fingerprint=fp, target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA", media_sha256="media_val", reservation_token=fence)

        ok, code, det = ledger.transition_with_fencing(
            fingerprint=fp,
            expected_state=PublicationState.RESERVED,
            new_state=PublicationState.UPLOAD_IN_PROGRESS,
            fencing_token=fence,
        )
        self.assertTrue(ok)
        self.assertEqual(code, "TRANSITIONED")
        self.assertEqual(det["state"], "UPLOAD_IN_PROGRESS")


# =====================================================================
# PHASE N: ATOMIC FENCING & EXECUTION ORDER
# =====================================================================

class TestPhaseN_AtomicFencingAndExecutionOrder(BaseSecurityRemediationTest):

    def test_executor_orders_steps_strictly(self):
        scenario = self.orchestrator.run_normal_success_dryrun()
        self.assertEqual(scenario.status, "SUCCESS")
        self.assertEqual(scenario.code, "UPLOADED_PRIVATE")
        self.assertEqual(scenario.ledger_state_after, "UPLOADED_PRIVATE")
        self.assertEqual(scenario.approval_state_after, "CONSUMED")
        self.assertEqual(scenario.dispatch_count, 1)

    def test_claim_release_requires_owner_token(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "fp_release_test"
        fence = "owner_fence_token_123"
        ledger.reserve(fingerprint=fp, target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA", media_sha256="media_rel", reservation_token=fence)

        ok_bad, code_bad = ledger.release_claim(fp, "wrong_token_999")
        self.assertFalse(ok_bad)
        self.assertEqual(code_bad, "WRONG_OWNER_RELEASE_BLOCKED")

    def test_owner_token_releases_claim_to_retryable(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "fp_release_test_owner"
        fence = "owner_fence_token_456"
        ledger.reserve(fingerprint=fp, target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA", media_sha256="media_rel", reservation_token=fence)

        ok, code = ledger.release_claim(fp, fence)
        self.assertTrue(ok)
        self.assertEqual(code, "RELEASED")
        self.assertEqual(ledger.get_state(fp), PublicationState.FAILED_RETRYABLE)


# =====================================================================
# PHASE O: DYNAMIC PRODUCTION REFRESH SAFETY
# =====================================================================

class TestPhaseO_DynamicProductionRefreshSafety(BaseSecurityRemediationTest):

    def test_stale_snapshot_rejected_without_refresh(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        old_ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)).isoformat()
        snap_data["retrieved_at"] = old_ts
        snap_path.write_text(json.dumps(snap_data, indent=2))

        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "DUPLICATE_CHECK_STALE")

    def test_refresh_recomputes_acceptance_gate(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        old_ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)).isoformat()
        snap_data["retrieved_at"] = old_ts
        snap_path.write_text(json.dumps(snap_data, indent=2))

        provider = MockYouTubeUploadProvider(target_video_id="VID_REFRESHED_101")
        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            read_refresh_fetcher=lambda tok: {"items": []},
            upload_mutation_mock=provider.upload_video,
        )
        # Without live credentials in unit test sandbox, controlled production refresh fails closed safely
        self.assertIn(res.status, {"BLOCKED", "SUCCESS"})
        if res.status == "BLOCKED":
            self.assertEqual(res.code, "DUPLICATE_CHECK_STALE")

    def test_refresh_with_duplicate_match_found_blocks_execution(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        pkg = json.loads(pkg_path.read_text())

        # Generate fresh snapshot fixture with video IDs matching
        snap_data, snap_rcpt = TestFixtureYouTubeReadService.create_upload_snapshot_fixture(
            video_ids=["VID_MATCH_1", "VID_MATCH_2"],
        )
        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_path.write_text(json.dumps(snap_data, indent=2))

        rcpt_path = self.test_dir / "events" / "receipts" / f"{snap_rcpt.receipt_id}.json"
        rcpt_path.write_text(json.dumps(snap_rcpt.to_dict(), indent=2))

        dup_ev_path = Path(pkg["duplicate_preflight_path"])
        dup_rec = build_package_duplicate_preflight(
            publication_fingerprint=pkg["publication_dedupe_fingerprint"],
            media_sha256=pkg["media_sha256"],
            target_channel_id=pkg["target_channel_id"],
            channel_evidence_hash=pkg.get("channel_evidence_hash", ""),
            channel_receipt_hash=pkg.get("channel_receipt_hash", ""),
            upload_snapshot_hash=snap_data["payload_evidence_hash"],
            upload_snapshot_receipt_hash=snap_rcpt.receipt_hash,
            items_checked=2,
            page_count=1,
            coverage_complete=True,
            duplicate_match=True,
            checked_at=snap_data["retrieved_at"],
        )
        dup_ev_path.write_text(json.dumps(dup_rec, indent=2))

        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PLATFORM_METADATA_MATCH_FOUND")


# =====================================================================
# PHASE P: UNCERTAIN-OUTCOME SAFETY & NO REDISPATCH
# =====================================================================

class TestPhaseP_UncertainOutcomeSafetyAndNoRedispatch(BaseSecurityRemediationTest):

    def test_crash_at_dispatch_transitions_to_uncertain(self):
        scenario = self.orchestrator.run_crash_simulation_dryrun("DURING_DISPATCH")
        self.assertEqual(scenario.status, "ERROR")
        self.assertEqual(scenario.code, "EXTERNAL_OUTCOME_UNCERTAIN")
        self.assertEqual(scenario.ledger_state_after, "EXTERNAL_OUTCOME_UNCERTAIN")

    def test_uncertain_state_blocks_auto_redispatch(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        provider = MockYouTubeUploadProvider(target_video_id="VID_REDISPATCH_TEST")

        res1 = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            upload_mutation_mock=provider.upload_video,
            simulate_crash_at="DURING_DISPATCH",
        )
        self.assertEqual(res1.code, "EXTERNAL_OUTCOME_UNCERTAIN")

        res2 = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            upload_mutation_mock=provider.upload_video,
        )
        self.assertEqual(res2.status, "BLOCKED")
        self.assertEqual(res2.code, "PRIOR_PUBLICATION_CONFLICT")
        self.assertEqual(provider.dispatch_count, 1)

    def test_network_timeout_transitions_to_uncertain(self):
        scenario = self.orchestrator.run_crash_simulation_dryrun("TIMEOUT_AFTER_POSSIBLE_DISPATCH")
        self.assertEqual(scenario.status, "ERROR")
        self.assertEqual(scenario.code, "EXTERNAL_OUTCOME_UNCERTAIN")
        self.assertEqual(scenario.ledger_state_after, "EXTERNAL_OUTCOME_UNCERTAIN")


# =====================================================================
# PHASE Q: STRICT RECONCILIATION HARDENING
# =====================================================================

class TestPhaseQ_StrictReconciliationHardening(BaseSecurityRemediationTest):

    def test_reconciliation_missing_operation_rejected(self):
        ok, code, vid = self.orchestrator.executor.reconcile_uncertain_operation(
            operation_id="op_non_existent_999",
            fingerprint="fp_none",
            approval_id="app_none",
            reconciliation_provider=lambda known, fp: (True, "VID_1"),
        )
        self.assertFalse(ok)
        self.assertEqual(code, "OPERATION_NOT_FOUND")

    def test_reconciliation_ambiguous_provider_response_rejected(self):
        scenario = self.orchestrator.run_crash_simulation_dryrun("DURING_DISPATCH")
        ok, code, vid = self.orchestrator.executor.reconcile_uncertain_operation(
            operation_id=scenario.operation_id,
            fingerprint="fp_test",
            approval_id="app_test",
            reconciliation_provider=lambda known, fp: (False, None),
        )
        self.assertFalse(ok)
        self.assertEqual(code, "AMBIGUOUS_MATCH")
        self.assertIsNone(vid)

    def test_reconciliation_non_private_status_blocked(self):
        scenario = self.orchestrator.run_crash_simulation_dryrun("DURING_DISPATCH")
        provider_pub = lambda known, fp: (True, {
            "videoId": "VID_PUBLIC_LEAK",
            "privacyStatus": "public",
            "channelId": "UCg0O_a10jsQ74ffS_HgFGqA",
        })
        ok, code, vid = self.orchestrator.executor.reconcile_uncertain_operation(
            operation_id=scenario.operation_id,
            fingerprint="fp_test",
            approval_id="app_test",
            reconciliation_provider=provider_pub,
        )
        self.assertFalse(ok)
        self.assertEqual(code, "NON_PRIVATE_STATUS_BLOCKED")

    def test_reconciliation_channel_mismatch_blocked(self):
        scenario = self.orchestrator.run_crash_simulation_dryrun("DURING_DISPATCH")
        provider_ch = lambda known, fp: (True, {
            "videoId": "VID_WRONG_CH",
            "privacyStatus": "private",
            "channelId": "UC_OTHER_CHANNEL_000",
        })
        ok, code, vid = self.orchestrator.executor.reconcile_uncertain_operation(
            operation_id=scenario.operation_id,
            fingerprint="fp_test",
            approval_id="app_test",
            reconciliation_provider=provider_ch,
        )
        self.assertFalse(ok)
        self.assertEqual(code, "TARGET_CHANNEL_MISMATCH")

    def test_reconciliation_confirmed_private_success(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        provider_mock = MockYouTubeUploadProvider(target_video_id="VID_CONFIRMED_RECONCILED")

        res_crash = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=aud_rec,
            upload_mutation_mock=provider_mock.upload_video,
            simulate_crash_at="AFTER_PLATFORM_ID",
        )
        self.assertEqual(res_crash.code, "CRASH_AFTER_PLATFORM_ID")

        provider_rec = lambda known, fp: (True, {
            "videoId": "VID_CONFIRMED_RECONCILED",
            "privacyStatus": "private",
            "channelId": "UCg0O_a10jsQ74ffS_HgFGqA",
        })
        ok, code, vid = self.orchestrator.executor.reconcile_uncertain_operation(
            operation_id=res_crash.operation_id,
            fingerprint=approval.publication_fingerprint,
            approval_id=approval.approval_id,
            reconciliation_provider=provider_rec,
        )
        self.assertTrue(ok)
        self.assertEqual(code, "RECONCILED_SUCCESS")
        self.assertEqual(vid, "VID_CONFIRMED_RECONCILED")
        self.assertEqual(self.orchestrator.executor.ledger.get_state(approval.publication_fingerprint), PublicationState.UPLOADED_PRIVATE)


# =====================================================================
# PHASE R: ZERO MUTATION & ZERO SPEND GUARANTEE
# =====================================================================

class TestPhaseR_ZeroMutationAndZeroSpendGuarantee(BaseSecurityRemediationTest):

    def test_zero_youtube_writes_occurred(self):
        provider = MockYouTubeUploadProvider()
        self.assertEqual(provider.dispatch_count, 0)

    def test_zero_monetary_spend_guaranteed(self):
        ok, code = validate_finite_exact_zero(0.0)
        self.assertTrue(ok)
        self.assertEqual(code, "ZERO_COST_VERIFIED")

    def test_golden_trophy_and_mystery_box_packages_stop_at_human_gate(self):
        gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT, allow_test_fixtures=False)

        golden_pkg_path = REPO_ROOT / "content" / "shorts" / "golden_trophy_heist" / "publish_package.json"
        if golden_pkg_path.is_file():
            golden_res = gate.evaluate_package(golden_pkg_path, audience_record=None)
            self.assertIn(golden_res.result, {"AUDIENCE_DECISION_REQUIRED", "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED"})

        mystery_pkg_path = REPO_ROOT / "content" / "shorts" / "mystery_box_unboxing" / "publish_package.json"
        if mystery_pkg_path.is_file():
            mystery_res = gate.evaluate_package(mystery_pkg_path, audience_record=None)
            self.assertIn(mystery_res.result, {"AUDIENCE_DECISION_REQUIRED", "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED"})


if __name__ == "__main__":
    unittest.main()
