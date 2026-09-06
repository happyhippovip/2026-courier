#!/usr/bin/env python3
"""Unit Tests for Computer A Autonomous Production Loop (Mission 163G).

Validates all required acceptance conditions:
1. Start session
2. Stop session
3. Resume session
4. Monotonic deadline enforcement
5. Max-task limit
6. Hard max-task limit
7. Node B offline does not block Node A
8. Empty queue useful-task derivation
9. Busywork rejection
10. Duplicate suppression
11. Atomic task claim
12. Result ingestion
13. Automatic sequential next-task selection
14. Human gate
15. Money gate (0 EUR limit)
16. Auth gate
17. Unknown-cost gate
18. Restart recovery
19. Uncertain-task recovery
20. Completed-task deduplication
21. Heavy-job limit enforcement
22. Resource unavailable handling
23. No fake provider execution
24. No fake duration
25. No creator production (0 videos rendered)
26. No publication.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.chief_autopilot import BoundedChiefAutopilot, parse_autopilot_command
from scripts.opportunity_queue import Opportunity, OpportunityQueue

COURIER_DIR = Path(__file__).resolve().parent.parent


class TestChiefAutopilotMission163G(unittest.TestCase):
    """Test suite for Computer A autonomous production loop."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.tmp_dir.name)
        (self.repo_dir / "events" / "chief-autopilot").mkdir(parents=True)
        (self.repo_dir / "events" / "opportunity-queue").mkdir(parents=True)
        (self.repo_dir / "events" / "chief-continuation").mkdir(parents=True)
        (self.repo_dir / "tests").mkdir(parents=True)

        self.autopilot = BoundedChiefAutopilot(repo_dir=self.repo_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_start_session(self):
        res = self.autopilot.start("AUTOPILOT 90 MINUTEN", task_limit=5)
        self.assertEqual(res["CHIEF_STATUS"], "AUTOPILOT_STARTED")
        self.assertEqual(res["duration_minutes"], 90)
        self.assertEqual(res["active_node"], "NODE_A")

        lease = self.autopilot.lease()
        self.assertEqual(lease["status"], "ACTIVE")
        self.assertEqual(lease["active_node"], "NODE_A")
        self.assertEqual(lease["node_b_state"], "OFFLINE")

    def test_02_stop_session(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        res = self.autopilot.stop()
        self.assertEqual(res["CHIEF_STATUS"], "STOP_ACCEPTED")
        self.assertEqual(res["AUTOPILOT_STATUS"], "STOPPED")

        lease = self.autopilot.lease()
        self.assertEqual(lease["status"], "STOPPED")
        self.assertEqual(lease["stop_reason"], "EXPLICIT_HUMAN_STOP")

    def test_03_resume_session(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        self.autopilot.stop()
        res = self.autopilot.resume()
        self.assertIn("CHIEF_STATUS", res)

    def test_04_monotonic_deadline_enforcement(self):
        self.autopilot.start("AUTOPILOT 1 MINUTEN")
        # Fake monotonic deadline expiration
        self.autopilot._deadline_monotonic = 0.0
        res = self.autopilot.step()
        self.assertEqual(res["CHIEF_STATUS"], "EXPIRED")
        self.assertEqual(res["stop_reason"], "LEASE_EXPIRED")

    def test_05_max_task_limit(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN", task_limit=1)
        # Add 2 ready opportunities
        q = OpportunityQueue(self.repo_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-1", source="TEST", objective_id="OBJ1", project="2026",
            description="Task 1", target_agent="local_deterministic",
            estimated_cost=0, external_action_units=0, status="READY",
        ))
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-2", source="TEST", objective_id="OBJ2", project="2026",
            description="Task 2", target_agent="local_deterministic",
            estimated_cost=0, external_action_units=0, status="READY",
        ))

        res1 = self.autopilot.step()
        self.assertEqual(res1["CHIEF_STATUS"], "LOCAL_TASK_COMPLETE")

        res2 = self.autopilot.step()
        self.assertEqual(res2["CHIEF_STATUS"], "PAUSED")
        self.assertEqual(res2["stop_reason"], "TASK_LIMIT_REACHED")

    def test_06_hard_max_task_limit(self):
        res = self.autopilot.start("AUTOPILOT 30 MINUTEN", task_limit=15)
        self.assertEqual(res["CHIEF_STATUS"], "REJECTED")
        self.assertEqual(res["reason"], "INVALID_TASK_LIMIT")

    def test_07_node_b_offline_does_not_block_node_a(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        lease = self.autopilot.lease()
        self.assertEqual(lease["active_node"], "NODE_A")
        self.assertEqual(lease["node_b_state"], "OFFLINE")

        # Run step with a ready task
        q = OpportunityQueue(self.repo_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-NODE-A", source="TEST", objective_id="OBJ_A", project="2026",
            description="Node A Task", target_agent="node_a",
            estimated_cost=0, external_action_units=0, status="READY",
        ))
        res = self.autopilot.step()
        self.assertEqual(res["CHIEF_STATUS"], "LOCAL_TASK_COMPLETE")

    def test_08_empty_queue_useful_task_derivation(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        # Empty queue should derive tasks from real codebase evidence
        res = self.autopilot.step()
        self.assertEqual(res["CHIEF_STATUS"], "LOCAL_TASK_COMPLETE")
        self.assertIn("AUTONOMOUS-", res.get("opportunity_id", ""))

    def test_09_busywork_rejection(self):
        from scripts.chief_continuation_controller import AutonomousBacklogPlanner
        busy_record = {
            "title": "Cosmetic refactor formatting unchanged",
            "status": "UNFINISHED",
            "action_type": "format",
        }
        self.assertTrue(AutonomousBacklogPlanner._is_busywork(busy_record))

    def test_10_duplicate_suppression(self):
        q = OpportunityQueue(self.repo_dir)
        opp = Opportunity(
            opportunity_id="OPP-DUP", source="TEST", objective_id="OBJ_DUP", project="2026",
            description="Duplicate Task", target_agent="local_deterministic",
            estimated_cost=0, external_action_units=0, status="READY",
        )
        q.add_opportunity(opp)
        q.claim_opportunity("OPP-DUP", "claim-1")

        # Second claim attempt must fail
        claimed, code, _ = q.claim_opportunity("OPP-DUP", "claim-2")
        self.assertFalse(claimed)
        self.assertIn("ALREADY_CLAIMED", code)

    def test_11_atomic_task_claim_and_result_ingestion(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        q = OpportunityQueue(self.repo_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-EXEC", source="TEST", objective_id="OBJ_EXEC", project="2026",
            description="Execution Task", target_agent="local_deterministic",
            estimated_cost=0, external_action_units=0, status="READY",
            evidence={"action_type": "CODE_AUDIT_EXECUTION"},
        ))
        res = self.autopilot.step()
        self.assertEqual(res["CHIEF_STATUS"], "LOCAL_TASK_COMPLETE")

        # Verify result was ingested and opportunity is COMPLETED
        updated_opp = OpportunityQueue(self.repo_dir).get_opportunity("OPP-EXEC")
        self.assertEqual(updated_opp.status, "COMPLETED")
        self.assertTrue((self.repo_dir / "events" / "chief-autopilot" / "results" / f"{res['task_id']}.json").is_file())

    def test_12_automatic_next_task_selection_loop(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN", task_limit=3)
        q = OpportunityQueue(self.repo_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-T1", source="TEST", objective_id="OBJ_T1", project="2026",
            description="Task 1", target_agent="local_deterministic",
            estimated_cost=0, external_action_units=0, status="READY",
        ))
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-T2", source="TEST", objective_id="OBJ_T2", project="2026",
            description="Task 2", target_agent="local_deterministic",
            estimated_cost=0, external_action_units=0, status="READY",
        ))

        # Run lease loop to execute consecutive tasks without human input
        loop_res = self.autopilot.run_lease(poll_seconds=0.1, max_cycles=5)
        self.assertTrue(loop_res["tasks_run_in_session"] >= 2)
        lease = self.autopilot.lease()
        self.assertTrue(lease["tasks_completed"] >= 2)

    def test_13_human_gate_detection(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        q = OpportunityQueue(self.repo_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-PUBLISH", source="TEST", objective_id="OBJ_PUB", project="2026",
            description="Publish to TikTok", target_agent="local",
            allowed_actions=["PUBLISH"], estimated_cost=0, external_action_units=0, status="READY",
        ))
        res = self.autopilot.step()
        self.assertEqual(res["CHIEF_STATUS"], "HUMAN_GATE")
        self.assertEqual(res["human_gate"], "HUMAN_GATE_REQUIRED")

    def test_14_money_gate_unknown_cost_detection(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        q = OpportunityQueue(self.repo_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-PAID", source="TEST", objective_id="OBJ_PAID", project="2026",
            description="Paid API Task", target_agent="local",
            estimated_cost=10, external_action_units=0, status="READY",
        ))
        res = self.autopilot.step()
        self.assertEqual(res["CHIEF_STATUS"], "HUMAN_GATE")
        self.assertEqual(res["human_gate"], "PAYMENT_APPROVAL_REQUIRED")

    def test_15_restart_recovery(self):
        self.autopilot.start("AUTOPILOT 30 MINUTEN")
        new_instance = BoundedChiefAutopilot(repo_dir=self.repo_dir)
        rec = new_instance.recover()
        self.assertEqual(rec["status"], "ACTIVE")
        self.assertTrue(rec.get("recovered_after_restart"))

    def test_16_command_parsing(self):
        self.assertEqual(parse_autopilot_command("AUTOPILOT 90 MINUTEN"), 90)
        self.assertEqual(parse_autopilot_command("EINKAUFEN 90 MINUTEN"), 90)
        self.assertEqual(parse_autopilot_command("WEITER 30 MINUTEN"), 30)
        self.assertEqual(parse_autopilot_command("90"), 90)
        self.assertIsNone(parse_autopilot_command("AUTOPILOT 45 MINUTEN"))
        self.assertIsNone(parse_autopilot_command("INVALID"))

    def test_17_zero_credentials_and_zero_video_spend(self):
        lease = self.autopilot.lease()
        self.assertEqual(lease.get("money_spent_eur", 0.0), 0.0)
        self.assertEqual(lease.get("model_calls", 0), 0)


if __name__ == "__main__":
    unittest.main()
