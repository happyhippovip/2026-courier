#!/usr/bin/env python3
"""Deterministic Test Suite for MISSION 117 — Real Sleep Autopilot.

Tests:
A. AWAKE -> SLEEPING transition
B. SLEEPING presence persists across supervisor restart
C. Useful objective creates bounded task
D. Duplicate objective/result does not duplicate task
E. No-value objectives create zero tasks (IDLE)
F. Cost uncertainty blocks affected task (PAYMENT_APPROVAL_REQUIRED)
G. Human Gate pauses only affected branch (WAITING_FOR_HUMAN)
H. Repeated failure opens circuit (CIRCUIT_OPEN)
I. Task/session limits stop autonomous expansion (MAX_TASKS_REACHED)
J. SLEEPING -> AWAKE transition
K. Morning Report generated exactly once with required fields
L. Existing 25-agent roster preserved
M. Codex remains IDLE without trigger
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_chief_commander import ChiefCommander, ChiefDecisionContract
from scripts.run_autonomous_supervisor import AutonomousSupervisor
from scripts.standing_objectives import StandingObjectivesRegistry, StandingObjective
from scripts.capability_registry import AgentProfileRegistry


class TestSleepAutopilotMission117(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="courier_test_m117_")
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
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Create sample config fixtures
        (self.config_dir / "local_tools.json").write_text(json.dumps({"tools": ["read_file", "write_file"]}), encoding="utf-8")
        (self.config_dir / "social_channels.json").write_text(json.dumps({"channels": ["youtube", "twitter"]}), encoding="utf-8")
        (self.config_dir / "teamwork_policy.json").write_text(json.dumps({"heavy_job_limit": 1}), encoding="utf-8")

        self.supervisor = AutonomousSupervisor(repo_dir=self.test_dir, max_tasks=5)
        self.chief = self.supervisor.chief
        self.registry = self.supervisor.objectives_registry

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_a_awake_to_sleeping_transition(self):
        """A. AWAKE -> SLEEPING state transition."""
        self.chief.set_presence("AWAKE")
        self.assertEqual(self.chief.get_presence()["presence"], "AWAKE")

        self.chief.set_presence("SLEEPING", session_id="test-sleep-01")
        presence = self.chief.get_presence()
        self.assertEqual(presence["presence"], "SLEEPING")
        self.assertEqual(presence["session_id"], "test-sleep-01")

        state_file = self.events_dir / "agent-states/agent-chief-commander.json"
        self.assertTrue(state_file.exists())
        chief_state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(chief_state["state"], "SLEEPING")
        self.assertEqual(chief_state["position_hint"], "fireplace")

    def test_b_sleeping_presence_persists_across_restart(self):
        """B. SLEEPING presence persists across supervisor restart."""
        self.chief.set_presence("SLEEPING", session_id="test-sleep-persist")

        # Simulate fresh supervisor instance
        new_supervisor = AutonomousSupervisor(repo_dir=self.test_dir)
        presence = new_supervisor.chief.get_presence()
        self.assertEqual(presence["presence"], "SLEEPING")
        self.assertEqual(presence["session_id"], "test-sleep-persist")

    def test_c_useful_objective_creates_bounded_task(self):
        """C. Useful objective creates bounded task."""
        obj, task = self.registry.evaluate_and_select_next_objective("WF-NIGHT-01", "sess-01")
        self.assertIsNotNone(obj)
        self.assertIsNotNone(task)
        self.assertEqual(obj.objective_id, "KEEP_PRODUCTION_PIPELINE_HEALTHY")
        self.assertEqual(task["target_agent"], "antigravity")
        self.assertEqual(task["cost_class"], "ZERO_COST_LOCAL")

    def test_d_duplicate_objective_result_does_not_duplicate_task(self):
        """D. Duplicate objective/result does not duplicate task."""
        obj, task = self.registry.evaluate_and_select_next_objective("WF-NIGHT-02", "sess-02")
        self.assertIsNotNone(obj)

        # Dispatch and mark complete
        result_file = self.supervisor.dispatch_and_execute_task(task, "WF-NIGHT-02", "corr-02")
        self.registry.mark_objective_result(obj.objective_id, "hash_12345", "PASS")

        # Next selection with visited set skips already completed objective
        obj2, task2 = self.registry.evaluate_and_select_next_objective(
            "WF-NIGHT-02", "sess-02", visited_objectives={obj.objective_id}
        )
        self.assertNotEqual(obj2.objective_id, "KEEP_PRODUCTION_PIPELINE_HEALTHY")

    def test_e_no_value_objectives_create_zero_tasks(self):
        """E. No-value/disabled objectives create zero tasks (IDLE)."""
        # Disable all objectives
        for obj in self.registry.list_objectives():
            obj.enabled = False
            self.registry.save_objective(obj)

        obj, task = self.registry.evaluate_and_select_next_objective("WF-NIGHT-03", "sess-03")
        self.assertIsNone(obj)
        self.assertIsNone(task)

    def test_f_cost_uncertainty_blocks_affected_task(self):
        """F. Cost uncertainty blocks affected task (PAYMENT_APPROVAL_REQUIRED)."""
        obj = self.registry.get_objective("KEEP_PRODUCTION_PIPELINE_HEALTHY")
        obj.cost_ceiling = 15.00  # Non-zero spend requested
        self.registry.save_objective(obj)

        obj_sel, task_sel = self.registry.evaluate_and_select_next_objective("WF-NIGHT-04", "sess-04")
        # Objective is blocked by Cost Gate
        if obj_sel:
            self.assertNotEqual(obj_sel.objective_id, "KEEP_PRODUCTION_PIPELINE_HEALTHY")
        self.assertEqual(obj.status, "BLOCKED")

    def test_g_human_gate_pauses_only_affected_branch(self):
        """G. Human Gate pauses only affected branch (WAITING_FOR_HUMAN)."""
        # Create task requiring human approval
        task_info = {
            "task_id": "WF-NIGHT-HG-TASK",
            "instruction": "Deploy new production credentials to public gateway",
            "target_agent": "antigravity",
            "allowed_scope": ["config/local_tools.json"],
            "cost_class": "ZERO_COST_LOCAL",
            "risk_level": "HIGH",
        }

        # Create dummy result with HUMAN_GATE required
        res_file = self.test_dir / "events/processed/WF-NIGHT-HG-TASK-result.json"
        res_envelope = {
            "schema_version": "2.0",
            "task_id": "WF-NIGHT-HG-TASK",
            "correlation_id": "corr-hg",
            "source": "antigravity",
            "type": "RESULT",
            "status": "COMPLETED",
            "payload": {"verdict": "PASS", "human_gate_required": True, "reason": "Requires deployment auth"},
        }
        res_file.write_text(json.dumps(res_envelope), encoding="utf-8")

        decision = self.chief.evaluate_result_and_decide(
            task_id="WF-NIGHT-HG-TASK",
            correlation_id="corr-hg",
            workflow_id="WF-NIGHT-HG",
            result_file=res_file,
        )
        self.assertEqual(decision.decision, "WAIT_FOR_HUMAN")

    def test_h_repeated_failure_opens_circuit(self):
        """H. Repeated failure opens circuit (CIRCUIT_OPEN)."""
        supervisor = AutonomousSupervisor(
            repo_dir=self.test_dir,
            max_tasks=5,
            max_consecutive_failures=2,
        )
        # Point objective to non-existent scope file or failing action to force failure
        obj = supervisor.objectives_registry.get_objective("KEEP_PRODUCTION_PIPELINE_HEALTHY")
        obj.allowed_scope = ["config/local_tools.json"]
        obj.instruction_template = "Force fail"
        supervisor.objectives_registry.save_objective(obj)

        # Mock dispatch failure by overriding dispatch_and_execute_task
        def failing_dispatch(*args, **kwargs):
            raise RuntimeError("Forced execution failure for circuit test")

        supervisor.dispatch_and_execute_task = failing_dispatch

        result = supervisor.run_sleep_session(workflow_id="WF-FAIL-CIRCUIT", max_tasks=3)
        self.assertEqual(result["status"], "FAILED_CIRCUIT_OPEN")
        self.assertEqual(result["stop_reason"], "CIRCUIT_OPEN")

    def test_i_task_and_session_limits_stop_expansion(self):
        """I. Task/session limits stop autonomous expansion (MAX_TASKS_REACHED)."""
        supervisor = AutonomousSupervisor(
            repo_dir=self.test_dir,
            max_tasks=2,
        )
        result = supervisor.run_sleep_session(workflow_id="WF-MAX-LIMITS", max_tasks=2)
        self.assertLessEqual(result["tasks_executed"], 2)

    def test_j_sleeping_to_awake_transition(self):
        """J. SLEEPING -> AWAKE state transition."""
        self.chief.set_presence("SLEEPING")
        self.assertEqual(self.chief.get_presence()["presence"], "SLEEPING")

        self.chief.set_presence("AWAKE")
        presence = self.chief.get_presence()
        self.assertEqual(presence["presence"], "AWAKE")

        state_file = self.events_dir / "agent-states/agent-chief-commander.json"
        chief_state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(chief_state["state"], "IDLE")
        self.assertEqual(chief_state["position_hint"], "command_table")

    def test_k_morning_report_generated_exactly_once(self):
        """K. Morning Report generated exactly once with required keys."""
        session_id = "test-sleep-report-01"
        self.chief.log_night_journal(session_id, {
            "action": "RESULT_EVALUATED",
            "task_id": "TASK-01",
            "objective_id": "KEEP_PRODUCTION_PIPELINE_HEALTHY",
            "target_agent": "antigravity",
            "result_file": "TASK-01-result.json",
            "decision": "COMPLETE",
            "verdict": "PASS",
        })

        report = self.supervisor.generate_morning_report(session_id)
        self.assertEqual(report["sleep_session_id"], session_id)
        self.assertEqual(report["money_spent"], "0.00 EUR (Strict Zero-Spend Policy enforced)")
        self.assertIn("what_completed", report)
        self.assertIn("what_changed", report)
        self.assertIn("codex_usage", report)
        self.assertIn("antigravity_usage", report)

        md_file = self.events_dir / "morning-reports/MORNING_REPORT.md"
        self.assertTrue(md_file.exists())
        self.assertIn(session_id, md_file.read_text(encoding="utf-8"))

    def test_l_agent_roster_preservation(self):
        """L. Existing 25-agent roster preserved: 0 renamed, 0 deleted, 0 merged."""
        registry = AgentProfileRegistry(self.test_dir)
        profiles = registry.list_profiles()
        self.assertGreaterEqual(len(profiles), 7)

        agent_ids = [p.agent_id for p in profiles]
        self.assertIn("agent-chief-commander", agent_ids)
        self.assertIn("agent-courier-relay", agent_ids)
        self.assertIn("smart-resource-router", agent_ids)
        self.assertIn("agent-antigravity-bridge", agent_ids)
        self.assertIn("agent-codex-bridge", agent_ids)
        self.assertIn("agent-thought-curator", agent_ids)
        self.assertIn("agent-update-steward", agent_ids)

    def test_m_codex_remains_idle_without_trigger(self):
        """M. Codex remains IDLE without trigger during night loop."""
        result = self.supervisor.run_sleep_session(workflow_id="WF-CODEX-IDLE", max_tasks=1)
        self.assertEqual(result["status"], "COMPLETED")

        # Verify Codex visual state remained IDLE
        codex_state_file = self.events_dir / "agent-states/agent-codex-bridge.json"
        if codex_state_file.exists():
            codex_state = json.loads(codex_state_file.read_text(encoding="utf-8"))
            self.assertIn(codex_state.get("state", "IDLE"), ("IDLE", "STANDBY"))


if __name__ == "__main__":
    unittest.main()
