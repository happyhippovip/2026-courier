#!/usr/bin/env python3
"""Mission 190G: Organization-Wide Elite Autonomy Activation Test Suite."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

COURIER_DIR = Path(__file__).resolve().parent.parent

from scripts.elite_execution_core import (
    CapabilityType,
    EliteActionSpec,
    EliteExecutionCore,
    IntelligenceLadderLevel,
    QualityFloorClass,
    SchedulerDecision,
)
from scripts.organization_elite_policy import (
    AnomalyDomain,
    AnomalySeverity,
    CentralElitePolicyRegistry,
    FastFinishEngine,
    OrganizationPolicyConfig,
    SnitchAnomalyManager,
)


class TestOrganizationElitePolicyMission190G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="org_elite_190g_test_"))
        CentralElitePolicyRegistry._instance = None
        self.registry = CentralElitePolicyRegistry(repo_dir=self.test_dir)
        self.core = self.registry.core
        self.snitch_manager = self.registry.snitch_manager
        self.fast_finish_engine = self.registry.fast_finish_engine

    def tearDown(self):
        CentralElitePolicyRegistry._instance = None
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_existing_agent_inherits_elite_policy(self):
        agent_info = self.registry.inherit_policy_for_agent("agent-chief-commander")
        self.assertIsNotNone(agent_info)
        self.assertEqual(agent_info["role"], "CHIEF_COMMANDER")
        policy = agent_info["inherited_policy"]
        self.assertEqual(policy["spend_limit_eur"], 0.0)
        self.assertEqual(policy["publication_inference"], "DENY")
        self.assertTrue(policy["wake_on_evidence"])
        self.assertTrue(policy["quality_floor_enforced"])
        self.assertTrue(policy["snitch_on_anomaly_active"])

    def test_02_newly_created_future_test_agent_inherits_elite_policy(self):
        future_agent = self.registry.inherit_policy_for_agent("agent-future-2027-creator", role="FUTURE_CREATOR_BOT")
        self.assertIsNotNone(future_agent)
        self.assertEqual(future_agent["role"], "FUTURE_CREATOR_BOT")
        policy = future_agent["inherited_policy"]
        self.assertEqual(policy["spend_limit_eur"], 0.0)
        self.assertEqual(policy["publication_inference"], "DENY")
        self.assertTrue(policy["anti_swarm_enabled"])

    def test_03_fast_finish_prioritizes_critical_path(self):
        self.registry.set_fast_finish_mode(True)
        act_non_crit = EliteActionSpec(
            action_id="ACT-NON-CRITICAL",
            goal="Format docstrings",
            expected_unlock="Cosmetic formatting",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="OPTIONAL",
            is_on_critical_path=False,
            priority=3,
        )
        act_crit = EliteActionSpec(
            action_id="ACT-CRITICAL-UNBLOCK",
            goal="Resolve release gate dependency",
            expected_unlock="Unblocks deployment milestone",
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

        plan = self.fast_finish_engine.optimize_action_plan([act_non_crit, act_crit], "GOAL_FAST_RELEASE")
        self.assertEqual(plan["status"], "PLAN_OPTIMIZED")
        self.assertEqual(plan["primary_action"], "ACT-CRITICAL-UNBLOCK")

    def test_04_fast_finish_parallelizes_safe_independent_valuable_work(self):
        self.registry.set_fast_finish_mode(True)
        act1 = EliteActionSpec(
            action_id="ACT-SCOPE-A",
            goal="Build feature A",
            expected_unlock="Feature A",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="HIGH_VALUE",
            mutation_scope=["SCOPE_A"],
            priority=8,
        )
        act2 = EliteActionSpec(
            action_id="ACT-SCOPE-B",
            goal="Build feature B",
            expected_unlock="Feature B",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="HIGH_VALUE",
            mutation_scope=["SCOPE_B"],
            priority=7,
        )
        plan = self.fast_finish_engine.optimize_action_plan([act1, act2], "GOAL_PARALLEL_BUILD")
        self.assertEqual(plan["selected_count"], 2)
        self.assertIn("ACT-SCOPE-B", plan["parallel_actions"])

    def test_05_fast_finish_does_not_bypass_quality_floor(self):
        spec_high_risk = EliteActionSpec(
            action_id="ACT-FAST-FINISH-SECURITY",
            goal="Security token handler",
            expected_unlock="Token processing",
            quality_floor=QualityFloorClass.SECURITY,
            risk_class="HIGH",
            new_information="",
            why_now="Fast finish active",
            why_model="Security judgment",
            why_not_local="N/A",
            why_not_cache="N/A",
            decision_value_class="CRITICAL_UNBLOCK",
            mutation_scope=["SECURITY_SCOPE"],
        )
        lvl, decision, payload = self.core.evaluate_ladder_level(spec_high_risk)
        self.assertIn(decision, (SchedulerDecision.RUN_NOW, SchedulerDecision.LOCALIZE))
        # Quality floor requires ZERO_SECRET_SCAN and structured verification
        self.assertIn(lvl, (IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC, IntelligenceLadderLevel.LEVEL_4_TARGETED_MODEL_JUDGMENT, IntelligenceLadderLevel.LEVEL_5_STRONG_MODEL_JUDGMENT))

    def test_06_fast_finish_does_not_bypass_money_gate(self):
        spec_money = EliteActionSpec(
            action_id="ACT-PAID-TRANSACTION",
            goal="Purchase compute tokens",
            expected_unlock="Tokens",
            quality_floor=QualityFloorClass.MONEY,
            risk_class="HIGH",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
        )
        lvl, decision, payload = self.core.evaluate_ladder_level(spec_money)
        self.assertEqual(decision, SchedulerDecision.PARK_MONEY_GATE)
        self.assertEqual(lvl, IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE)

    def test_07_fast_finish_does_not_bypass_publication_human_gate(self):
        spec_pub = EliteActionSpec(
            action_id="ACT-FAST-PUBLISH",
            goal="Release video publicly",
            expected_unlock="Public release",
            quality_floor=QualityFloorClass.PUBLICATION,
            risk_class="HIGH",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
        )
        lvl, decision, payload = self.core.evaluate_ladder_level(spec_pub)
        self.assertEqual(decision, SchedulerDecision.PARK_HUMAN_GATE)
        self.assertEqual(lvl, IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE)

    def test_08_harmless_anomaly_does_not_create_expensive_escalation(self):
        sev, event, msg = self.snitch_manager.report_observation(
            reporting_agent="agent-qc-inspector",
            domain=AnomalyDomain.PROCESS_BEHAVIOR,
            observed="Package verified with 0 errors",
            expected="Package verified with 0 errors",
        )
        self.assertEqual(sev, AnomalySeverity.NORMAL)
        self.assertIsNone(event)

    def test_09_unknown_triggers_bounded_local_evidence_collection(self):
        sev, event, action = self.snitch_manager.report_observation(
            reporting_agent="agent-resource-intelligence-officer",
            domain=AnomalyDomain.PROCESS_BEHAVIOR,
            observed="PID 99999 exited without log",
            expected="Process running or logged termination",
            affected_scope="RUNTIME_PROCESSES",
        )
        self.assertEqual(sev, AnomalySeverity.UNKNOWN)
        self.assertIsNotNone(event)
        self.assertIn("LOCAL_INVESTIGATION", action)

    def test_10_suspicious_creates_structured_snitch_event(self):
        sev, event, action = self.snitch_manager.report_observation(
            reporting_agent="agent-security-auditor",
            domain=AnomalyDomain.STATE_CONTRADICTION,
            observed="Barrier marked satisfied without worker 2 result",
            expected="Barrier satisfied only with both workers",
            affected_scope="CONTROL_PLANE",
            affected_branch="SYNTHESIS_BRANCH",
        )
        self.assertEqual(sev, AnomalySeverity.SUSPICIOUS)
        self.assertIsNotNone(event)
        self.assertEqual(event.risk_level, "HIGH")

    def test_11_critical_fails_closed_for_affected_branch(self):
        sev, event, action = self.snitch_manager.report_observation(
            reporting_agent="agent-publication-officer",
            domain=AnomalyDomain.PUBLICATION_ATTEMPT,
            observed="Unapproved public upload initiated",
            expected="Publication firewall strictly blocks without signed approval",
            affected_scope="PUBLICATION_SCOPE",
            affected_branch="RELEASE_BRANCH",
        )
        self.assertEqual(sev, AnomalySeverity.CRITICAL)
        self.assertTrue(self.snitch_manager.is_branch_quarantined("RELEASE_BRANCH"))
        self.assertTrue(self.snitch_manager.is_scope_quarantined("PUBLICATION_SCOPE"))

    def test_12_independent_branch_continues_after_branch_local_anomaly(self):
        # Freeze Release branch
        self.snitch_manager.report_observation(
            reporting_agent="agent-publication-officer",
            domain=AnomalyDomain.PUBLICATION_ATTEMPT,
            observed="Unapproved upload",
            expected="No upload",
            affected_branch="RELEASE_BRANCH",
        )
        self.assertTrue(self.snitch_manager.is_branch_quarantined("RELEASE_BRANCH"))
        # Independent local build branch remains unquarantined and running
        self.assertFalse(self.snitch_manager.is_branch_quarantined("LOCAL_BUILD_BRANCH"))

    def test_13_duplicate_anomaly_is_suppressed(self):
        sev1, ev1, msg1 = self.snitch_manager.report_observation(
            reporting_agent="agent-qc",
            domain=AnomalyDomain.FINGERPRINT_MISMATCH,
            observed="Hash ABC does not match XYZ",
            expected="Hash ABC matches ABC",
            affected_branch="QC_BRANCH",
        )
        self.assertNotIn("DUPLICATE_SUPPRESSED", msg1)

        # Report exact duplicate
        sev2, ev2, msg2 = self.snitch_manager.report_observation(
            reporting_agent="agent-qc",
            domain=AnomalyDomain.FINGERPRINT_MISMATCH,
            observed="Hash ABC does not match XYZ",
            expected="Hash ABC matches ABC",
            affected_branch="QC_BRANCH",
        )
        self.assertIn("DUPLICATE_SUPPRESSED", msg2)
        self.assertEqual(self.snitch_manager.anomalies_suppressed_duplicate, 1)

    def test_14_new_relevant_anomaly_delta_can_reescalate(self):
        sev1, _, _ = self.snitch_manager.report_observation(
            reporting_agent="agent-qc",
            domain=AnomalyDomain.FINGERPRINT_MISMATCH,
            observed="Hash delta in file 1",
            expected="Hash matches",
            affected_branch="BRANCH_1",
        )
        # New observation with different content
        sev2, _, msg2 = self.snitch_manager.report_observation(
            reporting_agent="agent-qc",
            domain=AnomalyDomain.FINGERPRINT_MISMATCH,
            observed="Hash delta in file 2",
            expected="Hash matches",
            affected_branch="BRANCH_2",
        )
        self.assertNotIn("DUPLICATE_SUPPRESSED", msg2)

    def test_15_no_secrets_appear_in_anomaly_artifact(self):
        sev, event, _ = self.snitch_manager.report_observation(
            reporting_agent="agent-sec",
            domain=AnomalyDomain.SECRET_EXPOSURE,
            observed="Found client_secret=abcdef123456 in file",
            expected="Zero secrets stored",
        )
        self.assertIsNotNone(event)
        self.assertNotIn("abcdef123456", event.observed_state)
        self.assertIn("[REDACTED", event.observed_state)

    def test_16_idle_no_new_evidence_causes_zero_model_work(self):
        # When no active ready opportunities exist, model calls admitted remains 0
        initial_calls = self.core.metrics.model_calls_admitted
        act_none = self.core.select_fastest_path_action([])
        self.assertIsNone(act_none)
        self.assertEqual(self.core.metrics.model_calls_admitted, initial_calls)

    def test_17_twenty_five_logical_agents_do_not_imply_25_model_workers(self):
        self.assertGreaterEqual(len(self.registry.registered_agents), 25)
        # All 25 agents inherit central admission without spawning model sessions
        self.assertEqual(self.core.metrics.model_calls_admitted, 0)

    def test_18_free_provider_plus_zero_gain_causes_no_dispatch(self):
        spec_zg = EliteActionSpec(
            action_id="ACT-ZERO-GAIN-2",
            goal="Format markdown blank line",
            expected_unlock="Cosmetic blank line",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="ZERO_GAIN",
        )
        lvl, dec, _ = self.core.evaluate_ladder_level(spec_zg)
        self.assertEqual(dec, SchedulerDecision.DROP_ZERO_GAIN)

    def test_19_free_provider_plus_valuable_independent_work_dispatches(self):
        spec_val = EliteActionSpec(
            action_id="ACT-VALUABLE-2",
            goal="Synthesize release orchestrator logic",
            expected_unlock="Automates pipeline release",
            quality_floor=QualityFloorClass.MEDIUM_RISK,
            risk_class="MEDIUM",
            new_information="Architecture contract",
            why_now="Ready for implementation",
            why_model="Complex synthesis",
            why_not_local="Requires semantic reasoning",
            why_not_cache="New design",
            decision_value_class="HIGH_VALUE",
            mutation_scope=["ORCHESTRATION_CORE"],
            required_capability=CapabilityType.CODE_BUILD,
        )
        lvl, dec, payload = self.core.evaluate_ladder_level(spec_val)
        self.assertEqual(dec, SchedulerDecision.RUN_NOW)
        self.assertTrue(payload.get("admitted"))

    def test_20_sufficient_quality_plus_completed_goal_yields_stop_success(self):
        stop_ok, msg = self.core.check_stop_on_sufficient_quality(
            goal_satisfied=True,
            quality_floor_verified=True,
            remaining_blockers=[],
        )
        self.assertTrue(stop_ok)
        self.assertIn("STOP_SUCCESS", msg)


if __name__ == "__main__":
    unittest.main()
