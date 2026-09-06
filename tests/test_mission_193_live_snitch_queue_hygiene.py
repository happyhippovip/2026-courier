#!/usr/bin/env python3
"""Mission 193: Test Suite for Live Snitch, Queue Hygiene & Continuous Flow."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.continuous_local_flow import ContinuousLocalFlowController, FlowDecision
from scripts.lightweight_live_snitch import (
    LightweightLiveSnitch,
    RecommendationClass,
    SnitchAlert,
    WorkerObservation,
    WorkerState,
)
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.queue_hygiene_manager import QueueHygieneManager


class TestMission193LiveSnitchAndQueueHygiene(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_193_test_"))
        self.queue_dir = self.test_dir / "events" / "opportunity-queue"
        self.alerts_dir = self.test_dir / "events" / "runtime-alerts"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

        self.snitch = LightweightLiveSnitch(
            repo_dir=self.test_dir,
            observation_interval_seconds=10.0,
            progress_stall_threshold_seconds=100.0,
        )
        self.queue_manager = QueueHygieneManager(repo_dir=self.test_dir)
        self.flow_controller = ContinuousLocalFlowController(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # Objective A & D: Worker State & Permission Detection Tests
    # --------------------------------------------------------------------------

    def test_01_command_safety_classification(self):
        # Safe test command
        rec1, reason1 = self.snitch.classify_command_safety("python3 -m unittest discover tests")
        self.assertEqual(rec1, RecommendationClass.SAFE_COMMAND_PATTERN)

        # Dangerous mutation
        rec2, reason2 = self.snitch.classify_command_safety("rm -rf /")
        self.assertEqual(rec2, RecommendationClass.HUMAN_APPROVAL_REQUIRED)

        # Inline script requiring rewrite
        rec3, reason3 = self.snitch.classify_command_safety("python3 -c 'import os; print(1)'")
        self.assertEqual(rec3, RecommendationClass.REWRITE_COMMAND)

        # Safe project script
        rec4, reason4 = self.snitch.classify_command_safety("python3 scripts/launch_visual_studio.py")
        self.assertEqual(rec4, RecommendationClass.POLICY_CONFIGURATION_REQUIRED)

    def test_02_worker_state_evaluations(self):
        now_ts = time.time()

        # 1. Recent activity (< 30s) -> PROGRESSING
        obs1 = self.snitch.evaluate_worker_state(
            worker_id="CLI_1",
            worker_role="SCOUT",
            pid=os.getpid(),
            last_activity_time=now_ts - 5.0,
        )
        self.assertEqual(obs1.state, WorkerState.PROGRESSING)

        # 2. Permission prompt -> WAITING_PERMISSION
        obs2 = self.snitch.evaluate_worker_state(
            worker_id="CLI_1",
            worker_role="SCOUT",
            pid=os.getpid(),
            last_activity_time=now_ts - 40.0,
            permission_prompt_detected=True,
            permission_reason="Do you want to proceed with tool call? [y/N]",
            last_command="python3 -m unittest tests/test_unit.py",
        )
        self.assertEqual(obs2.state, WorkerState.WAITING_PERMISSION)
        self.assertEqual(obs2.recommended_action, RecommendationClass.SAFE_COMMAND_PATTERN)

        # 3. Long idle on active task -> RUNNING_NO_PROGRESS
        obs3 = self.snitch.evaluate_worker_state(
            worker_id="CLI_1",
            worker_role="SCOUT",
            pid=os.getpid(),
            last_activity_time=now_ts - 150.0,
            task_id="OPP-ACTIVE-TASK",
        )
        self.assertEqual(obs3.state, WorkerState.RUNNING_NO_PROGRESS)

        # 4. Clean idle with no task -> SAFE_IDLE
        obs4 = self.snitch.evaluate_worker_state(
            worker_id="CLI_1",
            worker_role="SCOUT",
            pid=os.getpid(),
            last_activity_time=now_ts - 150.0,
            task_id=None,
        )
        self.assertEqual(obs4.state, WorkerState.SAFE_IDLE)

    # --------------------------------------------------------------------------
    # Objective B & E: Alert Generation & Deduplication Tests
    # --------------------------------------------------------------------------

    def test_03_alert_generation_and_schema(self):
        obs = WorkerObservation(
            worker_id="CLI_1",
            worker_role="OPERATIONS_ENGINEER",
            pid=12345,
            is_alive=True,
            state=WorkerState.WAITING_PERMISSION,
            task_id="OPP-TEST-1",
            last_progress_at="2026-09-01T03:00:00Z",
            last_output_at="2026-09-01T03:00:00Z",
            last_command="git status",
            permission_reason="Do you want to run git status? [y/N]",
            recommended_action=RecommendationClass.SAFE_COMMAND_PATTERN,
        )

        alert_file = self.snitch.emit_alert_if_needed(obs)
        self.assertIsNotNone(alert_file)
        self.assertTrue(alert_file.is_file())

        data = json.loads(alert_file.read_text(encoding="utf-8"))
        self.assertEqual(data["alert_version"], "3.0")
        self.assertEqual(data["worker_id"], "CLI_1")
        self.assertEqual(data["state"], "WAITING_PERMISSION")
        self.assertEqual(data["recommended_action"], "SAFE_COMMAND_PATTERN")
        self.assertIn("fingerprint", data)
        self.assertFalse(data["acknowledged"])

    def test_04_alert_deduplication(self):
        obs = WorkerObservation(
            worker_id="CLI_1",
            worker_role="OPERATIONS_ENGINEER",
            pid=12345,
            is_alive=True,
            state=WorkerState.WAITING_PERMISSION,
            task_id="OPP-TEST-1",
            last_command="git status",
            permission_reason="Do you want to run git status? [y/N]",
        )

        # First emit -> creates alert
        alert1 = self.snitch.emit_alert_if_needed(obs)
        self.assertIsNotNone(alert1)
        self.assertEqual(self.snitch.telemetry["alerts_emitted"], 1)

        # Second emit with same fingerprint -> suppresses duplicate!
        alert2 = self.snitch.emit_alert_if_needed(obs)
        self.assertIsNone(alert2)
        self.assertEqual(self.snitch.telemetry["alerts_emitted"], 1)
        self.assertEqual(self.snitch.telemetry["duplicate_alerts_suppressed"], 1)

        # Total alert files on disk must remain exactly 1
        alerts_on_disk = list(self.alerts_dir.glob("*.json"))
        self.assertEqual(len(alerts_on_disk), 1)

    # --------------------------------------------------------------------------
    # Objective F & G: Queue Hygiene & Historical Archival Tests
    # --------------------------------------------------------------------------

    def test_05_queue_pruning_and_safety_invariants(self):
        q = OpportunityQueue(repo_dir=self.test_dir)

        # Add mix of completed and actionable/protected tasks
        opp_comp1 = Opportunity(opportunity_id="OPP-COMP-1", source="TEST", objective_id="OBJ1", project="P1", description="Comp 1", status="COMPLETED", priority=9)
        opp_comp2 = Opportunity(opportunity_id="OPP-COMP-2", source="TEST", objective_id="OBJ1", project="P1", description="Comp 2", status="COMPLETED", priority=8)
        opp_ready = Opportunity(opportunity_id="OPP-READY-1", source="TEST", objective_id="OBJ1", project="P1", description="Ready 1", status="READY", priority=10)
        opp_human = Opportunity(opportunity_id="OPP-HUMAN-1", source="TEST", objective_id="OBJ1", project="P1", description="Human 1", status="WAITING_FOR_HUMAN", priority=10)
        opp_money = Opportunity(opportunity_id="OPP-MONEY-1", source="TEST", objective_id="OBJ1", project="P1", description="Money 1", status="PAYMENT_APPROVAL_REQUIRED", priority=10)

        q.add_opportunity(opp_comp1)
        q.add_opportunity(opp_comp2)
        q.add_opportunity(opp_ready)
        q.add_opportunity(opp_human)
        q.add_opportunity(opp_money)

        # Inspect pre-prune
        pre_info = self.queue_manager.inspect_queue()
        self.assertEqual(pre_info["total_count"], 5)
        self.assertEqual(pre_info["completed_count"], 2)

        # Execute Prune
        res = self.queue_manager.prune_and_archive_completed()
        self.assertEqual(res["archived_count"], 2)
        self.assertEqual(res["active_remaining_count"], 3)

        # Verify active queue only has protected actionable tasks
        q_refreshed = OpportunityQueue(repo_dir=self.test_dir)
        active_opps = q_refreshed.list_opportunities()
        self.assertEqual(len(active_opps), 3)
        active_ids = {o.opportunity_id for o in active_opps}
        self.assertIn("OPP-READY-1", active_ids)
        self.assertIn("OPP-HUMAN-1", active_ids)
        self.assertIn("OPP-MONEY-1", active_ids)
        self.assertNotIn("OPP-COMP-1", active_ids)
        self.assertNotIn("OPP-COMP-2", active_ids)

        # Verify historical ledger contains completed fingerprints
        self.assertTrue(self.queue_manager.is_task_completed_in_history("OPP-COMP-1"))
        self.assertTrue(self.queue_manager.is_task_completed_in_history("OPP-COMP-2"))
        self.assertFalse(self.queue_manager.is_task_completed_in_history("OPP-READY-1"))

    # --------------------------------------------------------------------------
    # Objective I & J: Continuous Local Flow & Next-Work Selection Tests
    # --------------------------------------------------------------------------

    def test_06_continuous_flow_evaluations(self):
        # Helper to reset queue dir
        def clear_test_queue():
            for p in self.queue_dir.glob("*.json"):
                p.unlink(missing_ok=True)

        clear_test_queue()
        q = OpportunityQueue(repo_dir=self.test_dir)

        # Case 1: Safe ready task exists -> NEXT_TASK_AVAILABLE
        q.add_opportunity(Opportunity(opportunity_id="OPP-SAFE-READY", source="TEST", objective_id="OBJ1", project="P1", description="Safe Ready", status="READY", priority=9))
        res1 = self.flow_controller.evaluate_next_work()
        self.assertEqual(res1.decision, FlowDecision.NEXT_TASK_AVAILABLE)
        self.assertEqual(res1.opportunity_id, "OPP-SAFE-READY")

        # Case 2: Only human gate exists -> WAITING_HUMAN
        clear_test_queue()
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(opportunity_id="OPP-HUMAN-GATE", source="TEST", objective_id="OBJ1", project="P1", description="Human Gate", status="WAITING_FOR_HUMAN", priority=10))
        res2 = self.flow_controller.evaluate_next_work()
        self.assertEqual(res2.decision, FlowDecision.WAITING_HUMAN)

        # Case 3: High risk task -> HIGH_RISK_REVIEW
        clear_test_queue()
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(opportunity_id="OPP-HIGH-RISK", source="TEST", objective_id="OBJ1", project="P1", description="High Risk", status="READY", risk="HIGH", priority=10))
        res3 = self.flow_controller.evaluate_next_work()
        self.assertEqual(res3.decision, FlowDecision.HIGH_RISK_REVIEW)

        # Case 4: Queue completely empty -> SAFE_IDLE
        clear_test_queue()
        res4 = self.flow_controller.evaluate_next_work()
        self.assertEqual(res4.decision, FlowDecision.SAFE_IDLE)
        self.assertEqual(res4.spend_eur, 0.0)
        self.assertEqual(res4.model_calls, 0)


if __name__ == "__main__":
    unittest.main()
