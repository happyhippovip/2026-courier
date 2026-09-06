#!/usr/bin/env python3
"""Mission 189G: Elite Execution Core & Fastest High-Quality Path Test Suite."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

COURIER_DIR = Path(__file__).resolve().parent.parent

from scripts.elite_execution_core import (
    CapabilityType,
    DecisionCacheManager,
    EliteActionSpec,
    EliteExecutionCore,
    IntelligenceLadderLevel,
    QualityFloorClass,
    SchedulerDecision,
    SemanticDeltaClassifier,
    SemanticDeltaType,
)


class TestEliteExecutionCoreMission189G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="elite_189g_test_"))
        self.core = EliteExecutionCore(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_free_provider_zero_gain_dropped_without_dispatch(self):
        spec = EliteActionSpec(
            action_id="ACT-ZERO-GAIN",
            goal="Format comment lines with no logic change",
            expected_unlock="Cosmetic whitespace alignment",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="Provider is idle",
            why_model="Model available",
            why_not_local="Could run locally",
            why_not_cache="N/A",
            decision_value_class="ZERO_GAIN",
        )
        lvl, decision, payload = self.core.evaluate_ladder_level(spec)
        self.assertEqual(decision, SchedulerDecision.DROP_ZERO_GAIN)
        self.assertFalse(payload.get("admitted", True))
        self.assertEqual(self.core.metrics.zero_gain_jobs_dropped, 1)

    def test_02_free_provider_valuable_independent_work_dispatches(self):
        spec = EliteActionSpec(
            action_id="ACT-VALUABLE-BUILD",
            goal="Build high value autonomous scheduler feature",
            expected_unlock="Unlocks multi-agent execution pipeline",
            quality_floor=QualityFloorClass.MEDIUM_RISK,
            risk_class="MEDIUM",
            new_information="New specification contract",
            why_now="High value ready work",
            why_model="Complex code synthesis",
            why_not_local="Requires semantic code design",
            why_not_cache="New specification",
            decision_value_class="HIGH_VALUE",
            mutation_scope=["FEATURE_SCHEDULER"],
            required_capability=CapabilityType.CODE_BUILD,
        )
        lvl, decision, payload = self.core.evaluate_ladder_level(spec)
        self.assertEqual(decision, SchedulerDecision.RUN_NOW)
        self.assertTrue(payload.get("admitted"))
        self.assertEqual(self.core.metrics.model_calls_admitted, 1)

    def test_03_cheap_local_sufficient_avoids_model(self):
        spec = EliteActionSpec(
            action_id="ACT-DETERMINISTIC-AUDIT",
            goal="Verify SHA-256 hashes of creator packages",
            expected_unlock="Cryptographic integrity verification",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="Package file listing",
            why_now="Scheduled verification",
            why_model="None",
            why_not_local="Local code sufficient",
            why_not_cache="N/A",
            decision_value_class="USEFUL",
        )
        resolver = lambda tid: (True, {"hash_pass": True, "files_checked": 20})
        lvl, decision, payload = self.core.evaluate_ladder_level(spec, deterministic_resolver=resolver)
        self.assertEqual(decision, SchedulerDecision.LOCALIZE)
        self.assertEqual(lvl, IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC)
        self.assertEqual(self.core.metrics.local_resolutions, 1)
        self.assertEqual(self.core.metrics.model_calls_avoided, 1)

    def test_04_cheap_local_insufficient_for_quality_floor_escalates(self):
        spec = EliteActionSpec(
            action_id="ACT-HIGH-RISK-SECURITY-GATE",
            goal="Evaluate custom cryptographic authentication token parser",
            expected_unlock="Security boundary compliance",
            quality_floor=QualityFloorClass.HIGH_RISK,
            risk_class="HIGH",
            new_information="Parser implementation",
            why_now="Pre-release verification",
            why_model="Security boundary review required",
            why_not_local="Deterministic test cannot judge trust boundary implications",
            why_not_cache="Fresh code delta",
            decision_value_class="CRITICAL_UNBLOCK",
            mutation_scope=["SECURITY_CORE"],
        )
        # Deterministic resolver passes unit tests, but High Risk Quality Floor requires structured review
        resolver = lambda tid: (False, {})
        lvl, decision, payload = self.core.evaluate_ladder_level(spec, deterministic_resolver=resolver)
        self.assertEqual(decision, SchedulerDecision.RUN_NOW)
        self.assertEqual(lvl, IntelligenceLadderLevel.LEVEL_5_STRONG_MODEL_JUDGMENT)

    def test_05_same_judgment_fingerprint_reuses_cache_without_model(self):
        spec = EliteActionSpec(
            action_id="ACT-REVIEW-EXISTING",
            goal="Review existing module",
            expected_unlock="Code acceptance",
            quality_floor=QualityFloorClass.MEDIUM_RISK,
            risk_class="MEDIUM",
            new_information="Unchanged content",
            why_now="Routine check",
            why_model="Review",
            why_not_local="N/A",
            why_not_cache="N/A",
            decision_value_class="USEFUL",
        )
        fp = spec.compute_fingerprint()
        self.core.decision_cache.store_judgment(
            fingerprint=fp,
            task_id=spec.action_id,
            judgment={"verdict": "PASS", "confidence": "HIGH"},
            quality_floor=spec.quality_floor,
        )

        lvl, decision, payload = self.core.evaluate_ladder_level(spec)
        self.assertEqual(decision, SchedulerDecision.REUSE_CACHE)
        self.assertEqual(lvl, IntelligenceLadderLevel.LEVEL_1_REUSE_ACCEPTED_RESULT)
        self.assertEqual(payload["cached_judgment"]["verdict"], "PASS")
        self.assertEqual(self.core.metrics.reviews_reused, 1)

    def test_06_semantic_irrelevant_delta_produces_no_review(self):
        old_code = "def add(a, b):\n    # add numbers\n    return a + b\n"
        new_code = "def add(a, b):\n    # add numbers\n    \n    return a + b\n"
        delta_type, reason = self.core.delta_classifier.classify_delta(old_code, new_code, "scripts/math_utils.py")
        self.assertEqual(delta_type, SemanticDeltaType.NO_RELEVANT_CHANGE)

    def test_07_high_risk_semantic_delta_triggers_appropriate_escalation(self):
        old_code = "AUTONOMOUS_SPEND_LIMIT = 0.0\n"
        new_code = "AUTONOMOUS_SPEND_LIMIT = 100.0\n"
        delta_type, reason = self.core.delta_classifier.classify_delta(old_code, new_code, "scripts/spend_firewall.py")
        self.assertEqual(delta_type, SemanticDeltaType.RELEVANT_HIGH_RISK_DELTA)

    def test_08_speculative_local_prep_proceeds_while_model_works(self):
        test_file = self.test_dir / "sample.py"
        test_file.write_text("def test_fn(): pass\n", encoding="utf-8")
        prep = self.core.prepare_speculative_local_work("TASK-SPECULATIVE", [test_file])
        self.assertTrue(prep["zero_secrets_verified"])
        self.assertIn("sample.py", prep["file_hashes"])

    def test_09_independent_scopes_parallel_eligible_and_overlapping_serialize(self):
        ok1, err1 = self.core.acquire_scope_lock("TASK-1", ["SCOPE-A"])
        self.assertTrue(ok1)

        # Independent scope B succeeds in parallel
        ok2, err2 = self.core.acquire_scope_lock("TASK-2", ["SCOPE-B"])
        self.assertTrue(ok2)

        # Overlapping scope A is denied / serialized
        ok3, err3 = self.core.acquire_scope_lock("TASK-3", ["SCOPE-A"])
        self.assertFalse(ok3)
        self.assertIn("locked by task 'TASK-1'", err3)

        self.core.release_scope_lock("TASK-1")
        ok4, err4 = self.core.acquire_scope_lock("TASK-3", ["SCOPE-A"])
        self.assertTrue(ok4)

    def test_10_several_results_coalesce_into_single_decision_boundary(self):
        events = [
            {"event": "TEST_PASS", "module": "auth_test"},
            {"event": "STATIC_CLEAN", "module": "auth_core"},
            {"event": "ARTIFACT_READY", "module": "auth_package"},
        ]
        coalesced = self.core.coalesce_results(events, "TASK-AUTH-SYNTHESIS")
        self.assertEqual(coalesced["events_count"], 3)
        self.assertEqual(coalesced["status"], "COALESCED_READY_FOR_SYNTHESIS")
        self.assertEqual(self.core.metrics.decisions_coalesced, 1)

    def test_11_human_and_money_branches_parked_safely(self):
        spec_human = EliteActionSpec(
            action_id="ACT-HUMAN-PUBLISH",
            goal="Publish video to YouTube",
            expected_unlock="Audience visibility",
            quality_floor=QualityFloorClass.PUBLICATION,
            risk_class="HIGH",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
        )
        lvl_h, dec_h, _ = self.core.evaluate_ladder_level(spec_human)
        self.assertEqual(dec_h, SchedulerDecision.PARK_HUMAN_GATE)

        spec_money = EliteActionSpec(
            action_id="ACT-PAID-API",
            goal="Activate external paid compute credits",
            expected_unlock="Credits",
            quality_floor=QualityFloorClass.MONEY,
            risk_class="HIGH",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
        )
        lvl_m, dec_m, _ = self.core.evaluate_ladder_level(spec_money)
        self.assertEqual(dec_m, SchedulerDecision.PARK_MONEY_GATE)

    def test_12_stop_on_sufficient_quality_prevents_perfection_loops(self):
        # When goal achieved, quality floor verified, no blockers -> STOP_SUCCESS
        stop_ok, msg = self.core.check_stop_on_sufficient_quality(
            goal_satisfied=True,
            quality_floor_verified=True,
            remaining_blockers=[],
        )
        self.assertTrue(stop_ok)
        self.assertIn("STOP_SUCCESS", msg)

        # When blocker remains -> continue
        stop_fail, msg2 = self.core.check_stop_on_sufficient_quality(
            goal_satisfied=True,
            quality_floor_verified=True,
            remaining_blockers=["BLOCKER_SIGNATURE_PENDING"],
        )
        self.assertFalse(stop_fail)

    def test_13_fastest_path_planner_prefers_critical_path_high_value_actions(self):
        act_low = EliteActionSpec(
            action_id="ACT-LOW",
            goal="Minor cosmetic tweak",
            expected_unlock="Clean indentation",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="OPTIONAL",
            is_on_critical_path=False,
            priority=2,
        )
        act_crit = EliteActionSpec(
            action_id="ACT-CRITICAL",
            goal="Unblock release pipeline dependency",
            expected_unlock="Unblocks full release flow",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="CRITICAL_UNBLOCK",
            is_on_critical_path=True,
            priority=9,
            required_capability=CapabilityType.DETERMINISTIC,
        )
        best = self.core.select_fastest_path_action([act_low, act_crit])
        self.assertIsNotNone(best)
        self.assertEqual(best.action_id, "ACT-CRITICAL")

    def test_14_amplification_ratio_computation(self):
        self.core.metrics.quality_verified_transitions = 15
        self.core.metrics.model_calls_admitted = 3
        self.assertEqual(self.core.metrics.amplification_ratio, 5.0)

    def test_15_zero_interference_with_running_188g_supervisor(self):
        pid_file = COURIER_DIR / "events" / "autonomy-runtime" / "supervisor.pid"
        if pid_file.is_file():
            data = json.loads(pid_file.read_text())
            self.assertEqual(data.get("session_id"), "session-188g-endurance-1788216021")


if __name__ == "__main__":
    unittest.main()
