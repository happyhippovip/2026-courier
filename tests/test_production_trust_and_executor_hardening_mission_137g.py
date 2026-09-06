#!/usr/bin/env python3
"""Targeted adversarial unit test suite for Mission 137G: Production Trust Boundary, Atomic Authority, & Executor Hard Gate."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from scripts.creator_input_sources import compute_publication_dedupe_fingerprint
from scripts.evidence_provenance import (
    CHANNEL_IDENTITY_MAX_AGE_SECONDS,
    DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS,
    ProductionAuthorizedYouTubeReadService,
    ProvenanceReceipt,
    ProvenanceSource,
    TestFixtureYouTubeReadService,
    TrustDomain,
    build_package_duplicate_preflight,
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
    PublicationLedger,
    PublicationState,
)
from scripts.release_acceptance_gate import (
    AcceptanceResult,
    ReleaseAcceptanceGate,
    compute_acceptance_input_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestProductionTrustAndExecutorHardeningMission137G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_137g_test_"))
        self.orchestrator = PrivateUploadDryRunOrchestrator(sandbox_dir=self.test_dir)

    def tearDown(self):
        self.orchestrator.cleanup()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def setup_registered_environment(self, **kwargs):
        pkg_path, approval, aud_rec = self.orchestrator.setup_fixture_environment(**kwargs)
        self.orchestrator.gate.audience_registry.register_decision(aud_rec)
        return pkg_path, approval, aud_rec

    # ----------------------------------------------------
    # 1. PRODUCTION TRUST & PROVENANCE TESTS
    # ----------------------------------------------------

    def test_generic_builder_cannot_forge_production_trust_domain(self):
        with self.assertRaises(PermissionError):
            ProvenanceReceipt.create(
                trust_domain=TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
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

    def test_fixture_provenance_rejected_by_production_gate(self):
        # Production gate with allow_test_fixtures=False
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=False)
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        # The fixture environment created TEST_FIXTURE domain receipts
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_REQUIRED")

    def test_receipt_tampering_and_swap_detected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        # 1. Modify channel receipt payload hash
        ch_ev_path = self.test_dir / "events" / "evidence" / "channel_evidence_fruitki.json"
        ch_data = json.loads(ch_ev_path.read_text())
        rcpt_path = self.test_dir / "events" / "receipts" / f"{ch_data['authorized_read_receipt_id']}.json"
        rcpt_data = json.loads(rcpt_path.read_text())
        rcpt_data["payload_evidence_hash"] = "tampered_hash_00000000000000000000000000000000"
        rcpt_path.write_text(json.dumps(rcpt_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "CHANNEL_EVIDENCE_PROVENANCE_MISMATCH")

    def test_snapshot_swap_detected(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        snap_path = self.test_dir / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        snap_data = json.loads(snap_path.read_text())
        snap_data["video_ids"].append("VID_SWAPPED_UNAUTHORIZED")
        snap_path.write_text(json.dumps(snap_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "DUPLICATE_EVIDENCE_PROVENANCE_MISMATCH")

    # ----------------------------------------------------
    # 2. PAGINATION TESTS
    # ----------------------------------------------------

    def test_pagination_fixtures_zero_one_and_multi_page(self):
        # 0 items
        ev0, rcpt0 = TestFixtureYouTubeReadService.create_upload_snapshot_fixture(video_ids=[])
        self.assertEqual(ev0["items_checked"], 0)
        self.assertTrue(rcpt0.verify_integrity())

        # 1 page
        ev1, rcpt1 = TestFixtureYouTubeReadService.create_upload_snapshot_fixture(video_ids=["V1", "V2"])
        self.assertEqual(ev1["page_count"], 1)
        self.assertTrue(ev1["coverage_complete"])

        # Multi-page
        ev_multi, rcpt_multi = TestFixtureYouTubeReadService.create_upload_snapshot_fixture(
            video_ids=[f"V_{i}" for i in range(150)],
            page_count=3,
            coverage_complete=True,
        )
        self.assertEqual(ev_multi["page_count"], 3)
        self.assertEqual(ev_multi["items_checked"], 150)

    def test_incomplete_pagination_blocked(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        # Mark duplicate preflight as incomplete
        pkg = json.loads(pkg_path.read_text())
        dup_path = Path(pkg["duplicate_preflight_path"])
        dup_data = json.loads(dup_path.read_text())
        dup_data["coverage_complete"] = False
        dup_data["result"] = "PLATFORM_METADATA_CHECK_INCOMPLETE"
        dup_path.write_text(json.dumps(dup_data, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PLATFORM_METADATA_CHECK_INCOMPLETE")

    # ----------------------------------------------------
    # 3. SCHEMA AND BINDING TESTS
    # ----------------------------------------------------

    def test_unsupported_package_schema_blocked(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        pkg["schema_version"] = "1.0"  # Unsupported
        pkg_path.write_text(json.dumps(pkg, indent=2))

        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PACKAGE_SCHEMA_UNSUPPORTED")

    def test_wrong_platform_and_fingerprint_blocked(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        pkg["platform"] = "TIKTOK"
        pkg_path.write_text(json.dumps(pkg, indent=2))
        res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res.result, "PLATFORM_MISMATCH")

        pkg["platform"] = "YOUTUBE"
        pkg["publication_dedupe_fingerprint"] = "wrong_fingerprint_00000000000000000000000000000000"
        pkg_path.write_text(json.dumps(pkg, indent=2))
        res_fp = gate.evaluate_package(pkg_path, audience_record=aud_rec)
        self.assertEqual(res_fp.result, "FINGERPRINT_MISMATCH")

    def test_publication_authorized_non_false_blocked(self):
        pkg_path, approval, aud_rec = self.setup_registered_environment()
        gate = ReleaseAcceptanceGate(repo_dir=self.test_dir, allow_test_fixtures=True)

        pkg = json.loads(pkg_path.read_text())
        for invalid_val in [True, "false", "0", 1, None]:
            pkg["publication_authorized"] = invalid_val
            pkg_path.write_text(json.dumps(pkg, indent=2))
            res = gate.evaluate_package(pkg_path, audience_record=aud_rec)
            self.assertEqual(res.result, "PUBLICATION_AUTHORIZATION_STATE_INVALID")

    # ----------------------------------------------------
    # 4. MONEY FIREWALL TESTS
    # ----------------------------------------------------

    def test_finite_exact_zero_money_cases(self):
        # Valid cases
        self.assertTrue(validate_finite_exact_zero(0)[0])
        self.assertTrue(validate_finite_exact_zero(0.0)[0])
        self.assertTrue(validate_finite_exact_zero(-0.0)[0])

        # Invalid cases
        for invalid in [False, True, "0", "0.0", None, math.nan, math.inf, -math.inf, -1.0, 5.0, "EUR"]:
            ok, code = validate_finite_exact_zero(invalid)
            self.assertFalse(ok)
            self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    # ----------------------------------------------------
    # 5. APPROVAL REGISTRY AND AUTHORITY TESTS
    # ----------------------------------------------------

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

    def test_approval_conflict_detection(self):
        registry = ApprovalRegistry(self.test_dir / "events" / "approvals" / "registry")
        app1 = ApprovalRecord(
            approval_id="app-conflict-test",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_1",
            media_sha256="sha_1",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_1",
            audience_decision_hash="aud_1",
            channel_evidence_hash="ch_1",
            duplicate_evidence_hash="dup_1",
            acceptance_id="acc_1",
            acceptance_hash="hash_1",
        )
        ok1, code1, _ = registry.register_approval(app1)
        self.assertTrue(ok1)
        self.assertEqual(code1, "APPROVAL_REGISTERED")

        # Idempotent repeat
        ok_idem, code_idem, _ = registry.register_approval(app1)
        self.assertTrue(ok_idem)
        self.assertEqual(code_idem, "IDEMPOTENT_EXISTING_APPROVAL")

        # Conflicting parameters
        app_conflict = ApprovalRecord(
            approval_id="app-conflict-test",
            approved_action="PRIVATE_UPLOAD",
            publication_fingerprint="fp_DIFFERENT",
            media_sha256="sha_1",
            platform="YOUTUBE",
            target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
            approved_privacy="private",
            metadata_revision_hash="meta_1",
            audience_decision_hash="aud_1",
            channel_evidence_hash="ch_1",
            duplicate_evidence_hash="dup_1",
            acceptance_id="acc_1",
            acceptance_hash="hash_1",
        )
        ok_conf, code_conf, _ = registry.register_approval(app_conflict)
        self.assertFalse(ok_conf)
        self.assertEqual(code_conf, "APPROVAL_ID_CONFLICT")

    def test_concurrent_approval_ledger_lost_update_protection(self):
        ledger = AppendOnlyApprovalLedger(self.test_dir / "events" / "approvals")

        def write_event(idx: int):
            return ledger.record_event(
                approval_id=f"app-{idx}",
                approval_state=ApprovalState.ACTIVE.value,
                publication_fingerprint=f"fp-{idx}",
                action="PRIVATE_UPLOAD",
                reason=f"Concurrent thread {idx}",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(write_event, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 20)
        ok, reason = ledger.verify_integrity()
        self.assertTrue(ok, f"Ledger integrity failed: {reason}")

    # ----------------------------------------------------
    # 6. OPERATION AUTHORITY AND FENCING TESTS
    # ----------------------------------------------------

    def test_concurrent_reservation_two_and_six_processes(self):
        ledger = PublicationLedger(self.test_dir / "events" / "publications")
        fp = "test_concurrent_fp_100"

        def attempt_reserve(proc_id: int):
            token = f"token-{proc_id}"
            return ledger.reserve(
                fingerprint=fp,
                target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                media_sha256="sha_concurrent",
                reservation_token=token,
                operation_id=f"op-{proc_id}",
            )

        # 2-process race
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(attempt_reserve, i) for i in range(2)]
            res2 = [f.result() for f in concurrent.futures.as_completed(futs)]
        winners2 = [r for r in res2 if r[0] is True]
        self.assertEqual(len(winners2), 1)

        # 6-process race on new fingerprint
        fp6 = "test_concurrent_fp_600"
        def attempt_reserve_6(proc_id: int):
            token = f"token-6-{proc_id}"
            return ledger.reserve(
                fingerprint=fp6,
                target_channel_id="UCg0O_a10jsQ74ffS_HgFGqA",
                media_sha256="sha_concurrent_6",
                reservation_token=token,
                operation_id=f"op-6-{proc_id}",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futs6 = [pool.submit(attempt_reserve_6, i) for i in range(6)]
            res6 = [f.result() for f in concurrent.futures.as_completed(futs6)]
        winners6 = [r for r in res6 if r[0] is True]
        self.assertEqual(len(winners6), 1)
        self.assertEqual(len(res6) - len(winners6), 5)

    def test_stale_fencing_token_rejected_on_all_mutations(self):
        fencing_res = self.orchestrator.run_fencing_old_owner_simulation()
        self.assertTrue(fencing_res["owner_1_stale_release_blocked"])
        self.assertEqual(fencing_res["rejection_code"], "WRONG_OWNER_RELEASE_BLOCKED")

    # ----------------------------------------------------
    # 7. EXECUTOR HARD GATE & EXECUTION TESTS
    # ----------------------------------------------------

    def test_executor_stops_on_non_ready_acceptance(self):
        pkg_path, approval, _ = self.orchestrator.setup_fixture_environment()
        pkg = json.loads(pkg_path.read_text())
        pkg["audience_decision"] = "DECISION_REQUIRED"
        pkg["audience_decision_hash"] = ""
        pkg_path.write_text(json.dumps(pkg, indent=2))
        res = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            audience_record=None,
        )
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.code, "AUDIENCE_DECISION_REQUIRED")

    def test_normal_success_dryrun(self):
        res = self.orchestrator.run_normal_success_dryrun()
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.code, "UPLOADED_PRIVATE")
        self.assertEqual(res.dispatch_count, 1)
        self.assertEqual(res.approval_state_after, "CONSUMED")
        self.assertEqual(res.ledger_state_after, "UPLOADED_PRIVATE")

    def test_reconciliation_exact_id_vs_arbitrary_callback(self):
        # 1. Exact durable ID
        ok_exact, code_exact, vid_exact = self.orchestrator.run_reconciliation_simulation(exact_id_available=True)
        self.assertTrue(ok_exact)
        self.assertEqual(code_exact, "RECONCILED_SUCCESS")
        self.assertEqual(vid_exact, "VID_RECON_TARGET")

        # 2. Ambiguous callback
        ok_ambig, code_ambig, vid_ambig = self.orchestrator.run_reconciliation_simulation(exact_id_available=False)
        self.assertFalse(ok_ambig)
        self.assertEqual(code_ambig, "AMBIGUOUS_MATCH")
        self.assertIsNone(vid_ambig)

    def test_public_release_firebreak(self):
        fb_res = self.orchestrator.run_public_release_firebreak_test()
        self.assertTrue(fb_res["public_release_action_blocked"])
        self.assertEqual(fb_res["public_release_action_code"], "APPROVAL_ACTION_MISMATCH")
        self.assertTrue(fb_res["public_privacy_blocked"])
        self.assertEqual(fb_res["public_privacy_code"], "INVALID_PRIVACY_FOR_PRIVATE_UPLOAD")


if __name__ == "__main__":
    unittest.main()
