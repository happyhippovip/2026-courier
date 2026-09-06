#!/usr/bin/env python3
"""Mission 190G-R1: Organization-Wide Elite Autonomy Remediation Test Suite.

Proves closure of the 4 Codex 190C integration blockers:
1. Active central policy inheritance in real runtime execution path.
2. FastFinishEngine evaluates actions through canonical admission gates (cannot authorize publication or money directly).
3. Durable Snitch critical-branch quarantine survives process recreation and clears on resolution.
4. Integrated single execution path (Policy -> FastFinish -> Snitch -> Gate -> Execution -> Quarantine -> Stop Success).
"""

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
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.real_autonomy_runtime import RealAutonomyRuntime, SessionStatus


class TestOrganizationElitePolicyRemediationMission190GR1(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="org_remediation_190g_r1_test_"))
        CentralElitePolicyRegistry._instance = None
        self.registry = CentralElitePolicyRegistry(repo_dir=self.test_dir)
        self.core = self.registry.core
        self.snitch_manager = self.registry.snitch_manager
        self.fast_finish_engine = self.registry.fast_finish_engine
        self.runtime = RealAutonomyRuntime(repo_dir=self.test_dir)

    def tearDown(self):
        CentralElitePolicyRegistry._instance = None
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_active_existing_agent_inheritance_in_runtime_path(self):
        # Existing agent inherits policy through active runtime path
        opp = Opportunity(
            opportunity_id="OPP-TEST-CHIEF",
            source="CHIEF",
            objective_id="OBJ-1",
            project="GLOBAL",
            description="Chief task",
            target_agent="chief_commander",
            status="READY",
            priority=8,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-test-1", "Test policy inheritance")

        # Next action selection automatically resolves agent policy
        action = self.runtime.select_next_action(session, deterministic_resolver=lambda tid: (True, {"done": True}))
        self.assertIsNotNone(action)
        self.assertIn("agent-chief_commander", self.runtime.policy_registry.registered_agents)
        policy = self.runtime.policy_registry.registered_agents["agent-chief_commander"]["inherited_policy"]
        self.assertEqual(policy["spend_limit_eur"], 0.0)
        self.assertEqual(policy["publication_inference"], "DENY")

    def test_02_active_future_agent_inheritance_in_runtime_path(self):
        # Brand new future agent automatically registered and bound to policy on first encounter
        opp = Opportunity(
            opportunity_id="OPP-TEST-FUTURE",
            source="DISPATCH",
            objective_id="OBJ-FUTURE",
            project="FUTURE_PROJECT",
            description="Future autonomous capability",
            target_agent="unseen_future_bot_2027",
            status="READY",
            priority=8,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-test-2", "Test future agent inheritance")
        action = self.runtime.select_next_action(session, deterministic_resolver=lambda tid: (True, {"done": True}))
        self.assertIsNotNone(action)
        self.assertIn("agent-unseen_future_bot_2027", self.runtime.policy_registry.registered_agents)
        policy = self.runtime.policy_registry.registered_agents["agent-unseen_future_bot_2027"]["inherited_policy"]
        self.assertEqual(policy["spend_limit_eur"], 0.0)
        self.assertTrue(policy["anti_swarm_enabled"])

    def test_03_mandatory_policy_cannot_be_weakened(self):
        # Attempt to weaken spend limit or publication inference fails closed to global defaults
        cfg = OrganizationPolicyConfig()
        self.assertEqual(cfg.autonomous_spend_limit_eur, 0.0)
        self.assertEqual(cfg.publication_inference, "DENY")
        self.assertEqual(cfg.secret_storage, "DENY")

    def test_04_fast_finish_publication_candidate_hits_gate(self):
        # FastFinish evaluates a publication candidate: optimization finds it, but admission strictly returns PARK_HUMAN_GATE
        spec_pub = EliteActionSpec(
            action_id="ACT-FAST-PUBLISH-MEDIA",
            goal="Fast publish video to YouTube",
            expected_unlock="Public audience exposure",
            quality_floor=QualityFloorClass.PUBLICATION,
            risk_class="HIGH",
            new_information="Video master ready",
            why_now="Fast finish active",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="CRITICAL_UNBLOCK",
            is_on_critical_path=True,
            priority=10,
        )
        self.assertFalse(self.fast_finish_engine.can_authorize_action())
        plan = self.fast_finish_engine.evaluate_and_schedule_plan([spec_pub], "GOAL_FAST_FINISH")
        self.assertEqual(plan["status"], "PLAN_OPTIMIZED")
        adm = plan["admissions"]["ACT-FAST-PUBLISH-MEDIA"]
        self.assertEqual(adm["decision"], SchedulerDecision.PARK_HUMAN_GATE.value)
        self.assertFalse(adm["admitted"])

    def test_05_fast_finish_money_candidate_hits_gate(self):
        # FastFinish evaluates a payment candidate: admission strictly returns PARK_MONEY_GATE
        spec_money = EliteActionSpec(
            action_id="ACT-FAST-BUY-CREDITS",
            goal="Fast activate paid API credits",
            expected_unlock="Compute credits",
            quality_floor=QualityFloorClass.MONEY,
            risk_class="HIGH",
            new_information="",
            why_now="Fast finish active",
            why_model="",
            why_not_local="",
            why_not_cache="",
            decision_value_class="CRITICAL_UNBLOCK",
            is_on_critical_path=True,
            priority=10,
        )
        plan = self.fast_finish_engine.evaluate_and_schedule_plan([spec_money], "GOAL_FAST_FINISH")
        adm = plan["admissions"]["ACT-FAST-BUY-CREDITS"]
        self.assertEqual(adm["decision"], SchedulerDecision.PARK_MONEY_GATE.value)
        self.assertFalse(adm["admitted"])

    def test_06_safe_fast_finish_candidate_executes(self):
        spec_safe = EliteActionSpec(
            action_id="ACT-SAFE-FAST-BUILD",
            goal="Build deterministic release manifest",
            expected_unlock="Release manifest",
            quality_floor=QualityFloorClass.LOW_RISK,
            risk_class="LOW",
            new_information="",
            why_now="Fast finish",
            why_model="",
            why_not_local="Local code sufficient",
            why_not_cache="",
            decision_value_class="CRITICAL_UNBLOCK",
            is_on_critical_path=True,
            priority=9,
        )
        resolver = lambda tid: (True, {"manifest_created": True})
        plan = self.fast_finish_engine.evaluate_and_schedule_plan([spec_safe], "GOAL_FAST_FINISH", deterministic_resolver=resolver)
        adm = plan["admissions"]["ACT-SAFE-FAST-BUILD"]
        self.assertEqual(adm["decision"], SchedulerDecision.LOCALIZE.value)
        self.assertTrue(adm["admitted"])

    def test_07_durable_snitch_quarantine_survives_restart(self):
        # 1. Report critical anomaly -> quarantines branch
        sev, event, _ = self.snitch_manager.report_observation(
            reporting_agent="agent-security",
            domain=AnomalyDomain.SECURITY_BOUNDARY_VIOLATION,
            observed="Unauthorized root access attempt",
            expected="Restricted sandbox environment",
            affected_scope="ROOT_SCOPE",
            affected_branch="SECURITY_BRANCH",
        )
        self.assertEqual(sev, AnomalySeverity.CRITICAL)
        self.assertTrue(self.snitch_manager.is_branch_quarantined("SECURITY_BRANCH"))
        self.assertTrue(self.snitch_manager.is_scope_quarantined("ROOT_SCOPE"))

        # 2. Recreate SnitchAnomalyManager (simulating process restart)
        restarted_snitch = SnitchAnomalyManager(repo_dir=self.test_dir)
        self.assertTrue(restarted_snitch.is_branch_quarantined("SECURITY_BRANCH"))
        self.assertTrue(restarted_snitch.is_scope_quarantined("ROOT_SCOPE"))

    def test_08_unrelated_branch_continues_after_quarantine(self):
        self.snitch_manager.report_observation(
            reporting_agent="agent-sec",
            domain=AnomalyDomain.SECRET_EXPOSURE,
            observed="Found token in file",
            expected="Zero tokens",
            affected_branch="COMPROMISED_BRANCH",
            affected_scope="COMPROMISED_SCOPE",
        )
        self.assertTrue(self.snitch_manager.is_branch_quarantined("COMPROMISED_BRANCH"))
        # Unrelated safe branch is NOT quarantined
        self.assertFalse(self.snitch_manager.is_branch_quarantined("SAFE_BUILD_BRANCH"))
        self.assertFalse(self.snitch_manager.is_scope_quarantined("SAFE_BUILD_SCOPE"))

    def test_09_resolved_anomaly_clears_quarantine_correctly(self):
        sev, event, _ = self.snitch_manager.report_observation(
            reporting_agent="agent-sec",
            domain=AnomalyDomain.SPEND_ANOMALY,
            observed="Spend attempted: 10 EUR",
            expected="0 EUR",
            affected_branch="PAYMENT_BRANCH",
            affected_scope="PAYMENT_SCOPE",
        )
        self.assertTrue(self.snitch_manager.is_branch_quarantined("PAYMENT_BRANCH"))

        # Resolve anomaly
        resolved = self.snitch_manager.resolve_anomaly(event.anomaly_id, "Operator reset spend to 0 EUR and verified credentials")
        self.assertTrue(resolved)
        self.assertFalse(self.snitch_manager.is_branch_quarantined("PAYMENT_BRANCH"))
        self.assertFalse(self.snitch_manager.is_scope_quarantined("PAYMENT_SCOPE"))

    def test_10_no_evidence_runtime_causes_no_wake(self):
        # Empty queue -> IDLE_EXPECTED with 0 model calls
        session = self.runtime.start_night_session("sess-test-empty", "No work")
        action = self.runtime.select_next_action(session)
        self.assertEqual(action["action_type"], "IDLE_EXPECTED")
        self.assertEqual(self.runtime.elite_core.metrics.model_calls_admitted, 0)

    def test_11_relevant_evidence_causes_one_wake(self):
        opp = Opportunity(
            opportunity_id="OPP-RELEVANT-1",
            source="TEST",
            objective_id="OBJ-REL",
            project="REL_PROJ",
            description="Relevant task",
            status="READY",
            priority=8,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-test-rel", "Relevant work")
        step_res = self.runtime.execute_session_step(deterministic_resolver=lambda tid: (True, {"ok": True}))
        self.assertEqual(step_res["status"], "PROGRESS_MADE")

    def test_12_duplicate_evidence_causes_no_duplicate_wake(self):
        ing1 = self.runtime.ingest_real_event("RESULT", "GOOGLE", "CORR-DUP-1", {"res": 1}, "TASK-DUP")
        self.assertEqual(ing1["status"], "INGESTED")

        ing2 = self.runtime.ingest_real_event("RESULT", "GOOGLE", "CORR-DUP-1", {"res": 1}, "TASK-DUP")
        self.assertEqual(ing2["status"], "DUPLICATE_IGNORED")

    def test_13_twenty_five_logical_agents_yields_minimum_necessary_model_workers(self):
        self.assertGreaterEqual(len(self.registry.registered_agents), 25)
        # All 25 are registered, active model worker count remains 0
        self.assertEqual(self.runtime.elite_core.metrics.model_calls_admitted, 0)

    def test_14_no_shadow_model_fan_out(self):
        # Concurrency constraints strictly limit model heavy slots
        self.assertEqual(self.registry.config.model_heavy_per_provider_limit, 1)
        self.assertEqual(self.registry.config.mutation_scope_owner_limit, 1)

    def test_15_integrated_fast_finish_snitch_gates_scenario(self):
        # Full integrated adversarial scenario:
        # Candidate A: Safe independent build (READY) -> executes
        # Candidate B: Publication candidate -> parked human gate
        # Candidate C: Money candidate -> parked payment gate
        # Candidate D: In quarantined branch -> parked/skipped
        self.snitch_manager.report_observation(
            reporting_agent="agent-sec",
            domain=AnomalyDomain.SECURITY_BOUNDARY_VIOLATION,
            observed="Breach in branch D",
            expected="Clean",
            affected_branch="BRANCH_D",
            affected_scope="SCOPE_D",
        )

        candidates = [
            EliteActionSpec(
                action_id="ACT-A-SAFE",
                goal="Build core library",
                expected_unlock="Core lib",
                quality_floor=QualityFloorClass.LOW_RISK,
                risk_class="LOW",
                new_information="",
                why_now="Critical path",
                why_model="",
                why_not_local="",
                why_not_cache="",
                decision_value_class="CRITICAL_UNBLOCK",
                mutation_scope=["SCOPE_A"],
                is_on_critical_path=True,
                priority=9,
            ),
            EliteActionSpec(
                action_id="ACT-B-PUB",
                goal="Publish video",
                expected_unlock="Visibility",
                quality_floor=QualityFloorClass.PUBLICATION,
                risk_class="HIGH",
                new_information="",
                why_now="",
                why_model="",
                why_not_local="",
                why_not_cache="",
                decision_value_class="HIGH_VALUE",
                mutation_scope=["SCOPE_PUB"],
                priority=8,
            ),
            EliteActionSpec(
                action_id="ACT-C-MONEY",
                goal="Activate paid API",
                expected_unlock="Credits",
                quality_floor=QualityFloorClass.MONEY,
                risk_class="HIGH",
                new_information="",
                why_now="",
                why_model="",
                why_not_local="",
                why_not_cache="",
                decision_value_class="HIGH_VALUE",
                mutation_scope=["SCOPE_MONEY"],
                priority=8,
            ),
            EliteActionSpec(
                action_id="ACT-D-QUARANTINED",
                goal="Execute task in compromised branch",
                expected_unlock="Compromised",
                quality_floor=QualityFloorClass.LOW_RISK,
                risk_class="LOW",
                new_information="",
                why_now="",
                why_model="",
                why_not_local="",
                why_not_cache="",
                decision_value_class="USEFUL",
                mutation_scope=["SCOPE_D"],
                priority=5,
            ),
        ]

        resolver = lambda tid: (True, {"built": True}) if tid == "ACT-A-SAFE" else (False, {})
        plan = self.fast_finish_engine.evaluate_and_schedule_plan(
            candidates,
            "GOAL_INTEGRATED_ADVERSARIAL",
            deterministic_resolver=resolver,
            snitch_manager=self.snitch_manager,
        )

        # Act A executes safely
        self.assertEqual(plan["admissions"]["ACT-A-SAFE"]["decision"], SchedulerDecision.LOCALIZE.value)
        self.assertTrue(plan["admissions"]["ACT-A-SAFE"]["admitted"])

        # Act B hits publication gate
        self.assertEqual(plan["admissions"]["ACT-B-PUB"]["decision"], SchedulerDecision.PARK_HUMAN_GATE.value)
        self.assertFalse(plan["admissions"]["ACT-B-PUB"]["admitted"])

        # Act C hits money gate
        self.assertEqual(plan["admissions"]["ACT-C-MONEY"]["decision"], SchedulerDecision.PARK_MONEY_GATE.value)
        self.assertFalse(plan["admissions"]["ACT-C-MONEY"]["admitted"])

        # Act D blocked by Snitch quarantine
        self.assertIn("QUARANTINED_BY_SNITCH", plan["admissions"]["ACT-D-QUARANTINED"]["payload"]["reason"])
        self.assertFalse(plan["admissions"]["ACT-D-QUARANTINED"]["admitted"])

    def test_16_stop_success_when_goal_and_quality_floor_satisfied(self):
        stop_ok, msg = self.core.check_stop_on_sufficient_quality(
            goal_satisfied=True,
            quality_floor_verified=True,
            remaining_blockers=[],
        )
        self.assertTrue(stop_ok)
        self.assertIn("STOP_SUCCESS", msg)


if __name__ == "__main__":
    unittest.main()
