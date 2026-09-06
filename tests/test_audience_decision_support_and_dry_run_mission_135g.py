#!/usr/bin/env python3
"""Targeted unit tests for Mission 135G: Human Audience Decision Support & First-Upload Dry-Run Simulator."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.audience_decision_support import (
    CARD_WARNING_TEXT,
    DECISION_SUPPORT_VERSION,
    HUMAN_SELECTABLE_OPTIONS,
    compute_preview_decision_hash,
    extract_observable_facts,
    generate_all_decision_cards,
    generate_audience_decision_card,
    generate_fruitki_audience_decision_cards_package,
)
from scripts.evidence_provenance import check_for_secrets
from scripts.private_upload_dry_run import (
    DryRunScenarioResult,
    MockYouTubeUploadProvider,
    PrivateUploadDryRunOrchestrator,
)
from scripts.publication_approval import (
    ApprovalAction,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalState,
    AudienceDecisionRecord,
    AudienceDecisionState,
    derive_approval_state,
    validate_finite_exact_zero,
)
from scripts.publication_engine import (
    PublicationLedger,
    PublicationState,
)
from scripts.release_acceptance_gate import ReleaseAcceptanceGate

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAudienceDecisionSupportAndDryRunMission135G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pub_135g_test_"))
        self.orchestrator = PrivateUploadDryRunOrchestrator(sandbox_dir=self.test_dir)

    def tearDown(self):
        self.orchestrator.cleanup()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ----------------------------------------------------
    # 1. AUDIENCE_CARD_TESTS
    # ----------------------------------------------------

    def test_golden_trophy_decision_card_generation(self):
        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        card = generate_audience_decision_card(gt_pkg)

        self.assertEqual(card["content_id"], "golden_trophy_short")
        self.assertIn("goldene Trophäe", card["human_readable_title"])
        self.assertEqual(card["media_sha256"], "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8")
        self.assertEqual(card["publication_fingerprint"], "c42c6830a2b5f3d43f542b0d9521bf5572ae12e43b09bc4724e16b4a0081eed0")
        self.assertEqual(card["technical_specifications"]["duration_seconds"], 8.0)
        self.assertEqual(card["technical_specifications"]["dimensions"]["width"], 360)
        self.assertEqual(card["technical_specifications"]["dimensions"]["height"], 640)
        self.assertEqual(card["decision_status"], "PENDING_HUMAN_DECISION")
        self.assertIsNone(card["default_selection"])

    def test_mystery_box_decision_card_generation(self):
        mb_pkg = REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json"
        card = generate_audience_decision_card(mb_pkg)

        self.assertEqual(card["content_id"], "mystery_box_short")
        self.assertIn("Mystery Box", card["human_readable_title"])
        self.assertEqual(card["media_sha256"], "0610c35c3589e38f943de2bf3efca75f670852390b69814e77f8251ab91bba99")
        self.assertEqual(card["publication_fingerprint"], "0226e05a99d440b4302c0167cc9894b1e24dc497522638740472cd05dbd34b39")
        self.assertEqual(card["technical_specifications"]["duration_seconds"], 7.5)
        self.assertEqual(card["decision_status"], "PENDING_HUMAN_DECISION")
        self.assertIsNone(card["default_selection"])

    def test_observable_content_facts_grounded(self):
        gt_pkg = json.loads((REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json").read_text())
        facts_gt = extract_observable_facts("golden_trophy_short", gt_pkg)
        self.assertIn("Erdbeere (Strawberry)", facts_gt.characters_depicted)
        self.assertIn("Kiwi", facts_gt.characters_depicted)
        self.assertIn("Goldene Trophäe (Golden Trophy)", facts_gt.characters_depicted)
        self.assertIn("Wettlauf", facts_gt.visual_theme)

        mb_pkg = json.loads((REPO_ROOT / "runtime" / "content" / "mystery_box_short" / "publish_package.json").read_text())
        facts_mb = extract_observable_facts("mystery_box_short", mb_pkg)
        self.assertIn("Erdbeere (Strawberry)", facts_mb.characters_depicted)
        self.assertIn("Geheimnisvolle Kiste (Mystery Box)", facts_mb.characters_depicted)
        self.assertIn("Konfetti", facts_mb.characters_depicted)

    # ----------------------------------------------------
    # 2. HUMAN_DECISION_ISOLATION_TESTS
    # ----------------------------------------------------

    def test_human_choice_options_and_no_default(self):
        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        card = generate_audience_decision_card(gt_pkg)

        self.assertEqual(card["human_choice_options"], ["MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS", "CANCEL / NO DECISION"])
        self.assertIsNone(card["default_selection"])
        self.assertEqual(card["card_warning"], CARD_WARNING_TEXT)

    def test_binding_previews_marked_not_durable(self):
        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        card = generate_audience_decision_card(gt_pkg)

        previews = card["decision_record_binding_previews"]
        self.assertEqual(previews["MADE_FOR_KIDS"]["status"], "PREVIEW_ONLY_NOT_DURABLE")
        self.assertEqual(previews["NOT_MADE_FOR_KIDS"]["status"], "PREVIEW_ONLY_NOT_DURABLE")
        self.assertTrue(previews["MADE_FOR_KIDS"]["preview_decision_hash"])
        self.assertTrue(previews["NOT_MADE_FOR_KIDS"]["preview_decision_hash"])

    def test_preview_cannot_satisfy_real_acceptance_gate(self):
        gate = ReleaseAcceptanceGate(repo_dir=REPO_ROOT, allow_test_fixtures=False)
        gt_pkg = REPO_ROOT / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
        res = gate.evaluate_package(gt_pkg)
        self.assertEqual(res.result, "AUDIENCE_DECISION_REQUIRED")

    # ----------------------------------------------------
    # 3. DRY_RUN_SUCCESS_TESTS
    # ----------------------------------------------------

    def test_normal_success_dryrun_simulation(self):
        res = self.orchestrator.run_normal_success_dryrun()
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.code, "UPLOADED_PRIVATE")
        self.assertEqual(res.dispatch_count, 1)
        self.assertEqual(res.video_id, "VID_DRYRUN_SUCCESS_200")
        self.assertEqual(res.approval_state_after, "CONSUMED")
        self.assertEqual(res.ledger_state_after, "UPLOADED_PRIVATE")

    # ----------------------------------------------------
    # 4. DRY_RUN_CRASH_TESTS
    # ----------------------------------------------------

    def test_crash_before_and_after_reservation(self):
        res_res = self.orchestrator.run_crash_simulation_dryrun("AFTER_RESERVATION")
        self.assertEqual(res_res.status, "ERROR")
        self.assertEqual(res_res.code, "CRASH_AFTER_RESERVATION")
        self.assertEqual(res_res.dispatch_count, 0)

        res_int = self.orchestrator.run_crash_simulation_dryrun("AFTER_INTENT")
        self.assertEqual(res_int.status, "ERROR")
        self.assertEqual(res_int.code, "CRASH_AFTER_INTENT")
        self.assertEqual(res_int.dispatch_count, 0)

    def test_timeout_after_possible_dispatch_and_no_auto_retry(self):
        res_to = self.orchestrator.run_crash_simulation_dryrun("TIMEOUT_AFTER_POSSIBLE_DISPATCH")
        self.assertEqual(res_to.status, "ERROR")
        self.assertEqual(res_to.code, "EXTERNAL_OUTCOME_UNCERTAIN")
        self.assertEqual(res_to.dispatch_count, 1)

        # Attempting second execution is blocked
        pkg_path, approval, _ = self.orchestrator.setup_fixture_environment()
        # Set state to EXTERNAL_OUTCOME_UNCERTAIN
        self.orchestrator.executor.ledger.transition_state(
            approval.publication_fingerprint, PublicationState.EXTERNAL_OUTCOME_UNCERTAIN
        )
        second_exec = self.orchestrator.executor.execute_private_upload(
            package_path=pkg_path,
            approval=approval,
            upload_mutation_mock=lambda p: {"status": "SUCCESS", "video_id": "SHOULD_NOT_RUN"},
        )
        self.assertEqual(second_exec.status, "BLOCKED")
        self.assertEqual(second_exec.code, "PRIOR_PUBLICATION_CONFLICT")

    def test_reconciliation_exact_id_vs_ambiguous(self):
        # 1. Exact ID available
        ok_exact, code_exact, vid_exact = self.orchestrator.run_reconciliation_simulation(exact_id_available=True)
        self.assertTrue(ok_exact)
        self.assertEqual(code_exact, "RECONCILED_SUCCESS")
        self.assertEqual(vid_exact, "VID_RECON_TARGET")

        # 2. Ambiguous scan without exact ID
        ok_ambig, code_ambig, vid_ambig = self.orchestrator.run_reconciliation_simulation(exact_id_available=False)
        self.assertFalse(ok_ambig)
        self.assertEqual(code_ambig, "AMBIGUOUS_MATCH")
        self.assertIsNone(vid_ambig)

    # ----------------------------------------------------
    # 5. FENCING_DRY_RUN_TESTS
    # ----------------------------------------------------

    def test_fencing_stale_owner_rejected(self):
        fencing_res = self.orchestrator.run_fencing_old_owner_simulation()
        self.assertTrue(fencing_res["owner_1_initial_reservation"])
        self.assertTrue(fencing_res["owner_2_new_reservation"])
        self.assertTrue(fencing_res["owner_1_stale_release_blocked"])
        self.assertEqual(fencing_res["rejection_code"], "WRONG_OWNER_RELEASE_BLOCKED")

    # ----------------------------------------------------
    # 6. PUBLIC_RELEASE_FIREBREAK_TESTS
    # ----------------------------------------------------

    def test_private_approval_firebreak_against_public_release(self):
        fb_res = self.orchestrator.run_public_release_firebreak_test()
        self.assertTrue(fb_res["public_release_action_blocked"])
        self.assertEqual(fb_res["public_release_action_code"], "APPROVAL_ACTION_MISMATCH")
        self.assertTrue(fb_res["public_privacy_blocked"])
        self.assertEqual(fb_res["public_privacy_code"], "INVALID_PRIVACY_FOR_PRIVATE_UPLOAD")

    # ----------------------------------------------------
    # 7. ZERO_SPEND_TESTS & 8. SECRET_ABSENCE_TESTS
    # ----------------------------------------------------

    def test_zero_spend_validation(self):
        ok0, _ = validate_finite_exact_zero(0.0)
        self.assertTrue(ok0)

        ok_bad, code_bad = validate_finite_exact_zero(5.0)
        self.assertFalse(ok_bad)
        self.assertEqual(code_bad, "PAYMENT_APPROVAL_REQUIRED")

    def test_secret_absence_in_all_artifacts_and_cards(self):
        pkg = generate_fruitki_audience_decision_cards_package(REPO_ROOT)
        clean, reason = check_for_secrets(pkg)
        self.assertTrue(clean, f"Secret detected: {reason}")


if __name__ == "__main__":
    unittest.main()
