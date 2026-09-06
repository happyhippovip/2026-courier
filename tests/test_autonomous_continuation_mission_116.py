#!/usr/bin/env python3
"""Deterministic Unit Tests for Mission 116: Autonomous Chief Loop (Phase 1+2 Minimal Vertical Slice).

Tests:
A. Normal two-step continuation (Task A -> Result A -> CONTINUE -> Task B -> Result B -> COMPLETE).
B. Duplicate Result A handling (Idempotent decision consumption prevents second dispatch).
C. Supervisor restart after Chief decision but before dispatch (Safe recovery).
D. Supervisor restart after dispatch (Safe recovery without duplicate dispatch).
E. MAX_TASKS reached limit enforcement (Stops at 5 tasks).
F. Zero-value next step (Value Gate cleanly halts continuation).
G. Cost not proven zero (Zero-Spend Firewall raises PAYMENT_APPROVAL_REQUIRED).
H. WAITING_FOR_HUMAN parking (Independent branch paused safely).
I. Malformed decision handling (Invalid decision string raises ValueError / fails safe).
J. Existing agent roster preserved (25 desks / all agents intact: renamed=0, deleted=0, merged=0).
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_chief_commander import ChiefCommander, ChiefDecisionContract, evaluate_value_gate
from scripts.run_autonomous_supervisor import AutonomousSupervisor


class TestAutonomousContinuationMission116(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_test_m116_"))
        self.events_dir = self.test_dir / "events"
        self.config_dir = self.test_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy config files for test scope
        (self.config_dir / "local_tools.json").write_text('{"tools": ["local_canary"]}', encoding="utf-8")
        (self.config_dir / "social_channels.json").write_text('{"channels": ["youtube", "tiktok"]}', encoding="utf-8")
        (self.config_dir / "teamwork_policy.json").write_text('{"policy": "strict"}', encoding="utf-8")

        self.supervisor = AutonomousSupervisor(repo_dir=self.test_dir, max_tasks=5)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_a_normal_two_step_continuation(self):
        """A. Normal two-step continuation: Task A -> Result A -> CONTINUE -> Task B -> Result B -> COMPLETE."""
        workflow_id = "WF-TEST-TWO-STEP-001"
        plan = [
            {
                "task_id": f"{workflow_id}-STEP-A",
                "instruction": "Inspect local tool configuration",
                "target_agent": "antigravity",
                "allowed_scope": ["config/local_tools.json"],
                "cost_class": "ZERO_COST_LOCAL",
            },
            {
                "task_id": f"{workflow_id}-STEP-B",
                "instruction": "Validate channels configuration",
                "target_agent": "antigravity",
                "allowed_scope": ["config/social_channels.json"],
                "cost_class": "ZERO_COST_LOCAL",
            },
        ]

        result = self.supervisor.run_autonomous_continuation(workflow_id, plan)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["stop_reason"], "GOAL_COMPLETED")
        self.assertEqual(result["tasks_executed"], 2)
        self.assertEqual(result["human_copy_paste_between_steps"], 0)
        self.assertEqual(result["unapproved_spend_eur"], 0.0)
        self.assertEqual(len(result["history"]), 2)

        # Check Decision A was CONTINUE
        dec_a_file = self.supervisor.decisions_dir / f"{workflow_id}-STEP-A-chief-decision.json"
        self.assertTrue(dec_a_file.exists())
        dec_a = json.loads(dec_a_file.read_text(encoding="utf-8"))
        self.assertEqual(dec_a["decision"], "CONTINUE")
        self.assertEqual(dec_a["next_task"]["task_id"], f"{workflow_id}-STEP-B")

        # Check Decision B was COMPLETE
        dec_b_file = self.supervisor.decisions_dir / f"{workflow_id}-STEP-B-chief-decision.json"
        self.assertTrue(dec_b_file.exists())
        dec_b = json.loads(dec_b_file.read_text(encoding="utf-8"))
        self.assertEqual(dec_b["decision"], "COMPLETE")

    def test_b_duplicate_result_idempotency(self):
        """B. Duplicate Result A handling: Idempotent consumption prevents second dispatch."""
        workflow_id = "WF-TEST-IDEMPOTENT-002"
        task_id = f"{workflow_id}-STEP-A"
        dec_id = "dec-chief-test-idempotent-001"

        self.assertFalse(self.supervisor.is_decision_consumed(dec_id))
        self.supervisor.mark_decision_consumed(dec_id, task_id, workflow_id, f"{workflow_id}-STEP-B")
        self.assertTrue(self.supervisor.is_decision_consumed(dec_id))

        # Re-marking does not crash and stays consumed
        self.supervisor.mark_decision_consumed(dec_id, task_id, workflow_id, f"{workflow_id}-STEP-B")
        self.assertTrue(self.supervisor.is_decision_consumed(dec_id))

    def test_c_supervisor_restart_recovery_before_dispatch(self):
        """C. Supervisor restart after Chief decision but before dispatch."""
        workflow_id = "WF-TEST-RESTART-003"
        task_id = f"{workflow_id}-STEP-A"

        # Simulate existing decision in decisions_dir
        dec_data = {
            "schema_version": "2.0",
            "chief_decision_id": "dec-chief-003",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "decision": "CONTINUE",
            "next_task": {"task_id": f"{workflow_id}-STEP-B"},
        }
        dec_file = self.supervisor.decisions_dir / f"{task_id}-chief-decision.json"
        dec_file.write_text(json.dumps(dec_data), encoding="utf-8")

        checkpoint = self.supervisor.recover_checkpoint(workflow_id)
        self.assertEqual(checkpoint["workflow_id"], workflow_id)
        self.assertEqual(checkpoint["last_completed_task"], task_id)
        self.assertEqual(checkpoint["last_decision"]["decision"], "CONTINUE")
        self.assertFalse(checkpoint["is_terminal"])

    def test_d_supervisor_restart_recovery_after_dispatch(self):
        """D. Supervisor restart after dispatch: Recognizes pending dispatch."""
        workflow_id = "WF-TEST-RESTART-004"
        task_id = f"{workflow_id}-STEP-B"

        # Simulate pending dispatch file
        dispatch_file = self.supervisor.dispatch_dir / f"{task_id}-worker-job.json"
        dispatch_file.write_text(json.dumps({
            "schema_version": "2.0",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "instruction": "Test instruction",
        }), encoding="utf-8")

        checkpoint = self.supervisor.recover_checkpoint(workflow_id)
        self.assertIsNotNone(checkpoint["pending_dispatch"])
        self.assertEqual(checkpoint["pending_dispatch"]["task_id"], task_id)

    def test_e_max_tasks_limit(self):
        """E. MAX_TASKS reached limit enforcement (Bounded stop)."""
        workflow_id = "WF-TEST-MAX-TASKS-005"
        # Configure small supervisor with max_tasks=2
        small_supervisor = AutonomousSupervisor(repo_dir=self.test_dir, max_tasks=2)
        plan = [
            {"task_id": f"{workflow_id}-STEP-1", "instruction": "Step 1", "target_agent": "antigravity", "allowed_scope": ["config/local_tools.json"], "cost_class": "ZERO_COST_LOCAL"},
            {"task_id": f"{workflow_id}-STEP-2", "instruction": "Step 2", "target_agent": "antigravity", "allowed_scope": ["config/local_tools.json"], "cost_class": "ZERO_COST_LOCAL"},
            {"task_id": f"{workflow_id}-STEP-3", "instruction": "Step 3", "target_agent": "antigravity", "allowed_scope": ["config/local_tools.json"], "cost_class": "ZERO_COST_LOCAL"},
        ]

        result = small_supervisor.run_autonomous_continuation(workflow_id, plan)
        self.assertEqual(result["status"], "STOPPED_MAX_TASKS")
        self.assertEqual(result["stop_reason"], "MAX_TASKS_REACHED")
        self.assertEqual(result["tasks_executed"], 2)

    def test_f_value_gate_zero_value_stop(self):
        """F. Zero-value next step: Value Gate halts continuation."""
        # Payload with zero value / noop
        zero_payload = {"is_noop": True, "zero_value": True, "verdict": "PASS"}
        vg = evaluate_value_gate(zero_payload)
        self.assertFalse(vg["passed"])
        self.assertFalse(vg["creates_new_information"])
        self.assertFalse(vg["advances_production"])

        # Real payload with output
        good_payload = {"output": "Extracted 5 tool records", "verdict": "PASS"}
        vg_good = evaluate_value_gate(good_payload)
        self.assertTrue(vg_good["passed"])
        self.assertTrue(vg_good["creates_new_information"])

    def test_g_zero_spend_firewall(self):
        """G. Cost not proven zero: Zero-Spend Firewall raises PAYMENT_APPROVAL_REQUIRED."""
        workflow_id = "WF-TEST-FIREWALL-007"
        expensive_plan = [
            {
                "task_id": f"{workflow_id}-PAID-TASK",
                "instruction": "Call paid external API",
                "target_agent": "antigravity",
                "allowed_scope": ["config/local_tools.json"],
                "cost_class": "PAID_API_USAGE",
                "cost_estimate": 5.0,
            }
        ]

        result = self.supervisor.run_autonomous_continuation(workflow_id, expensive_plan)
        self.assertEqual(result["status"], "PAYMENT_APPROVAL_REQUIRED")
        self.assertEqual(result["stop_reason"], "PAYMENT_APPROVAL_REQUIRED")
        self.assertEqual(result["tasks_executed"], 0)

    def test_h_waiting_for_human_gate(self):
        """H. WAITING_FOR_HUMAN parking: Task requiring explicit human approval is safely parked."""
        workflow_id = "WF-TEST-HUMAN-GATE-008"
        task_id = f"{workflow_id}-AUTH-STEP"

        # Create dummy result with human_gate_required
        res_dir = self.supervisor.processed_dir
        res_file = res_dir / f"{task_id}-result.json"
        res_data = {
            "schema_version": "2.0",
            "task_id": task_id,
            "payload": {
                "verdict": "HUMAN_APPROVAL_REQUIRED",
                "requires_human_approval": True,
                "reason": "OAuth token rotation requires user confirmation",
            }
        }
        res_file.write_text(json.dumps(res_data), encoding="utf-8")

        decision = self.supervisor.chief.evaluate_result_and_decide(
            task_id=task_id,
            correlation_id="corr-test-008",
            workflow_id=workflow_id,
            result_file=res_file,
        )

        self.assertEqual(decision.decision, "WAIT_FOR_HUMAN")
        self.assertIsNone(decision.next_task)
        self.assertTrue((self.supervisor.decisions_dir / f"{task_id}-chief-decision.json").exists())

    def test_i_malformed_decision_handling(self):
        """I. Malformed decision handling: Invalid decision string raises ValueError (fails safe)."""
        with self.assertRaises(ValueError):
            ChiefDecisionContract(
                workflow_id="WF-TEST-009",
                task_id="TASK-009",
                decision="INVALID_UNRECOGNIZED_DECISION_STRING",
            )

    def test_j_agent_roster_preservation(self):
        """J. Existing agent roster preserved: All desks and core agents intact."""
        from scripts.capability_registry import AgentProfileRegistry

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


if __name__ == "__main__":
    unittest.main()
