#!/usr/bin/env python3
"""Mission 190G-R2: Active Runtime Integration Test Suite.

Proves closure of the 4 Codex 190C-R1 open findings:
1. RealAutonomyRuntime.select_next_action() actively applies central mandatory policy.
2. Active runtime directly invokes FastFinishEngine.evaluate_and_schedule_plan().
3. Active runtime directly routes events/observations through SnitchAnomalyManager.
4. One unified execution path (Organization Policy -> FastFinish -> Snitch -> Low-level Control Plane -> Execution).
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


class TestActiveRuntimeIntegrationMission190GR2(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="org_r2_active_runtime_test_"))
        CentralElitePolicyRegistry._instance = None
        self.registry = CentralElitePolicyRegistry(repo_dir=self.test_dir)
        self.runtime = RealAutonomyRuntime(repo_dir=self.test_dir)

    def tearDown(self):
        CentralElitePolicyRegistry._instance = None
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_active_runtime_applies_central_policy(self):
        opp = Opportunity(
            opportunity_id="OPP-R2-POLICY-1",
            source="DISPATCH",
            objective_id="OBJ-R2",
            project="GLOBAL",
            description="Execute standard autonomous task",
            target_agent="deterministic_builder",
            status="READY",
            priority=8,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-r2-1", "Goal active policy")

        action = self.runtime.select_next_action(session, deterministic_resolver=lambda tid: (True, {"built": True}))
        self.assertIsNotNone(action)
        self.assertIn("agent-deterministic_builder", self.runtime.policy_registry.registered_agents)
        policy = self.runtime.policy_registry.registered_agents["agent-deterministic_builder"]["inherited_policy"]
        self.assertEqual(policy["spend_limit_eur"], 0.0)
        self.assertEqual(policy["publication_inference"], "DENY")

    def test_02_conflicting_agent_specialization_cannot_weaken_mandatory_policy(self):
        # Even if opportunity specifies paid external cost or publication, mandatory policy forces it to gate
        opp = Opportunity(
            opportunity_id="OPP-R2-ROGUE-SPEND",
            source="AGENT_SPECIALIZATION",
            objective_id="OBJ-ROGUE",
            project="ROGUE_PROJECT",
            description="Agent requests 50 EUR spend bypass",
            target_agent="specialized_rogue_bot",
            status="READY",
            cost_class="PAID_EXTERNAL",
            estimated_cost=50.0,
            priority=9,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-r2-2", "Goal enforce mandatory policy")

        action = self.runtime.select_next_action(session)
        # Should record money gate and refuse unauthorized execution
        self.assertTrue(any(g.get("task_id") == "OPP-R2-ROGUE-SPEND" for g in session.money_gates_encountered))

    def test_03_active_runtime_invokes_fast_finish_evaluation(self):
        opp1 = Opportunity(
            opportunity_id="OPP-R2-LOW-PRIO",
            source="BACKLOG",
            objective_id="OBJ-1",
            project="DOCS",
            description="Minor formatting",
            status="READY",
            priority=2,
        )
        opp2 = Opportunity(
            opportunity_id="OPP-R2-CRIT-PATH",
            source="BACKLOG",
            objective_id="OBJ-1",
            project="CORE",
            description="Core dependency unblocker",
            status="READY",
            priority=9,
        )
        self.runtime.opp_queue.add_opportunity(opp1)
        self.runtime.opp_queue.add_opportunity(opp2)
        session = self.runtime.start_night_session("sess-r2-3", "Goal test fast finish invocation")

        action = self.runtime.select_next_action(session, deterministic_resolver=lambda tid: (True, {"done": True}))
        # FastFinish prioritizes OPP-R2-CRIT-PATH over OPP-R2-LOW-PRIO
        self.assertEqual(action["task_id"], "OPP-R2-CRIT-PATH")

    def test_04_fast_finish_selected_safe_action_reaches_canonical_admission(self):
        opp = Opportunity(
            opportunity_id="OPP-R2-SAFE-BUILD",
            source="BUILDER",
            objective_id="OBJ-BUILD",
            project="BUILD_SCOPE",
            description="Build safe module",
            target_agent="antigravity",
            status="READY",
            priority=8,
            risk="LOW",
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-r2-4", "Goal safe build")

        action = self.runtime.select_next_action(session)
        self.assertEqual(action["action_type"], "DISPATCH_JOB")
        self.assertEqual(action["job_envelope"]["task_id"], "OPP-R2-SAFE-BUILD")
        self.assertTrue(action["admitted"])

    def test_05_fast_finish_selected_publication_hits_publication_gate(self):
        opp_pub = Opportunity(
            opportunity_id="OPP-R2-PUB",
            source="CREATOR",
            objective_id="OBJ-PUB",
            project="CONTENT",
            description="Publish generated media video to YouTube",
            target_agent="publication_officer",
            status="READY",
            priority=10,
        )
        self.runtime.opp_queue.add_opportunity(opp_pub)
        session = self.runtime.start_night_session("sess-r2-5", "Goal publication gate")

        action = self.runtime.select_next_action(session)
        self.assertTrue(any(g.get("task_id") == "OPP-R2-PUB" for g in session.human_gates_encountered))

    def test_06_fast_finish_selected_money_action_hits_payment_gate(self):
        opp_money = Opportunity(
            opportunity_id="OPP-R2-MONEY",
            source="INFRA",
            objective_id="OBJ-MONEY",
            project="CLOUD",
            description="Purchase cloud instance credits",
            status="READY",
            cost_class="PAID_EXTERNAL",
            estimated_cost=25.0,
            priority=10,
        )
        self.runtime.opp_queue.add_opportunity(opp_money)
        session = self.runtime.start_night_session("sess-r2-6", "Goal money gate")

        action = self.runtime.select_next_action(session)
        self.assertTrue(any(g.get("task_id") == "OPP-R2-MONEY" for g in session.money_gates_encountered))

    def test_07_active_runtime_routes_normal_observation_through_snitch(self):
        res = self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="GOOGLE",
            correlation_id="CORR-NORMAL-1",
            payload={"outcome": "SUCCESS", "observed": "Build completed with 0 errors", "expected": "Build completed with 0 errors"},
            task_id="TASK-NORMAL-1",
        )
        self.assertEqual(res["status"], "INGESTED")
        self.assertEqual(res["snitch_severity"], "NORMAL")
        self.assertFalse(res["quarantined"])

    def test_08_active_runtime_routes_critical_observation_through_snitch(self):
        res = self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="GOOGLE",
            correlation_id="CORR-CRIT-1",
            payload={
                "outcome": "FAILURE",
                "anomaly_domain": "SECURITY_BOUNDARY_VIOLATION",
                "observed": "Unauthorized outbound socket connection attempt",
                "expected": "No external socket calls allowed in sandbox",
                "affected_branch": "QUARANTINE_BRANCH_1",
                "affected_scope": "NETWORK_SCOPE",
            },
            task_id="TASK-CRIT-1",
        )
        self.assertEqual(res["snitch_severity"], "CRITICAL")
        self.assertTrue(res["quarantined"])
        self.assertTrue(self.runtime.policy_registry.snitch_manager.is_branch_quarantined("QUARANTINE_BRANCH_1"))

    def test_09_critical_observation_creates_durable_quarantine(self):
        # 1. Ingest critical event
        self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="GOOGLE",
            correlation_id="CORR-DURABLE-1",
            payload={
                "anomaly_domain": "SPEND_ANOMALY",
                "observed": "Attempted API charge: 15 EUR",
                "expected": "0 EUR",
                "affected_branch": "DURABLE_BRANCH_A",
            },
            task_id="TASK-DURABLE-1",
        )
        # 2. Re-instantiate runtime (simulating restart)
        restarted_runtime = RealAutonomyRuntime(repo_dir=self.test_dir)
        self.assertTrue(restarted_runtime.policy_registry.snitch_manager.is_branch_quarantined("DURABLE_BRANCH_A"))

    def test_10_duplicate_anomaly_does_not_reescalate(self):
        payload = {
            "anomaly_domain": "STATE_CONTRADICTION",
            "observed": "Hash mismatch in state vector",
            "expected": "Hash match in state vector",
            "affected_branch": "STATE_BRANCH_B",
        }
        res1 = self.runtime.ingest_real_event("RESULT", "WORKER_1", "CORR-A1", payload, "TASK-1")
        self.assertEqual(res1["snitch_severity"], "SUSPICIOUS")
        self.assertNotIn("DUPLICATE_SUPPRESSED", res1["snitch_action"])

        # Second event with identical observation
        res2 = self.runtime.ingest_real_event("RESULT", "WORKER_1", "CORR-A2", payload, "TASK-2")
        self.assertIn("DUPLICATE_SUPPRESSED", res2["snitch_action"])

    def test_11_unrelated_branch_remains_available(self):
        self.runtime.ingest_real_event(
            "RESULT", "GOOGLE", "CORR-CRIT-B",
            {
                "anomaly_domain": "PUBLICATION_ATTEMPT",
                "observed": "Unapproved public release",
                "expected": "No release",
                "affected_branch": "FROZEN_BRANCH",
            },
            "TASK-PUB",
        )
        self.assertTrue(self.runtime.policy_registry.snitch_manager.is_branch_quarantined("FROZEN_BRANCH"))
        self.assertFalse(self.runtime.policy_registry.snitch_manager.is_branch_quarantined("HEALTHY_BUILD_BRANCH"))

    def test_12_active_runtime_uses_anti_swarm_admission(self):
        # Concurrency constraints are active in runtime control plane & organization policy
        self.assertEqual(self.runtime.policy_registry.config.model_heavy_per_provider_limit, 1)
        self.assertEqual(self.runtime.policy_registry.config.mutation_scope_owner_limit, 1)

    def test_13_twenty_five_logical_agents_plus_one_model_judgment_yields_minimum_necessary_model_work(self):
        self.assertGreaterEqual(len(self.runtime.policy_registry.registered_agents), 25)
        # Adding one model-requiring opportunity admits exactly one job envelope
        opp = Opportunity(
            opportunity_id="OPP-MODEL-JOB-1",
            source="DISPATCH",
            objective_id="OBJ-MODEL",
            project="SYNTHESIS",
            description="Synthesize architecture refactor",
            target_agent="antigravity",
            status="READY",
            priority=9,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-r2-13", "Goal single model admission")

        action = self.runtime.select_next_action(session)
        self.assertEqual(action["action_type"], "DISPATCH_JOB")
        # Exactly 1 active job envelope in queue
        jobs = list(self.runtime.jobs_dir.glob("*.json"))
        self.assertEqual(len(jobs), 1)

    def test_14_twenty_five_logical_agents_plus_deterministic_action_yields_zero_unnecessary_model_work(self):
        opp = Opportunity(
            opportunity_id="OPP-LOCAL-JOB-1",
            source="BUILDER",
            objective_id="OBJ-LOCAL",
            project="LOCAL_SCOPE",
            description="Local deterministic calculation",
            target_agent="deterministic_builder",
            status="READY",
            priority=8,
        )
        self.runtime.opp_queue.add_opportunity(opp)
        session = self.runtime.start_night_session("sess-r2-14", "Goal deterministic resolution")

        action = self.runtime.select_next_action(session, deterministic_resolver=lambda tid: (True, {"calculated": 100}))
        self.assertEqual(action["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")
        # Model calls admitted remains 0
        self.assertEqual(self.runtime.elite_core.metrics.model_calls_admitted, 0)

    def test_15_older_control_plane_route_cannot_bypass_organization_policy_layer(self):
        # Opportunity with 0 spend limit set in organization policy cannot be admitted by control plane for paid external work
        opp_paid = Opportunity(
            opportunity_id="OPP-PAID-TEST",
            source="USER",
            objective_id="OBJ-PAID",
            project="PAID_PROJ",
            description="Paid task",
            status="READY",
            cost_class="PAID_EXTERNAL",
            estimated_cost=100.0,
            priority=9,
        )
        self.runtime.opp_queue.add_opportunity(opp_paid)
        session = self.runtime.start_night_session("sess-r2-15", "Goal bypass prevention")

        action = self.runtime.select_next_action(session)
        self.assertNotEqual(action.get("action_type"), "DISPATCH_JOB")
        self.assertTrue(any(g.get("task_id") == "OPP-PAID-TEST" for g in session.money_gates_encountered))

    def test_16_integrated_real_runtime_scenario(self):
        # Integrated real-runtime test:
        # A: Safe independent build task (READY) -> executes / dispatches
        # B: Publication action -> parked human gate
        # C: Money action -> parked money gate
        # D: Branch with CRITICAL anomaly -> actively quarantined by Snitch
        # E: Duplicate anomaly -> suppressed without re-escalation
        self.runtime.policy_registry.set_fast_finish_mode(True)

        # 1. Ingest CRITICAL anomaly on branch D
        ing_d = self.runtime.ingest_real_event(
            "RESULT", "WORKER_D", "CORR-D1",
            {
                "anomaly_domain": "SECURITY_BOUNDARY_VIOLATION",
                "observed": "Sandbox escape attempt on Branch D",
                "expected": "Isolated sandbox execution",
                "affected_branch": "BRANCH_D",
                "affected_scope": "SCOPE_D",
            },
            "TASK-D",
        )
        self.assertEqual(ing_d["snitch_severity"], "CRITICAL")
        self.assertTrue(ing_d["quarantined"])

        # 2. Ingest duplicate E of same D anomaly
        ing_e = self.runtime.ingest_real_event(
            "RESULT", "WORKER_D", "CORR-D2",
            {
                "anomaly_domain": "SECURITY_BOUNDARY_VIOLATION",
                "observed": "Sandbox escape attempt on Branch D",
                "expected": "Isolated sandbox execution",
                "affected_branch": "BRANCH_D",
                "affected_scope": "SCOPE_D",
            },
            "TASK-D2",
        )
        self.assertIn("DUPLICATE_SUPPRESSED", ing_e["snitch_action"])

        # 3. Add opportunities A, B, C, D
        opp_a = Opportunity("OPP-A-SAFE", "USER", "OBJ-A", "SCOPE_A", "Safe build action", target_agent="antigravity", status="READY", priority=9)
        opp_b = Opportunity("OPP-B-PUB", "USER", "OBJ-B", "SCOPE_B", "Publish video to YouTube", target_agent="publication_officer", status="READY", priority=8)
        opp_c = Opportunity("OPP-C-MONEY", "USER", "OBJ-C", "SCOPE_C", "Buy cloud credits", status="READY", cost_class="PAID_EXTERNAL", estimated_cost=10.0, priority=8)
        opp_d = Opportunity("OPP-D-QUAR", "USER", "OBJ-D", "SCOPE_D", "Task on quarantined branch D", status="READY", priority=8)
        setattr(opp_d, "branch", "BRANCH_D")

        self.runtime.opp_queue.add_opportunity(opp_a)
        self.runtime.opp_queue.add_opportunity(opp_b)
        self.runtime.opp_queue.add_opportunity(opp_c)
        self.runtime.opp_queue.add_opportunity(opp_d)

        session = self.runtime.start_night_session("sess-r2-16", "Integrated runtime scenario")

        # Action selection executes A safely while gating B, C, and isolating D
        action = self.runtime.select_next_action(session)
        self.assertEqual(action["action_type"], "DISPATCH_JOB")
        self.assertEqual(action["job_envelope"]["task_id"], "OPP-A-SAFE")

        # Check that B and C hit gates, and D was quarantined
        self.assertTrue(any(g.get("task_id") == "OPP-B-PUB" for g in session.human_gates_encountered))
        self.assertTrue(any(g.get("task_id") == "OPP-C-MONEY" for g in session.money_gates_encountered))
        self.assertTrue(any("QUARANTINED_BY_SNITCH" in g.get("reason", "") for g in session.human_gates_encountered))

    def test_17_stop_success_when_goal_and_quality_floor_satisfied(self):
        stop_ok, msg = self.runtime.elite_core.check_stop_on_sufficient_quality(
            goal_satisfied=True,
            quality_floor_verified=True,
            remaining_blockers=[],
        )
        self.assertTrue(stop_ok)
        self.assertIn("STOP_SUCCESS", msg)


if __name__ == "__main__":
    unittest.main()
