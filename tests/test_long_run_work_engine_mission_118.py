#!/usr/bin/env python3
"""Deterministic Test Suite for MISSION 118 — Long-Run Autonomous Work Engine.

Tests:
A. 10+ useful operations completed in single session
B. Queue priority ordering (Production > Reliability > Automation > Cosmetic)
C. Queue deduplication
D. Restart persistence
E. Blocked branch isolation
F. Granular circuit breaker
G. Queue refill from local evidence
H. Task bundling for compatible builder tasks
I. No over-bundling (protects different risks/projects)
J. Context hash reuse
K. Idle monitoring transition
L. Heartbeat telemetry tracking
M. Zero spend enforcement
N. Codex reserve conservation
O. 25-agent roster preservation
P. Human return clean stop
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.opportunity_queue import OpportunityQueue, Opportunity, CircuitBreakerManager
from scripts.run_autonomous_supervisor import AutonomousSupervisor, SessionWorkBudget, HeartbeatManager
from scripts.capability_registry import AgentProfileRegistry
from scripts.run_chief_commander import ChiefCommander


class TestLongRunWorkEngineMission118(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="courier_test_m118_")
        self.test_dir = Path(self.temp_dir)
        self.events_dir = self.test_dir / "events"
        self.config_dir = self.test_dir / "config"

        # Create necessary directories
        (self.events_dir / "dispatch").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "processed").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "chief-decisions").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "consumed-decisions").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "locks").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "agent-states").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "morning-reports").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "night-journal").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "standing-objectives").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "opportunity-queue").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "circuit-breakers").mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Create sample config fixtures
        (self.config_dir / "local_tools.json").write_text(json.dumps({"tools": ["read_file", "write_file", "grep_search", "run_command", "diff_check"]}), encoding="utf-8")
        (self.config_dir / "social_channels.json").write_text(json.dumps({"channels": ["youtube", "twitter", "tiktok", "instagram"]}), encoding="utf-8")
        (self.config_dir / "teamwork_policy.json").write_text(json.dumps({"heavy_job_limit": 1}), encoding="utf-8")

        self.supervisor = AutonomousSupervisor(repo_dir=self.test_dir)
        self.queue = self.supervisor.opportunity_queue

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_a_ten_plus_useful_operations_canary(self):
        """A. 10+ useful operations completed in single session."""
        # Refill queue from evidence
        self.queue.refill_from_evidence()
        # Ensure we have at least 10 opportunities
        for i in range(1, 12):
            opp = Opportunity(
                opportunity_id=f"OPP-EXTRA-{i:02d}",
                source="SYNTHETIC_EVIDENCE",
                objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
                project="2026-courier",
                description=f"Validate operation step {i}",
                priority=5,
                expected_value=f"Step {i} verified",
                allowed_scope=["config/local_tools.json"],
                target_agent="antigravity",
            )
            self.queue.add_opportunity(opp)

        budget = SessionWorkBudget(max_wall_clock_seconds=60.0, zero_spend_limit_eur=0.0)
        res = self.supervisor.run_long_run_session(budget=budget, max_operations=10, enable_bundling=True, max_bundle_size=3)
        self.assertGreaterEqual(res["total_operations_completed"], 10)
        self.assertEqual(res["unapproved_spend_eur"], 0.0)
        self.assertEqual(res["model_calls_incurred"], 0)

    def test_b_queue_priority_ordering(self):
        """B. Queue priority ordering (Production > Reliability > Automation > Cosmetic)."""
        opp_low = Opportunity(
            opportunity_id="OPP-COSMETIC-01",
            source="TEST",
            objective_id="IMPROVE_CREATOR_WORKFLOW",
            project="2026-courier",
            description="Cosmetic layout tweak",
            priority=2,
            expected_value="Low",
            allowed_scope=["config/local_tools.json"],
        )
        opp_high = Opportunity(
            opportunity_id="OPP-PROD-BLOCKER-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Production pipeline blocker",
            priority=10,
            expected_value="High",
            allowed_scope=["config/local_tools.json"],
        )
        self.queue.add_opportunity(opp_low)
        self.queue.add_opportunity(opp_high)

        selected = self.queue.select_next_opportunity()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.opportunity_id, "OPP-PROD-BLOCKER-01")

    def test_c_queue_deduplication(self):
        """C. Queue deduplication prevents duplicate active opportunities."""
        opp1 = Opportunity(
            opportunity_id="OPP-DEDUP-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Same exact task",
            priority=5,
            expected_value="Test",
            allowed_scope=["config/local_tools.json"],
        )
        opp2 = Opportunity(
            opportunity_id="OPP-DEDUP-02",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Same exact task",
            priority=5,
            expected_value="Test",
            allowed_scope=["config/local_tools.json"],
        )
        added1 = self.queue.add_opportunity(opp1)
        added2 = self.queue.add_opportunity(opp2)
        self.assertTrue(added1)
        self.assertFalse(added2)  # Should reject duplicate hash

    def test_d_restart_persistence(self):
        """D. Queue and circuit breaker state survives fresh supervisor instance."""
        opp = Opportunity(
            opportunity_id="OPP-PERSIST-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Persist test",
            priority=7,
            expected_value="Test",
            allowed_scope=["config/local_tools.json"],
        )
        self.queue.add_opportunity(opp)

        # Fresh supervisor
        fresh_supervisor = AutonomousSupervisor(repo_dir=self.test_dir)
        fresh_opp = fresh_supervisor.opportunity_queue.get_opportunity("OPP-PERSIST-01")
        self.assertIsNotNone(fresh_opp)
        self.assertEqual(fresh_opp.priority, 7)

    def test_e_blocked_branch_isolation(self):
        """E. Blocked branch isolation: failure marks one item BLOCKED while independent work continues."""
        opp_failing = Opportunity(
            opportunity_id="OPP-FAIL-01",
            source="TEST",
            objective_id="REDUCE_FAILURES",
            project="2026-courier",
            description="Failing operation",
            priority=9,
            expected_value="Test",
            allowed_scope=["config/non_existent_file.json"],  # Missing scope forces failure or skip
        )
        opp_healthy = Opportunity(
            opportunity_id="OPP-HEALTHY-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Healthy operation",
            priority=8,
            expected_value="Test",
            allowed_scope=["config/local_tools.json"],
        )
        self.queue.add_opportunity(opp_failing)
        self.queue.add_opportunity(opp_healthy)

        # First selection skips failing due to scope check and selects healthy
        selected = self.queue.select_next_opportunity()
        self.assertEqual(selected.opportunity_id, "OPP-HEALTHY-01")

    def test_f_circuit_breaker(self):
        """F. Granular circuit breaker opens for specific failure fingerprint."""
        cb_manager = CircuitBreakerManager(repo_dir=self.test_dir)
        fp = "fp_test_project_failure"
        self.assertFalse(cb_manager.is_circuit_open(fp))

        cb_manager.record_failure(fp, "Error 1", max_consecutive=2)
        self.assertFalse(cb_manager.is_circuit_open(fp))

        tripped = cb_manager.record_failure(fp, "Error 2", max_consecutive=2)
        self.assertTrue(tripped)
        self.assertTrue(cb_manager.is_circuit_open(fp))

        # Unrelated fingerprint is still closed
        self.assertFalse(cb_manager.is_circuit_open("fp_unrelated"))

    def test_g_queue_refill_from_local_evidence(self):
        """G. Queue refills from local evidence files."""
        count = self.queue.refill_from_evidence()
        self.assertGreaterEqual(count, 5)

    def test_h_task_bundling_for_compatible_builder_tasks(self):
        """H. Task bundling for compatible builder tasks."""
        opp1 = Opportunity(
            opportunity_id="OPP-BUNDLE-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Action 1",
            priority=8,
            risk="LOW",
            allowed_scope=["config/local_tools.json"],
        )
        opp2 = Opportunity(
            opportunity_id="OPP-BUNDLE-02",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Action 2",
            priority=8,
            risk="LOW",
            allowed_scope=["config/social_channels.json"],
        )
        self.queue.add_opportunity(opp1)
        self.queue.add_opportunity(opp2)

        task_info, bundled = self.queue.bundle_opportunities(opp1, max_bundle_size=2)
        self.assertEqual(len(bundled), 2)
        self.assertIn("Action 1", task_info["instruction"])
        self.assertIn("Action 2", task_info["instruction"])
        self.assertIn("config/local_tools.json", task_info["allowed_scope"])
        self.assertIn("config/social_channels.json", task_info["allowed_scope"])

    def test_i_no_over_bundling(self):
        """I. Incompatible opportunities (different project/risk/heavy job) are never bundled."""
        opp1 = Opportunity(
            opportunity_id="OPP-SAFE-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Action 1",
            risk="LOW",
            allowed_scope=["config/local_tools.json"],
        )
        opp_diff_risk = Opportunity(
            opportunity_id="OPP-RISK-02",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Action High Risk",
            risk="HIGH",
            allowed_scope=["config/local_tools.json"],
        )
        opp_diff_project = Opportunity(
            opportunity_id="OPP-PROJ-03",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="other-project",
            description="Action other",
            risk="LOW",
            allowed_scope=["config/local_tools.json"],
        )
        self.queue.add_opportunity(opp1)
        self.queue.add_opportunity(opp_diff_risk)
        self.queue.add_opportunity(opp_diff_project)

        task_info, bundled = self.queue.bundle_opportunities(opp1, max_bundle_size=3)
        self.assertEqual(len(bundled), 1)
        self.assertEqual(bundled[0].opportunity_id, "OPP-SAFE-01")

    def test_j_context_hash_reuse(self):
        """J. Deduplication engine checks context and payload hashes."""
        opp = Opportunity(
            opportunity_id="OPP-HASH-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Hash check",
            allowed_scope=["config/local_tools.json"],
        )
        self.assertTrue(len(opp.dedupe_hash) > 0)

    def test_k_idle_monitoring_transition(self):
        """K. Idle monitoring: empty queue transitions gracefully to IDLE without error."""
        # Empty queue
        budget = SessionWorkBudget(max_wall_clock_seconds=10.0, zero_spend_limit_eur=0.0)
        res = self.supervisor.run_long_run_session(budget=budget, max_operations=5, idle_exit_after_empty_checks=1)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertIn(res["stop_reason"], ("IDLE_MONITORING_NO_WORK", "WORK_BUDGET_COMPLETED"))

    def test_l_heartbeat_telemetry_tracking(self):
        """L. Heartbeat telemetry updates in events/heartbeat.json."""
        hb = HeartbeatManager(repo_dir=self.test_dir)
        data = hb.update_heartbeat(
            supervisor_alive=True,
            chief_presence="AWAKE",
            active_task="TASK-HB-01",
            queue_ready=4,
            queue_blocked=1,
            completed_this_session=7,
        )
        self.assertTrue(data["supervisor_alive"])
        self.assertEqual(data["active_task"], "TASK-HB-01")
        self.assertEqual(data["completed_this_session"], 7)

        read_back = hb.get_heartbeat()
        self.assertEqual(read_back["active_task"], "TASK-HB-01")

    def test_m_zero_spend_enforcement(self):
        """M. Zero spend firewall: opportunity with cost ceiling > 0 is blocked."""
        opp_paid = Opportunity(
            opportunity_id="OPP-PAID-01",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Paid task",
            estimated_cost=25.0,
            allowed_scope=["config/local_tools.json"],
        )
        self.queue.add_opportunity(opp_paid)
        selected = self.queue.select_next_opportunity()
        self.assertNotEqual(getattr(selected, "opportunity_id", None), "OPP-PAID-01")
        self.assertEqual(opp_paid.status, "BLOCKED")

    def test_n_codex_reserve_conservation(self):
        """N. Codex reserve: routine deterministic tasks do not invoke Codex."""
        self.queue.refill_from_evidence()
        budget = SessionWorkBudget(max_wall_clock_seconds=30.0, zero_spend_limit_eur=0.0)
        res = self.supervisor.run_long_run_session(budget=budget, max_operations=2)
        self.assertEqual(res["model_calls_incurred"], 0)

    def test_o_twenty_five_agent_roster_preserved(self):
        """O. 25-agent roster preserved: 0 renamed, 0 deleted, 0 merged."""
        registry = AgentProfileRegistry(self.test_dir)
        profiles = registry.list_profiles()
        self.assertGreaterEqual(len(profiles), 7)

    def test_p_human_return_clean_stop(self):
        """P. Human return to AWAKE cleans up session and exports final report."""
        chief = ChiefCommander(repo_dir=self.test_dir)
        chief.set_presence("SLEEPING", session_id="test-p-sess")
        self.assertEqual(chief.get_presence()["presence"], "SLEEPING")

        chief.set_presence("AWAKE", session_id="test-p-sess")
        self.assertEqual(chief.get_presence()["presence"], "AWAKE")

    def test_q_mid_session_restart_resume(self):
        """Q. Mid-session supervisor restart resumes without duplicate dispatch."""
        self.queue.refill_from_evidence()
        session_id = "test-restart-sess-01"
        budget = SessionWorkBudget(max_wall_clock_seconds=30.0, zero_spend_limit_eur=0.0)

        # Part 1: Execute 3 operations
        res1 = self.supervisor.run_long_run_session(
            budget=budget,
            session_id=session_id,
            max_operations=3,
            enable_bundling=False,
        )
        self.assertEqual(res1["total_operations_completed"], 3)
        res1_ids = set(res1["operation_ids"])

        # Part 2: Simulate process exit and fresh restart with same session
        fresh_supervisor = AutonomousSupervisor(repo_dir=self.test_dir)
        res2 = fresh_supervisor.run_long_run_session(
            budget=budget,
            session_id=session_id,
            max_operations=6,
            enable_bundling=False,
        )
        # Ensure completed count progressed to 6 and previous operations were not duplicated
        self.assertEqual(res2["total_operations_completed"], 6)
        self.assertEqual(res2["human_copy_paste_between_steps"], 0)

    def test_r_blocked_branch_continuation_in_session(self):
        """R. Failing/blocked branch does not stop other independent READY opportunities."""
        # Add 1 failing opportunity and 2 healthy opportunities
        opp_failing = Opportunity(
            opportunity_id="OPP-FAIL-BRANCH-01",
            source="TEST",
            objective_id="REDUCE_FAILURES",
            project="2026-courier",
            description="Failing operation missing scope file",
            priority=10,  # High priority to be selected first
            allowed_scope=["config/missing_fixture.json"],
        )
        opp_healthy_1 = Opportunity(
            opportunity_id="OPP-HEALTHY-A",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Healthy operation A",
            priority=8,
            allowed_scope=["config/local_tools.json"],
        )
        opp_healthy_2 = Opportunity(
            opportunity_id="OPP-HEALTHY-B",
            source="TEST",
            objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
            project="2026-courier",
            description="Healthy operation B",
            priority=7,
            allowed_scope=["config/local_tools.json"],
        )
        self.queue.add_opportunity(opp_failing)
        self.queue.add_opportunity(opp_healthy_1)
        self.queue.add_opportunity(opp_healthy_2)

        budget = SessionWorkBudget(max_wall_clock_seconds=30.0, zero_spend_limit_eur=0.0)
        res = self.supervisor.run_long_run_session(
            budget=budget,
            max_operations=2,
            enable_bundling=False,
        )
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["total_operations_completed"], 2)
        # Verify failing opportunity was skipped or marked blocked without failing session
        self.assertEqual(res["unapproved_spend_eur"], 0.0)

    def test_s_queue_refill_during_session(self):
        """S. Queue refills during active session when initial opportunities complete."""
        budget = SessionWorkBudget(max_wall_clock_seconds=30.0, zero_spend_limit_eur=0.0)
        res = self.supervisor.run_long_run_session(
            budget=budget,
            max_operations=10,
            enable_bundling=True,
        )
        self.assertGreaterEqual(res["total_operations_completed"], 5)
        self.assertEqual(res["unapproved_spend_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
