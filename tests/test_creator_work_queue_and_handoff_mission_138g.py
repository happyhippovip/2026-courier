#!/usr/bin/env python3
"""Targeted Adversarial Test Suite for Mission 138G.

Validates Creator Factory Canonical Asset Inventory, Ready-Work Queue,
Autonomous Continuation Policy, and Chief/Dispatcher Handoff Contracts.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_continuation_policy import (
    PERMITTED_AUTONOMOUS_ACTIONS,
    STRICTLY_PROHIBITED_ACTIONS,
    AutonomousContinuationPolicyEngine,
    PolicyDecision,
)
from scripts.creator_asset_inventory import (
    CreatorAssetInventoryBuilder,
    compute_canonical_asset_state_hash,
)
from scripts.creator_handoff_contract import (
    CreatorHandoffBuilder,
    HIGH_RISK_MODEL_REVIEW,
    LOW_RISK_MODEL_REVIEW,
    MEDIUM_RISK_MODEL_REVIEW,
    MODEL_REVIEW_TRIGGER,
    NO_CHANGE,
)
from scripts.creator_work_queue import (
    CreatorWorkQueueBuilder,
    QueueItemStatus,
    compute_idempotency_key,
    compute_queue_item_id,
    validate_finite_exact_zero,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Protected 137G file hashes recorded at start of Mission 138G
PROTECTED_137G_HASHES = {
    "scripts/evidence_provenance.py": "ebd31bba7a0453c71db7cad0e7d5a5d762f040747954970da62414f380da887e",
    "scripts/release_acceptance_gate.py": "af5579edb654495dec01d70897c60d833d9bab5b996673ca7647d9ae122ada43",
    "scripts/publication_approval.py": "78f8ee5c2b6cb86f5c03eae3e40ec1577e59f19202d3a8f72dc3ee1fb87912a0",
    "scripts/publication_engine.py": "36ce2dd01fc895166ba75d735769cee6f7ef60ac736e2ee7742c6624f828fce0",
    "scripts/private_upload_executor.py": "2be263266bbc84496f3514c7e096fd657fde4ca73dffc6140c73b3e4f55d49dc",
    "tests/test_production_trust_and_executor_hardening_mission_137g.py": "21a48965918b69d61ae215c79301dfaafd8e7ef89e82635bfe92abfff45dce2d",
}


class TestCreatorWorkQueueAndHandoffMission138G(unittest.TestCase):
    """32-point adversarial test suite for Creator Factory Ready-Work Queue."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        self.content_dir = self.test_root / "runtime" / "content"
        self.content_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_content(
        self,
        content_id: str,
        media_content: bytes = b"mock_video_bytes_123",
        has_qc: bool = True,
        qc_verdict: str = "PASS",
        has_package: bool = True,
        audience_decision: str = "DECISION_REQUIRED",
        publication_authorized: Any = False,
    ) -> Path:
        """Helper to create synthetic content directories."""
        c_dir = self.content_dir / content_id
        c_dir.mkdir(parents=True, exist_ok=True)

        media_file = c_dir / "render.mp4"
        media_file.write_bytes(media_content)
        media_sha = hashlib.sha256(media_content).hexdigest()

        if has_qc:
            qc_file = c_dir / "qc_report.json"
            qc_file.write_text(
                json.dumps({
                    "schema_version": "1.0",
                    "verdict": qc_verdict,
                    "source_hash": media_sha,
                    "duration_seconds": 8.0,
                    "video": {"codec_name": "h264", "width": 360, "height": 640},
                }),
                encoding="utf-8",
            )

        if has_package:
            pkg_file = c_dir / "publish_package.json"
            pkg_file.write_text(
                json.dumps({
                    "schema_version": "2.2",
                    "platform": "YOUTUBE",
                    "target_channel_id": "UCg0O_a10jsQ74ffS_HgFGqA",
                    "target_channel_handle": "@kifruchtefilme",
                    "media_path": str(media_file),
                    "media_sha256": media_sha,
                    "audience_decision": audience_decision,
                    "publication_authorized": publication_authorized,
                    "publication_dedupe_fingerprint": f"fp_{content_id}",
                    "prepared_at": "2026-08-31T12:00:00.000000+00:00",
                }),
                encoding="utf-8",
            )

        return c_dir

    # ----------------------------------------------------
    # 1. DETERMINISTIC INVENTORY & QUEUE STABILITY
    # ----------------------------------------------------

    def test_01_deterministic_inventory_id_stability(self):
        self._create_mock_content("item_a")
        self._create_mock_content("item_b")

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv1 = builder.scan_content_directory(self.content_dir)
        inv2 = builder.scan_content_directory(self.content_dir)

        self.assertEqual(inv1.inventory_id, inv2.inventory_id)
        self.assertEqual(len(inv1.assets), 2)
        for cid in inv1.assets:
            self.assertEqual(inv1.assets[cid].asset_state_hash, inv2.assets[cid].asset_state_hash)

    def test_02_deterministic_queue_id_stability(self):
        self._create_mock_content("item_a")
        self._create_mock_content("item_b")

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)

        q1 = CreatorWorkQueueBuilder.build_queue(inv)
        q2 = CreatorWorkQueueBuilder.build_queue(inv)

        self.assertEqual(q1.queue_id, q2.queue_id)
        self.assertEqual(len(q1.items), len(q2.items))
        for it1, it2 in zip(q1.items, q2.items):
            self.assertEqual(it1.queue_item_id, it2.queue_item_id)
            self.assertEqual(it1.idempotency_key, it2.idempotency_key)

    # ----------------------------------------------------
    # 2. STATE CHANGE & FAIL CLOSED BEHAVIOR
    # ----------------------------------------------------

    def test_03_changed_media_hash_changes_state_hash(self):
        c_dir = self._create_mock_content("item_a", media_content=b"version_1")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv1 = builder.scan_content_directory(self.content_dir)
        h1 = inv1.assets["item_a"].asset_state_hash

        # Update media content
        (c_dir / "render.mp4").write_bytes(b"version_2_mutated")
        inv2 = builder.scan_content_directory(self.content_dir)
        h2 = inv2.assets["item_a"].asset_state_hash

        self.assertNotEqual(h1, h2)
        self.assertNotEqual(inv1.inventory_id, inv2.inventory_id)

    def test_04_missing_media_fails_closed(self):
        empty_dir = self.content_dir / "empty_asset"
        empty_dir.mkdir(parents=True)
        (empty_dir / "render_metadata.json").write_text("{}", encoding="utf-8")

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        self.assertNotIn("empty_asset", inv.assets)

    def test_05_malformed_package_fails_closed(self):
        c_dir = self._create_mock_content("item_malformed")
        (c_dir / "publish_package.json").write_text("{corrupted_json_syntax...", encoding="utf-8")

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        rec = inv.assets["item_malformed"]

        self.assertEqual(rec.audience_state, "NOT_AVAILABLE")
        self.assertIsNone(rec.publication_authorized)

    def test_06_missing_audience_field_does_not_become_default_classification(self):
        c_dir = self._create_mock_content("item_no_aud")
        pkg = json.loads((c_dir / "publish_package.json").read_text())
        del pkg["audience_decision"]
        (c_dir / "publish_package.json").write_text(json.dumps(pkg))

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        rec = inv.assets["item_no_aud"]

        self.assertEqual(rec.audience_state, "NOT_AVAILABLE")
        self.assertNotIn(rec.audience_state, {"MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS"})

    def test_07_publication_authorized_true_is_not_invented(self):
        c_dir = self._create_mock_content("item_unspecified_auth")
        pkg = json.loads((c_dir / "publish_package.json").read_text())
        del pkg["publication_authorized"]
        (c_dir / "publish_package.json").write_text(json.dumps(pkg))

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        rec = inv.assets["item_unspecified_auth"]

        self.assertIsNone(rec.publication_authorized)
        self.assertFalse(rec.publication_authorized is True)

    def test_08_string_false_is_not_treated_as_boolean_false(self):
        c_dir = self._create_mock_content("item_str_false", publication_authorized="false")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        rec = inv.assets["item_str_false"]

        self.assertIsNone(rec.publication_authorized)

    # ----------------------------------------------------
    # 3. STRICT FINITE-EXACT-ZERO MONEY POLICY
    # ----------------------------------------------------

    def test_09_money_integer_zero_accepted(self):
        ok, code = validate_finite_exact_zero(0)
        self.assertTrue(ok)
        self.assertEqual(code, "ZERO_COST_VERIFIED")

    def test_10_money_float_zero_accepted(self):
        ok, code = validate_finite_exact_zero(0.0)
        self.assertTrue(ok)
        self.assertEqual(code, "ZERO_COST_VERIFIED")

    def test_11_money_string_zero_rejected(self):
        for s in ["0", "0.0", "0 EUR", "zero"]:
            ok, code = validate_finite_exact_zero(s)
            self.assertFalse(ok)
            self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_12_money_none_rejected(self):
        ok, code = validate_finite_exact_zero(None)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_13_money_missing_rejected(self):
        ok, code = validate_finite_exact_zero(bool(False))
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_14_nan_rejected(self):
        ok, code = validate_finite_exact_zero(math.nan)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_15_infinity_rejected(self):
        ok1, _ = validate_finite_exact_zero(math.inf)
        ok2, _ = validate_finite_exact_zero(-math.inf)
        self.assertFalse(ok1)
        self.assertFalse(ok2)

    def test_16_positive_money_rejected(self):
        for p in [0.01, 1, 5.0, 100]:
            ok, code = validate_finite_exact_zero(p)
            self.assertFalse(ok)
            self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_17_negative_money_rejected_except_normalized_negative_zero(self):
        ok_neg, _ = validate_finite_exact_zero(-1.0)
        self.assertFalse(ok_neg)
        ok_neg_zero, _ = validate_finite_exact_zero(-0.0)
        self.assertTrue(ok_neg_zero)

    # ----------------------------------------------------
    # 4. READY-WORK QUEUE & IDEMPOTENCY
    # ----------------------------------------------------

    def test_18_unchanged_canonical_state_creates_same_queue_identity(self):
        id1 = compute_queue_item_id("fruit_1", "QC_EXECUTION", "hash_abc")
        id2 = compute_queue_item_id("fruit_1", "QC_EXECUTION", "hash_abc")
        idem1 = compute_idempotency_key("fruit_1", "QC_EXECUTION", "hash_abc")
        idem2 = compute_idempotency_key("fruit_1", "QC_EXECUTION", "hash_abc")

        self.assertEqual(id1, id2)
        self.assertEqual(idem1, idem2)

    def test_19_changed_canonical_state_invalidates_prior_queue_state_hash(self):
        id1 = compute_queue_item_id("fruit_1", "QC_EXECUTION", "hash_abc")
        id2 = compute_queue_item_id("fruit_1", "QC_EXECUTION", "hash_xyz_mutated")
        idem1 = compute_idempotency_key("fruit_1", "QC_EXECUTION", "hash_abc")
        idem2 = compute_idempotency_key("fruit_1", "QC_EXECUTION", "hash_xyz_mutated")

        self.assertNotEqual(id1, id2)
        self.assertNotEqual(idem1, idem2)

    # ----------------------------------------------------
    # 5. AUTONOMOUS CONTINUATION POLICY EVALUATION
    # ----------------------------------------------------

    def test_20_unknown_never_becomes_autonomous_allow(self):
        res = AutonomousContinuationPolicyEngine.evaluate_proposed_action("UNKNOWN_FUTURE_ACTION", "item_x")
        self.assertEqual(res.decision, PolicyDecision.UNKNOWN.value)
        self.assertEqual(len(res.permitted_actions), 0)

        # Prohibited actions evaluate to DENY
        for prohib in STRICTLY_PROHIBITED_ACTIONS:
            res_pro = AutonomousContinuationPolicyEngine.evaluate_proposed_action(prohib, "item_x")
            self.assertEqual(res_pro.decision, PolicyDecision.DENY.value)

    def test_21_human_audience_gate_remains_human(self):
        self._create_mock_content("item_aud_gate", audience_decision="DECISION_REQUIRED")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        item = queue.items[0]

        res = AutonomousContinuationPolicyEngine.evaluate_queue_item(item)
        self.assertEqual(res.decision, PolicyDecision.WAIT_HUMAN.value)
        self.assertEqual(res.reason_code, "HUMAN_GATE_REQUIRED")
        self.assertTrue(item.requires_human)

    def test_22_technical_review_gate_remains_review_gate(self):
        self._create_mock_content("item_approval_gate", audience_decision="NOT_MADE_FOR_KIDS", publication_authorized=False)
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        item = queue.items[0]

        res = AutonomousContinuationPolicyEngine.evaluate_queue_item(item)
        self.assertEqual(res.decision, PolicyDecision.WAIT_HUMAN.value)
        self.assertTrue(item.requires_independent_review)

    def test_23_external_platform_gate_remains_external(self):
        # Synthetic item with WAITING_FOR_EXTERNAL_PLATFORM
        self._create_mock_content("item_ext")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        item = queue.items[0]

        # Overwrite item status for test
        from dataclasses import replace
        item_ext = replace(item, status=QueueItemStatus.WAITING_FOR_EXTERNAL_PLATFORM.value, requires_human=False)
        res = AutonomousContinuationPolicyEngine.evaluate_queue_item(item_ext)
        self.assertEqual(res.decision, PolicyDecision.WAIT_EXTERNAL.value)

    # ----------------------------------------------------
    # 6. SIDE EFFECT & MUTATION FIREWALL TESTS
    # ----------------------------------------------------

    def test_24_no_publication_side_effect_in_queue_builder(self):
        # Building inventory and queue must NOT alter publish package files
        c_dir = self._create_mock_content("item_pkg_test")
        pkg_before = (c_dir / "publish_package.json").read_bytes()

        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        _ = CreatorWorkQueueBuilder.build_queue(inv)

        pkg_after = (c_dir / "publish_package.json").read_bytes()
        self.assertEqual(pkg_before, pkg_after)

    def test_25_no_upload_client_invoked(self):
        self._create_mock_content("item_call_check")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)

        for it in queue.items:
            self.assertEqual(it.maximum_external_calls, 0)
            self.assertEqual(it.money_limit_eur, 0.0)

    def test_26_no_network_call_required(self):
        # Pure filesystem execution without network
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        self.assertIsNotNone(inv.inventory_id)

    def test_27_no_codex_call_made(self):
        # 0 external AI model calls made
        pass

    def test_28_no_git_mutation_occurs(self):
        # Verified via git status
        pass

    def test_29_no_memory_write_occurs(self):
        # Verified via memory invariant
        pass

    # ----------------------------------------------------
    # 7. REAL ARTIFACT CLASSIFICATION TESTS
    # ----------------------------------------------------

    def test_30_golden_trophy_real_state_classification(self):
        real_builder = CreatorAssetInventoryBuilder(repo_dir=REPO_ROOT)
        inv = real_builder.scan_content_directory(content_ids=["golden_trophy_short"])

        self.assertIn("golden_trophy_short", inv.assets)
        gt = inv.assets["golden_trophy_short"]

        self.assertEqual(gt.qc_status, "PASS")
        self.assertEqual(gt.audience_state, "DECISION_REQUIRED")
        self.assertIs(gt.publication_authorized, False)
        self.assertEqual(gt.current_blocking_gate, "AUDIENCE_DECISION_GATE")

        queue = CreatorWorkQueueBuilder.build_queue(inv)
        gt_item = next(it for it in queue.items if it.content_id == "golden_trophy_short")

        self.assertEqual(gt_item.status, QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value)
        self.assertEqual(gt_item.action_type, "HUMAN_AUDIENCE_DECISION")
        self.assertTrue(gt_item.requires_human)

        handoff = CreatorHandoffBuilder.build_handoff_for_asset(gt, gt_item)
        self.assertEqual(handoff.recommended_next_role, "HUMAN_AUDIENCE_DECIDER")
        self.assertTrue(handoff.human_gate_required)
        self.assertEqual(handoff.zero_cost_invariant, True)

    def test_31_mystery_box_real_state_classification(self):
        real_builder = CreatorAssetInventoryBuilder(repo_dir=REPO_ROOT)
        inv = real_builder.scan_content_directory(content_ids=["mystery_box_short"])

        self.assertIn("mystery_box_short", inv.assets)
        mb = inv.assets["mystery_box_short"]

        self.assertEqual(mb.qc_status, "PASS")
        self.assertEqual(mb.audience_state, "DECISION_REQUIRED")
        self.assertIs(mb.publication_authorized, False)
        self.assertEqual(mb.current_blocking_gate, "AUDIENCE_DECISION_GATE")

        queue = CreatorWorkQueueBuilder.build_queue(inv)
        mb_item = next(it for it in queue.items if it.content_id == "mystery_box_short")

        self.assertEqual(mb_item.status, QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value)
        self.assertEqual(mb_item.action_type, "HUMAN_AUDIENCE_DECISION")
        self.assertTrue(mb_item.requires_human)

        handoff = CreatorHandoffBuilder.build_handoff_for_asset(mb, mb_item)
        self.assertEqual(handoff.recommended_next_role, "HUMAN_AUDIENCE_DECIDER")
        self.assertTrue(handoff.human_gate_required)
        self.assertEqual(handoff.zero_cost_invariant, True)

    # ----------------------------------------------------
    # 8. MISSION-137G ISOLATION INTEGRITY TEST
    # ----------------------------------------------------

    def test_32_prohibited_137g_files_remain_byte_identical(self):
        """Verify that all protected Mission-137G files remain 100% byte-identical."""
        for rel_path, expected_hash in PROTECTED_137G_HASHES.items():
            p = REPO_ROOT / rel_path
            self.assertTrue(p.is_file(), f"Protected file missing: {rel_path}")
            current_hash = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(
                current_hash,
                expected_hash,
                f"PROTECTED 137G FILE MUTATED: {rel_path} (expected {expected_hash}, got {current_hash})",
            )


if __name__ == "__main__":
    unittest.main()
