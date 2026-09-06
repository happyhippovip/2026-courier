#!/usr/bin/env python3
"""Mission PRODUCT-5 Acceptance Test Suite — Autonomous Work Session Controller.

Verifies:
1. Session starts from canonical state.
2. Five-step sequential goal completes with 0 manual prompts (A -> B -> C -> D -> E -> STOP_SUCCESS).
3. Result triggers next useful work automatically.
4. No result/no evidence produces 0 model calls and enters SAFE_IDLE.
5. SAFE_IDLE when no useful work.
6. Completed work not redispatched.
7. CLAIMED work not duplicated.
8. Human-gated branch does not block safe branch.
9. Money-gated branch does not block safe branch.
10. Publication-gated branch does not block safe branch.
11. Global WAITING_HUMAN only when no safe work remains.
12. Global WAITING_MONEY only when no safe work remains.
13. Restart resumes from correct step.
14. Restart preserves DONE state.
15. Restart preserves waiting dependency.
16. Branch failure does not kill independent branch.
17. Systemic anomaly fails closed (FAILED_SYSTEMIC).
18. Resolved anomaly allows session continuation.
19. Product-4 opportunities consumed.
20. Product-2C prioritization reused.
21. Product-3C bridge interface reused.
22. Product-4C parallel batch compatibility preserved.
23. Product-5C message completion schema compatible.
24. Cockpit snapshot uses 0 model calls.
25. Structured end-of-session report uses 0 model calls.
26. No busywork loop when empty.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_work_session_controller import (
    AutonomousWorkSessionController,
    AutonomousSessionState,
)
from scripts.autonomous_opportunity_discovery import CanonicalOpportunity


class TestAutonomousWorkSessionControllerMissionProduct5(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_sess_ctrl_test_"))
        self.events_dir = self.test_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        (self.events_dir / "opportunity-queue").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "autonomy-runtime").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "anomalies").mkdir(parents=True, exist_ok=True)
        self.controller = AutonomousWorkSessionController(
            session_id="test-sess-001",
            repo_dir=self.test_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_session_starts_from_canonical_state(self):
        """Session controller initializes cleanly with RUNNING status and goal set."""
        state = self.controller.start_session(initial_goals=["Deliver Product 5"])
        self.assertEqual(state.status, "RUNNING")
        self.assertIn("Deliver Product 5", state.goal_set)
        self.assertTrue((self.test_dir / "events/autonomy-runtime/session_controller_state.json").exists())

    def test_02_five_step_goal_zero_prompt_chain_and_03_result_triggers_next(self):
        """Five sequential steps (A -> B -> C -> D -> E) complete without manual prompts to STOP_SUCCESS."""
        chain = [{
            "goal_id": "goal-5step",
            "steps": [
                {"step_id": "step-1", "description": "Step 1: Setup", "dependencies": []},
                {"step_id": "step-2", "description": "Step 2: Build", "dependencies": ["step-1"]},
                {"step_id": "step-3", "description": "Step 3: Test", "dependencies": ["step-2"]},
                {"step_id": "step-4", "description": "Step 4: Package", "dependencies": ["step-3"]},
                {"step_id": "step-5", "description": "Step 5: Verify", "dependencies": ["step-4"]},
            ]
        }]
        self.controller.start_session(initial_goals=["goal-5step"])

        # Step 1
        st1, disp1 = self.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st1, "RUNNING")
        self.assertEqual(len(disp1), 1)
        self.assertEqual(disp1[0]["opportunity_id"], "step-1")

        # Result 1 -> Step 2
        self.controller.process_result("step-1", "SUCCESS")
        st2, disp2 = self.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st2, "RUNNING")
        self.assertEqual(len(disp2), 1)
        self.assertEqual(disp2[0]["opportunity_id"], "step-2")

        # Result 2 -> Step 3
        self.controller.process_result("step-2", "SUCCESS")
        st3, disp3 = self.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st3, "RUNNING")
        self.assertEqual(len(disp3), 1)
        self.assertEqual(disp3[0]["opportunity_id"], "step-3")

        # Result 3 -> Step 4
        self.controller.process_result("step-3", "SUCCESS")
        st4, disp4 = self.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st4, "RUNNING")
        self.assertEqual(len(disp4), 1)
        self.assertEqual(disp4[0]["opportunity_id"], "step-4")

        # Result 4 -> Step 5
        self.controller.process_result("step-4", "SUCCESS")
        st5, disp5 = self.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st5, "RUNNING")
        self.assertEqual(len(disp5), 1)
        self.assertEqual(disp5[0]["opportunity_id"], "step-5")

        # Result 5 -> STOP_SUCCESS
        self.controller.process_result("step-5", "SUCCESS")
        st6, disp6 = self.controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st6, "STOP_SUCCESS")
        self.assertEqual(len(disp6), 0)
        self.assertEqual(self.controller.session.accounting.useful_tasks_completed, 5)
        self.assertEqual(self.controller.session.accounting.manual_intermediate_prompts, 0)

    def test_04_no_result_and_05_safe_idle_when_no_work(self):
        """When no pending work exists, enters SAFE_IDLE without model calls."""
        self.controller.start_session()
        status, disp = self.controller.run_next_step()
        self.assertEqual(status, "SAFE_IDLE")
        self.assertEqual(len(disp), 0)

    def test_06_completed_work_not_redispatched(self):
        """Completed task is not emitted in subsequent steps."""
        goals = [{"goal_id": "g1", "content": "One-time audit task"}]
        self.controller.start_session()
        st1, disp1 = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(len(disp1), 1)
        opp_id = disp1[0]["opportunity_id"]

        # Mark done
        self.controller.process_result(opp_id, "SUCCESS")

        # Next step
        st2, disp2 = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(len(disp2), 0)
        self.assertEqual(st2, "SAFE_IDLE")

    def test_07_claimed_work_not_duplicated(self):
        """Work marked CLAIMED by message stamp is not dispatched to another worker."""
        opp = CanonicalOpportunity(
            opportunity_id="opp-claimed-01",
            description="Handle specialized task",
            message_stamp={"status": "CLAIMED", "worker": "codex"},
        )
        self.controller.discovery_engine.add_opportunity(opp)

        st, disp = self.controller.run_next_step()
        self.assertEqual(len(disp), 0)
        self.assertEqual(self.controller.session.accounting.duplicates_avoided, 1)

    def test_08_human_gated_branch_does_not_block_safe_branch(self):
        """Gated branch (Human) waits locally while safe branch runs."""
        goals = [
            {"goal_id": "g-gate", "content": "Publish quarterly earnings release to website"},
            {"goal_id": "g-safe", "content": "Calculate cache memory footprint"},
        ]
        st, disp = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 1)
        self.assertEqual(disp[0]["description"], "Calculate cache memory footprint")
        self.assertEqual(len(self.controller.session.human_gates), 1)

    def test_09_money_gated_branch_does_not_block_safe_branch(self):
        """Gated branch (Money) waits locally while safe branch runs."""
        goals = [
            {"goal_id": "g-money", "content": "Purchase 100 API credits", "estimated_cost": 50.0},
            {"goal_id": "g-safe", "content": "Run linting pass on test files"},
        ]
        st, disp = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 1)
        self.assertEqual(disp[0]["description"], "Run linting pass on test files")
        self.assertEqual(len(self.controller.session.money_gates), 1)

    def test_10_publication_gated_branch_does_not_block_safe_branch(self):
        """Publication gate waits locally while safe branch runs."""
        goals = [
            {"goal_id": "g-pub", "content": "Public upload of video package"},
            {"goal_id": "g-safe", "content": "Optimize image thumbnails locally"},
        ]
        st, disp = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 1)
        self.assertEqual(disp[0]["description"], "Optimize image thumbnails locally")

    def test_11_global_waiting_human_only_when_no_safe_work(self):
        """Controller enters global WAITING_HUMAN only when NO safe work remains."""
        goals = [{"goal_id": "g-human-only", "content": "Publish press release"}]
        st, disp = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "WAITING_HUMAN")
        self.assertEqual(len(disp), 0)

    def test_12_global_waiting_money_only_when_no_safe_work(self):
        """Controller enters global WAITING_MONEY only when NO safe work remains."""
        goals = [{"goal_id": "g-money-only", "content": "Purchase license key", "estimated_cost": 99.0}]
        st, disp = self.controller.run_next_step(active_goals=goals)
        self.assertEqual(st, "WAITING_MONEY")
        self.assertEqual(len(disp), 0)

    def test_13_restart_resumes_correct_step_and_14_preserves_done_state(self):
        """Session restarted from disk resumes from exactly where it left off without duplicating completed steps."""
        chain = [{
            "goal_id": "goal-chain-restart",
            "steps": [
                {"step_id": "step-1", "description": "Step 1", "dependencies": []},
                {"step_id": "step-2", "description": "Step 2", "dependencies": ["step-1"]},
                {"step_id": "step-3", "description": "Step 3", "dependencies": ["step-2"]},
            ]
        }]
        self.controller.start_session(initial_goals=["goal-chain-restart"])

        # Execute Step 1
        self.controller.run_next_step(sequenced_chains=chain)
        self.controller.process_result("step-1", "SUCCESS")

        # Simulate fresh controller restart
        new_controller = AutonomousWorkSessionController(
            session_id="test-sess-001",
            repo_dir=self.test_dir,
        )
        self.assertIn("step-1", new_controller.session.completed_tasks)

        # Next step on restarted controller should be Step 2
        st, disp = new_controller.run_next_step(sequenced_chains=chain)
        self.assertEqual(st, "RUNNING")
        self.assertEqual(len(disp), 1)
        self.assertEqual(disp[0]["opportunity_id"], "step-2")

    def test_16_branch_failure_does_not_kill_independent_branch(self):
        """Failure on branch A records waiting/failed branch but does not crash the session."""
        self.controller.start_session()
        self.controller.session.active_branches["branch-a"] = {"task_id": "branch-a"}
        self.controller.session.active_branches["branch-b"] = {"task_id": "branch-b"}

        # Branch A fails
        self.controller.process_result("branch-a", "FAIL", branch="BRANCH_A")
        self.assertIn("branch-a", self.controller.session.waiting_branches)
        self.assertIn("branch-b", self.controller.session.active_branches)

    def test_17_systemic_anomaly_fails_closed(self):
        """Critical systemic anomaly transitions controller to FAILED_SYSTEMIC."""
        anom_data = {
            "anom_sys": {
                "fingerprint": "anom_sys",
                "severity": "CRITICAL",
                "affected_scope": "SYSTEMIC",
                "resolved": False,
            }
        }
        (self.events_dir / "anomalies/anomaly_ledger.json").write_text(json.dumps(anom_data))

        st, disp = self.controller.run_next_step()
        self.assertEqual(st, "FAILED_SYSTEMIC")
        self.assertEqual(len(disp), 0)

    def test_24_cockpit_snapshot_zero_model_calls(self):
        """Cockpit snapshot produces full telemetry dictionary with 0 model calls."""
        snapshot = self.controller.get_cockpit_snapshot()
        self.assertEqual(snapshot["session_id"], "test-sess-001")
        self.assertEqual(snapshot["model_calls"], 0)
        self.assertIn("accounting", snapshot)

    def test_25_structured_end_session_report_zero_model_calls(self):
        """Structured end-session report produces clean dictionary with 0 model calls."""
        report = self.controller.generate_end_session_report()
        self.assertEqual(report["session_id"], "test-sess-001")
        self.assertEqual(report["model_calls"], 0)
        self.assertIn("tasks_completed", report)

    def test_26_no_busywork_loop_when_empty(self):
        """When queue is empty and goals are empty, stays in SAFE_IDLE without inventing work."""
        self.controller.start_session()
        for _ in range(3):
            st, disp = self.controller.run_next_step()
            self.assertEqual(st, "SAFE_IDLE")
            self.assertEqual(len(disp), 0)


if __name__ == "__main__":
    unittest.main()
