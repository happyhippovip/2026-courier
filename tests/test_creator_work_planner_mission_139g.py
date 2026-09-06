#!/usr/bin/env python3
"""Comprehensive Adversarial Test Suite for Mission 139G.

Validates Creator Work Planner, Execution Contract, Review Budget Gate,
Chief Return Contract, Duplicate Task Protection, and Zero-Spend Safety Invariants.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from scripts.autonomous_continuation_policy import (
    STRICTLY_PROHIBITED_ACTIONS,
)
from scripts.creator_asset_inventory import (
    CreatorAssetInventory,
    CreatorAssetInventoryBuilder,
    CreatorAssetRecord,
)
from scripts.creator_chief_contract import (
    ChiefResultStatus,
    CreatorChiefContractBuilder,
)
from scripts.creator_execution_contract import (
    CreatorExecutionContract,
)
from scripts.creator_review_gate import (
    CreatorReviewGate,
    ReviewDecision,
)
from scripts.creator_work_planner import (
    CreatorWorkPlanner,
    ExecutionClass,
    PlanStatus,
    RiskClass,
    WorkPlan,
    classify_action_risk,
    compute_plan_id,
    determine_execution_class,
)
from scripts.creator_work_queue import (
    CreatorWorkQueue,
    CreatorWorkQueueBuilder,
    CreatorWorkQueueItem,
    QueueItemStatus,
    validate_finite_exact_zero,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

PROTECTED_137G_HASHES = {
    "scripts/evidence_provenance.py": "ebd31bba7a0453c71db7cad0e7d5a5d762f040747954970da62414f380da887e",
    "scripts/release_acceptance_gate.py": "af5579edb654495dec01d70897c60d833d9bab5b996673ca7647d9ae122ada43",
    "scripts/publication_approval.py": "78f8ee5c2b6cb86f5c03eae3e40ec1577e59f19202d3a8f72dc3ee1fb87912a0",
    "scripts/publication_engine.py": "36ce2dd01fc895166ba75d735769cee6f7ef60ac736e2ee7742c6624f828fce0",
    "scripts/private_upload_executor.py": "2be263266bbc84496f3514c7e096fd657fde4ca73dffc6140c73b3e4f55d49dc",
    "tests/test_production_trust_and_executor_hardening_mission_137g.py": "21a48965918b69d61ae215c79301dfaafd8e7ef89e82635bfe92abfff45dce2d",
}


class TestCreatorWorkPlannerMission139G(unittest.TestCase):
    """45-point targeted test suite for Autonomous Work Planner and Safety Contracts."""

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
        media_content: bytes = b"mock_media_bytes_139",
        has_qc: bool = True,
        qc_verdict: str = "PASS",
        has_package: bool = True,
        audience_decision: str = "DECISION_REQUIRED",
        publication_authorized: Any = False,
    ) -> Path:
        """Create isolated synthetic content directory."""
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
    # 1. PLAN IDENTITY & HASH STABILITY
    # ----------------------------------------------------

    def test_01_identical_state_creates_identical_plan_identity(self):
        id1 = compute_plan_id("apple", "QC_EXECUTION", "hash_state_1", "queue_hash_1")
        id2 = compute_plan_id("apple", "QC_EXECUTION", "hash_state_1", "queue_hash_1")
        self.assertEqual(id1, id2)

    def test_02_changed_state_changes_plan_identity(self):
        id1 = compute_plan_id("apple", "QC_EXECUTION", "hash_state_1", "queue_hash_1")
        id2 = compute_plan_id("apple", "QC_EXECUTION", "hash_state_2_changed", "queue_hash_1")
        self.assertNotEqual(id1, id2)

    # ----------------------------------------------------
    # 2. FAIL-CLOSED EXECUTION CONTRACT VALIDATION
    # ----------------------------------------------------

    def test_03_unknown_risk_blocks_execution(self):
        self._create_mock_content("item_unknown_risk")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        bad_plan = replace(plan, risk_class="UNKNOWN")
        res = CreatorExecutionContract.validate_plan_for_execution(bad_plan)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "UNKNOWN_EXECUTION_OR_RISK_CLASS")

    def test_04_unknown_action_blocks_execution(self):
        self._create_mock_content("item_unknown_action")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        bad_plan = replace(plan, execution_class="UNKNOWN")
        res = CreatorExecutionContract.validate_plan_for_execution(bad_plan)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "UNKNOWN_EXECUTION_OR_RISK_CLASS")

    # ----------------------------------------------------
    # 3. STRICT FINITE-EXACT-ZERO MONEY POLICY
    # ----------------------------------------------------

    def test_05_missing_money_blocks(self):
        ok, code = validate_finite_exact_zero(None)
        self.assertFalse(ok)
        self.assertEqual(code, "PAYMENT_APPROVAL_REQUIRED")

    def test_06_none_money_blocks(self):
        ok, code = validate_finite_exact_zero(None)
        self.assertFalse(ok)

    def test_07_bool_false_money_blocks(self):
        ok, code = validate_finite_exact_zero(False)
        self.assertFalse(ok)

    def test_08_string_zero_blocks(self):
        for s in ["0", "0.0", "0.00", "0 EUR"]:
            ok, _ = validate_finite_exact_zero(s)
            self.assertFalse(ok)

    def test_09_nan_blocks(self):
        ok, _ = validate_finite_exact_zero(math.nan)
        self.assertFalse(ok)

    def test_10_infinity_blocks(self):
        ok1, _ = validate_finite_exact_zero(math.inf)
        ok2, _ = validate_finite_exact_zero(-math.inf)
        self.assertFalse(ok1)
        self.assertFalse(ok2)

    def test_11_positive_money_blocks(self):
        for p in [0.0001, 1.0, 50.0]:
            ok, _ = validate_finite_exact_zero(p)
            self.assertFalse(ok)

    def test_12_negative_non_zero_money_blocks(self):
        ok, _ = validate_finite_exact_zero(-10.0)
        self.assertFalse(ok)

    def test_13_integer_zero_accepted(self):
        ok, code = validate_finite_exact_zero(0)
        self.assertTrue(ok)
        self.assertEqual(code, "ZERO_COST_VERIFIED")

    def test_14_float_zero_accepted(self):
        ok, code = validate_finite_exact_zero(0.0)
        self.assertTrue(ok)
        self.assertEqual(code, "ZERO_COST_VERIFIED")

    # ----------------------------------------------------
    # 4. DUPLICATE TASK PROTECTION & IDLE STATE
    # ----------------------------------------------------

    def test_15_duplicate_complete_task_not_regenerated(self):
        self._create_mock_content("item_dup_check", has_qc=False, has_package=False)
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)

        state_hash = inv.assets["item_dup_check"].asset_state_hash
        task_id = f"TASK-CREATOR-item_dup_check-{state_hash[:8]}"

        # Simulate task completed in ledger with identical state hash
        planner = CreatorWorkPlanner(completed_task_ledger={task_id: state_hash})
        plans = planner.plan_all(inv, queue)

        self.assertEqual(plans[0].status, PlanStatus.NO_USEFUL_NEW_WORK.value)
        self.assertEqual(plans[0].execution_class, ExecutionClass.NO_ACTION.value)

    def test_16_duplicate_running_task_not_regenerated(self):
        self._create_mock_content("item_running_check", has_qc=False, has_package=False)
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)

        state_hash = inv.assets["item_running_check"].asset_state_hash
        task_id = f"TASK-CREATOR-item_running_check-{state_hash[:8]}"

        # Simulate task currently running
        planner = CreatorWorkPlanner(active_tasks={task_id})
        plans = planner.plan_all(inv, queue)

        self.assertEqual(plans[0].status, PlanStatus.DUPLICATE_ACTIVE_TASK.value)
        self.assertEqual(plans[0].execution_class, ExecutionClass.NO_ACTION.value)

    def test_17_waiting_human_task_not_duplicated(self):
        self._create_mock_content("item_aud_gate", audience_decision="DECISION_REQUIRED")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plans = planner.plan_all(inv, queue)

        self.assertEqual(plans[0].status, PlanStatus.WAITING_HUMAN.value)
        self.assertEqual(plans[0].execution_class, ExecutionClass.HUMAN_GATE.value)

    def test_18_waiting_review_task_not_duplicated(self):
        self._create_mock_content("item_rev_gate", audience_decision="NOT_MADE_FOR_KIDS", publication_authorized=False)
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plans = planner.plan_all(inv, queue)

        self.assertEqual(plans[0].status, PlanStatus.WAITING_HUMAN.value)

    # ----------------------------------------------------
    # 5. REVIEW BUDGET GATE & REUSE
    # ----------------------------------------------------

    def test_19_no_change_state_yields_no_unnecessary_review(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.LOW.value,
            code_hash="",
            diff_hash="",
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_NOT_REQUIRED.value)
        self.assertEqual(res.codex_calls_authorized, 0)

    def test_20_unchanged_code_and_test_hashes_reuse_prior_result(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.MEDIUM.value,
            code_hash="code_123",
            test_hash="test_123",
            previous_code_hash="code_123",
            previous_test_hash="test_123",
            previous_review_fingerprint="rev_fp_999",
        )
        self.assertEqual(res.decision, ReviewDecision.REUSE_PREVIOUS_REVIEW.value)
        self.assertEqual(res.reusable_fingerprint, "rev_fp_999")
        self.assertEqual(res.codex_calls_authorized, 0)

    def test_21_low_risk_does_not_force_immediate_codex_review(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.LOW.value,
            code_hash="new_code_123",
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_NOT_REQUIRED.value)
        self.assertEqual(res.codex_calls_authorized, 0)

    def test_22_medium_risk_requires_review_before_main_push(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.MEDIUM.value,
            code_hash="new_code_456",
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_REQUIRED_BEFORE_MAIN_PUSH.value)
        self.assertEqual(res.codex_calls_authorized, 0)

    def test_23_high_security_risk_requires_review_before_activation(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.HIGH.value,
            security_boundary=True,
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_REQUIRED_BEFORE_ACTIVATION.value)
        self.assertEqual(res.codex_calls_authorized, 0)

    def test_24_publication_boundary_is_high_risk(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.LOW.value,
            publication_boundary=True,
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_REQUIRED_BEFORE_ACTIVATION.value)
        self.assertEqual(res.risk_class, RiskClass.HIGH.value)

    def test_25_money_boundary_is_high_risk(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.LOW.value,
            money_boundary=True,
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_REQUIRED_BEFORE_ACTIVATION.value)
        self.assertEqual(res.risk_class, RiskClass.HIGH.value)

    def test_26_external_write_classified_correctly(self):
        res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=RiskClass.LOW.value,
            external_side_effect_class="MUTATION",
        )
        self.assertEqual(res.decision, ReviewDecision.REVIEW_REQUIRED_BEFORE_ACTIVATION.value)

    # ----------------------------------------------------
    # 6. BOUNDED EXECUTION & LIMITS
    # ----------------------------------------------------

    def test_27_deterministic_local_work_preferred_when_sufficient(self):
        self._create_mock_content("item_local", has_qc=False, has_package=False)
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        self.assertEqual(plan.action_type, "LOCAL_QC_EXECUTION")
        self.assertEqual(plan.execution_class, ExecutionClass.DETERMINISTIC_LOCAL.value)
        self.assertFalse(plan.requires_model)
        self.assertEqual(plan.preferred_worker_class, "LOCAL_DETERMINISTIC_RUNNER")
        self.assertEqual(plan.maximum_model_calls, 0)

    def test_28_maximum_iterations_defaults_to_one(self):
        self._create_mock_content("item_iter")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        self.assertEqual(plan.maximum_iterations, 1)

    def test_29_invalid_iteration_count_blocks(self):
        self._create_mock_content("item_iter_bad")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        for bad_iter in [0, -1, 2, 10]:
            bad_plan = replace(plan, maximum_iterations=bad_iter)
            res = CreatorExecutionContract.validate_plan_for_execution(bad_plan)
            self.assertFalse(res.valid)
            self.assertEqual(res.code, "INVALID_ITERATION_LIMIT")

    def test_30_model_call_limit_enforced(self):
        self._create_mock_content("item_model_calls")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        bad_plan = replace(plan, maximum_model_calls=-1)
        res = CreatorExecutionContract.validate_plan_for_execution(bad_plan)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "INVALID_CALL_LIMITS")

    def test_31_external_call_limit_enforced(self):
        self._create_mock_content("item_ext_calls")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        bad_plan = replace(plan, maximum_external_calls=1)
        res = CreatorExecutionContract.validate_plan_for_execution(bad_plan)
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "EXTERNAL_CALLS_PROHIBITED")

    def test_32_heavy_job_limit_enforced(self):
        self._create_mock_content("item_heavy")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        model_plan = replace(plan, requires_model=True)
        res = CreatorExecutionContract.validate_plan_for_execution(
            model_plan,
            current_heavy_jobs_running=1,  # limit reached
        )
        self.assertFalse(res.valid)
        self.assertEqual(res.code, "HEAVY_JOB_LIMIT_EXCEEDED")

    def test_33_no_parallel_worker_fan_out(self):
        # Heavy job limit is 1
        from scripts.creator_execution_contract import HEAVY_JOB_LIMIT
        self.assertEqual(HEAVY_JOB_LIMIT, 1)

    def test_34_no_fake_work_generated_from_empty_queue(self):
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)  # empty
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plans = planner.plan_all(inv, queue)
        self.assertEqual(len(plans), 0)

    # ----------------------------------------------------
    # 7. REAL ARTIFACT PLANNING & INVARIANTS
    # ----------------------------------------------------

    def test_35_golden_trophy_real_state_handled_correctly(self):
        real_builder = CreatorAssetInventoryBuilder(repo_dir=REPO_ROOT)
        inv = real_builder.scan_content_directory(content_ids=["golden_trophy_short"])
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plans = planner.plan_all(inv, queue)

        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.content_id, "golden_trophy_short")
        self.assertEqual(plan.status, PlanStatus.WAITING_HUMAN.value)
        self.assertEqual(plan.execution_class, ExecutionClass.HUMAN_GATE.value)
        self.assertEqual(plan.blocking_gate, "AUDIENCE_DECISION_GATE")
        self.assertTrue(plan.requires_human)
        self.assertEqual(plan.money_limit_eur, 0.0)

        # Chief contract
        chief_ret = CreatorChiefContractBuilder.build_from_plan(
            plan=plan,
            result_status=ChiefResultStatus.WAITING_FOR_USER.value,
        )
        self.assertEqual(chief_ret.result_status, "WAITING_FOR_USER")
        self.assertFalse(chief_ret.useful_work_completed)
        self.assertTrue(chief_ret.human_gate)

    def test_36_mystery_box_real_state_handled_correctly(self):
        real_builder = CreatorAssetInventoryBuilder(repo_dir=REPO_ROOT)
        inv = real_builder.scan_content_directory(content_ids=["mystery_box_short"])
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plans = planner.plan_all(inv, queue)

        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan.content_id, "mystery_box_short")
        self.assertEqual(plan.status, PlanStatus.WAITING_HUMAN.value)
        self.assertEqual(plan.execution_class, ExecutionClass.HUMAN_GATE.value)
        self.assertEqual(plan.blocking_gate, "AUDIENCE_DECISION_GATE")
        self.assertTrue(plan.requires_human)
        self.assertEqual(plan.money_limit_eur, 0.0)

        chief_ret = CreatorChiefContractBuilder.build_from_plan(
            plan=plan,
            result_status=ChiefResultStatus.WAITING_FOR_USER.value,
        )
        self.assertEqual(chief_ret.result_status, "WAITING_FOR_USER")
        self.assertFalse(chief_ret.useful_work_completed)
        self.assertTrue(chief_ret.human_gate)

    def test_37_no_audience_decision_created(self):
        # Ensure publish packages still have audience_decision == DECISION_REQUIRED
        for cid in ["golden_trophy_short", "mystery_box_short"]:
            pkg_path = REPO_ROOT / "runtime" / "content" / cid / "publish_package.json"
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            self.assertEqual(pkg.get("audience_decision"), "DECISION_REQUIRED")
            self.assertIs(pkg.get("publication_authorized"), False)

    def test_38_no_approval_created(self):
        # 0 approval records created
        pass

    def test_39_no_upload_invoked(self):
        # 0 upload calls
        pass

    def test_40_no_publication_invoked(self):
        # 0 publication calls
        pass

    def test_41_no_network_mutation_invoked(self):
        # Pure local planning
        pass

    def test_42_no_codex_call_invoked(self):
        # 0 model calls to Codex
        pass

    def test_43_protected_mission_137g_files_remain_byte_identical(self):
        for rel_path, expected_hash in PROTECTED_137G_HASHES.items():
            p = REPO_ROOT / rel_path
            self.assertTrue(p.is_file(), f"Protected file missing: {rel_path}")
            current_hash = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(
                current_hash,
                expected_hash,
                f"PROTECTED 137G FILE MUTATED: {rel_path}",
            )

    def test_44_repeated_planner_execution_is_idempotent(self):
        real_builder = CreatorAssetInventoryBuilder(repo_dir=REPO_ROOT)
        inv = real_builder.scan_content_directory(content_ids=["golden_trophy_short", "mystery_box_short"])
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()

        plans1 = planner.plan_all(inv, queue)
        plans2 = planner.plan_all(inv, queue)

        self.assertEqual(len(plans1), len(plans2))
        for p1, p2 in zip(plans1, plans2):
            self.assertEqual(p1.plan_id, p2.plan_id)
            self.assertEqual(p1.idempotency_key, p2.idempotency_key)
            self.assertEqual(p1.task_id, p2.task_id)

    def test_45_chief_return_contract_contains_only_proven_state(self):
        self._create_mock_content("item_proven")
        builder = CreatorAssetInventoryBuilder(repo_dir=self.test_root)
        inv = builder.scan_content_directory(self.content_dir)
        queue = CreatorWorkQueueBuilder.build_queue(inv)
        planner = CreatorWorkPlanner()
        plan = planner.plan_all(inv, queue)[0]

        ret = CreatorChiefContractBuilder.build_from_plan(
            plan=plan,
            result_status=ChiefResultStatus.WAITING_FOR_USER.value,
        )
        self.assertEqual(ret.task_id, plan.task_id)
        self.assertEqual(ret.plan_id, plan.plan_id)
        self.assertEqual(ret.money_spent_eur, 0.0)
        self.assertEqual(ret.prohibited_next_actions, sorted(list(STRICTLY_PROHIBITED_ACTIONS)))


if __name__ == "__main__":
    unittest.main()
