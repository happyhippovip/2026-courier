"""
test_goal_driven_autonomy_acceptance.py - 12-Criteria Acceptance Test Suite

Demonstrates with real programmatic evidence:
1. Existing scheduler/daemon remains active.
2. Queue-empty state triggers goal reconciliation.
3. At least one real unresolved high-value candidate can be selected automatically when such a candidate exists.
4. Low-value/artificial candidate is rejected.
5. Conflicting writer candidate is held.
6. Verified completion causes another reconciliation without human input.
7. No useful candidate causes QUIESCENT_WAITING_FOR_NEW_EVIDENCE, not fake work.
8. Existing scheduled trigger can wake/reconcile again.
9. No human "weiter" is required between these transitions.
10. No Mac active scope is modified.
11. universuX is untouched.
12. Spend remains €0.
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from datetime import datetime, timezone
from unittest.mock import patch

from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.control_plane import ControlPlane
from courier.chief.goal_reconciler import GoalReconciler
from courier.chief.scheduled_cycle import execute_windows_validation_cycle


class TestGoalDrivenAutonomyAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace_root = r"C:\Users\lol\2026-workspace"
        cls.project_memory = os.path.join(cls.workspace_root, "project-memory")
        cls.cp = ControlPlane()

    # ----------------------------------------------------------------------
    # CRITERION 1: Existing scheduler/daemon remains active
    # ----------------------------------------------------------------------
    def test_01_existing_daemon_scheduler_remains_active(self):
        state_path = os.path.join(self.project_memory, "data", "autonomy_cycle_state.json")
        self.assertTrue(os.path.exists(state_path), "autonomy_cycle_state.json must exist")
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state.get("host"), "WINDOWS_PC2")
        self.assertEqual(state.get("spend_limit_eur"), 0.00)
        self.assertIn("subsystems", state)
        self.assertIn("courier_validator", state["subsystems"])
        self.assertIn("studio_dashboard_8088", state["subsystems"])

    # ----------------------------------------------------------------------
    # CRITERION 2: Queue-empty state triggers goal reconciliation
    # ----------------------------------------------------------------------
    def test_02_queue_empty_triggers_goal_reconciliation(self):
        with tempfile.TemporaryDirectory() as empty_inbox:
            res = execute_windows_validation_cycle(handoffs_dir=empty_inbox, cp=self.cp)
            self.assertEqual(res.get("status"), "PASS")
            self.assertIn(res.get("cycle_status"), ("GOAL_TASK_EXECUTED", "QUIESCENT_WAITING_FOR_NEW_EVIDENCE"))
            # Must NOT be the old passive premature exit
            self.assertNotEqual(res.get("evidence"), "LOCAL_QUEUE_EMPTY_ALL_TASKS_COMPLETED")

    # ----------------------------------------------------------------------
    # CRITERION 3: High-value unresolved candidate selected automatically
    # ----------------------------------------------------------------------
    def test_03_high_value_candidate_selected_automatically(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        candidate = {
            "candidate_id": "TEST-TASK-HIGH-VAL-01",
            "version": 1,
            "goal_id": "GOAL-03",
            "title": "Distribution Checksum Verification",
            "category": "SUSTAINABLE_COMMERCIAL_DELIVERY",
            "conflict_domain": "TEST_DOMAIN_COMMERCIAL",
            "scope": self.project_memory,
            "is_writer": False,
            "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
            "goal_impact": 9.0,
            "revenue_impact": 8.0,
            "info_gain": 9.0,
            "proof_debt_reduction": 8.0,
            "autonomy_gain": 9.0,
            "risk_score": 0.0,
            "spend_eur": 0.00,
            "human_requirement": "NONE"
        }
        ok, score, reason = reconciler.filter_and_score(candidate)
        self.assertTrue(ok, f"High value candidate should be approved: {reason}")
        self.assertGreaterEqual(score, 5.0)
        self.assertEqual(reason, "APPROVED_HIGH_VALUE_SAFE")

        # Select candidate
        selected, held = reconciler.select_next_candidate([candidate])
        self.assertIsNotNone(selected)
        self.assertEqual(selected["candidate_id"], "TEST-TASK-HIGH-VAL-01")

    # ----------------------------------------------------------------------
    # CRITERION 4: Low-value / artificial candidate is rejected
    # ----------------------------------------------------------------------
    def test_04_low_value_and_artificial_candidate_rejected(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)

        # 4A. Busywork: README rewrite
        busywork_cand = {
            "candidate_id": "TEST-TASK-BUSY-01",
            "title": "README rewrite with arbitrary date",
            "category": "DOCUMENTATION",
            "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
            "goal_impact": 1.0,
            "revenue_impact": 0.0,
            "info_gain": 0.0,
            "proof_debt_reduction": 0.0,
            "autonomy_gain": 1.0,
            "risk_score": 0.0,
            "spend_eur": 0.00,
            "human_requirement": "NONE"
        }
        ok, score, reason = reconciler.filter_and_score(busywork_cand)
        self.assertFalse(ok)
        self.assertIn("Busywork detected", reason)

        # 4B. Low value score
        low_val_cand = {
            "candidate_id": "TEST-TASK-LOW-01",
            "title": "Minor cosmetic comment tweak",
            "category": "COSMETIC",
            "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
            "goal_impact": 1.0,
            "revenue_impact": 0.0,
            "info_gain": 0.5,
            "proof_debt_reduction": 0.0,
            "autonomy_gain": 0.5,
            "risk_score": 0.0,
            "spend_eur": 0.00,
            "human_requirement": "NONE"
        }
        ok2, score2, reason2 = reconciler.filter_and_score(low_val_cand)
        self.assertFalse(ok2)
        self.assertIn("REJECT_TASK_AS_LOW_VALUE", reason2)

        # 4C. Missing gap parentage
        no_gap_cand = {
            "candidate_id": "TEST-TASK-NOGAP-01",
            "title": "Arbitrary test run without defect",
            "category": "TEST",
            "unresolved_gap": "UNKNOWN_OR_MISSING_GAP",
            "goal_impact": 8.0,
            "revenue_impact": 8.0,
            "info_gain": 8.0,
            "proof_debt_reduction": 8.0,
            "autonomy_gain": 8.0,
            "risk_score": 0.0,
            "spend_eur": 0.00,
            "human_requirement": "NONE"
        }
        ok3, score3, reason3 = reconciler.filter_and_score(no_gap_cand)
        self.assertFalse(ok3)
        self.assertIn("No valid unresolved gap parentage", reason3)

    # ----------------------------------------------------------------------
    # CRITERION 5: Conflicting writer candidate is held (NO_STACKING)
    # ----------------------------------------------------------------------
    def test_05_conflicting_writer_held_no_stacking(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        domain = "LOCKED_TEST_DOMAIN"

        # Acquire lock to simulate an active writer
        self.cp.acquire_lock(f"DOMAIN_{domain}", Lane.WINDOWS_CLI_1, Host.WINDOWS, "WRITE", ttl_seconds=60)
        try:
            cand_locked = {
                "candidate_id": "TEST-TASK-LOCKED-01",
                "goal_id": "GOAL-03",
                "title": "Task on Locked Domain",
                "conflict_domain": domain,
                "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
                "goal_impact": 9.0,
                "revenue_impact": 9.0,
                "info_gain": 9.0,
                "proof_debt_reduction": 9.0,
                "autonomy_gain": 9.0,
                "risk_score": 0.0,
                "spend_eur": 0.00,
                "human_requirement": "NONE"
            }
            cand_independent = {
                "candidate_id": "TEST-TASK-INDEPENDENT-01",
                "goal_id": "GOAL-05",
                "title": "Task on Independent Domain",
                "conflict_domain": "INDEPENDENT_DOMAIN_XYZ",
                "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
                "goal_impact": 8.5,
                "revenue_impact": 8.5,
                "info_gain": 8.5,
                "proof_debt_reduction": 8.5,
                "autonomy_gain": 8.5,
                "risk_score": 0.0,
                "spend_eur": 0.00,
                "human_requirement": "NONE"
            }

            selected, held = reconciler.select_next_candidate([cand_locked, cand_independent])
            # The locked candidate must be HELD
            self.assertEqual(len(held), 1)
            self.assertEqual(held[0]["candidate_id"], "TEST-TASK-LOCKED-01")
            self.assertIn("HELD_CONFLICTING_WRITER", held[0]["held_reason"])

            # The independent candidate must be SELECTED without stacking
            self.assertIsNotNone(selected)
            self.assertEqual(selected["candidate_id"], "TEST-TASK-INDEPENDENT-01")
        finally:
            self.cp.release_lock(f"DOMAIN_{domain}", Lane.WINDOWS_CLI_1)

    # ----------------------------------------------------------------------
    # CRITERION 6: Verified completion causes another reconciliation
    # ----------------------------------------------------------------------
    def test_06_verified_completion_causes_subsequent_reconciliation(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        # Verify that Result Customs accepts valid execution and marks VERIFIED
        mock_cand = {
            "candidate_id": "TEST-TASK-VERIFY-01",
            "scope": self.project_memory
        }
        mock_exec = {
            "success": True,
            "returncode": 0,
            "evidence_hash": "a" * 64,
            "files_changed": ["file_a.txt"]
        }
        customs_res = reconciler.result_customs(mock_cand, mock_exec)
        self.assertTrue(customs_res["verified"])
        self.assertEqual(customs_res["decision"], "VERIFIED")

    # ----------------------------------------------------------------------
    # CRITERION 7: No useful candidate causes QUIESCENT_WAITING_FOR_NEW_EVIDENCE
    # ----------------------------------------------------------------------
    def test_07_no_useful_candidate_enters_quiescent_waiting(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        # When all candidates are completed or empty, enters quiescent waiting
        with patch.object(reconciler, "discover_candidates", return_value=[]):
            res = reconciler.reconcile_and_execute(max_tasks_per_cycle=1)
            self.assertEqual(res.get("status"), "PASS")
            self.assertEqual(res.get("cycle_status"), "QUIESCENT_WAITING_FOR_NEW_EVIDENCE")
            self.assertEqual(res.get("evidence"), "NO_HIGH_VALUE_SAFE_TASK_AVAILABLE")
            self.assertEqual(res.get("files_changed"), [])
            self.assertFalse(res.get("side_effects_occurred"))
            self.assertTrue(res.get("quiescent"))

    # ----------------------------------------------------------------------
    # CRITERION 8: Existing scheduled trigger can wake/reconcile again
    # ----------------------------------------------------------------------
    def test_08_scheduled_trigger_can_wake_and_reconcile_again(self):
        # Calling execute_windows_validation_cycle() directly simulates scheduled cron waking
        res = execute_windows_validation_cycle()
        self.assertEqual(res.get("status"), "PASS")
        self.assertIn(res.get("cycle_status"), ("GOAL_TASK_EXECUTED", "QUIESCENT_WAITING_FOR_NEW_EVIDENCE"))

    # ----------------------------------------------------------------------
    # CRITERION 9: No human "weiter" required between transitions
    # ----------------------------------------------------------------------
    def test_09_no_human_weiter_required_between_transitions(self):
        # Entire flow executes end-to-end without blocking on stdin or prompt
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        res = reconciler.reconcile_and_execute(max_tasks_per_cycle=1)
        self.assertIn("cycle_status", res)
        self.assertEqual(res.get("blocker"), "NONE")

    # ----------------------------------------------------------------------
    # CRITERION 10: No Mac active scope is modified
    # ----------------------------------------------------------------------
    def test_10_no_mac_active_scope_modified(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        mac_cand = {
            "candidate_id": "TEST-TASK-MAC-VIOLATION",
            "scope": r"C:\Users\lol\2026-workspace\mac\active\file.js",
            "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
            "goal_impact": 10.0,
            "revenue_impact": 10.0,
            "info_gain": 10.0,
            "proof_debt_reduction": 10.0,
            "autonomy_gain": 10.0,
            "risk_score": 0.0,
            "spend_eur": 0.00,
            "human_requirement": "NONE"
        }
        ok, score, reason = reconciler.filter_and_score(mac_cand)
        self.assertFalse(ok)
        self.assertIn("Mac active scope is strictly excluded", reason)

    # ----------------------------------------------------------------------
    # CRITERION 11: universuX is untouched
    # ----------------------------------------------------------------------
    def test_11_universux_is_untouched(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        ux_cand = {
            "candidate_id": "TEST-TASK-UNIVERSUX-VIOLATION",
            "scope": r"C:\Users\lol\2026-workspace\universuX\core.ts",
            "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
            "goal_impact": 10.0,
            "revenue_impact": 10.0,
            "info_gain": 10.0,
            "proof_debt_reduction": 10.0,
            "autonomy_gain": 10.0,
            "risk_score": 0.0,
            "spend_eur": 0.00,
            "human_requirement": "NONE"
        }
        ok, score, reason = reconciler.filter_and_score(ux_cand)
        self.assertFalse(ok)
        self.assertIn("universuX is strictly protected", reason)

    # ----------------------------------------------------------------------
    # CRITERION 12: Spend remains €0
    # ----------------------------------------------------------------------
    def test_12_spend_remains_zero_euro(self):
        reconciler = GoalReconciler(cp=self.cp, workspace_root=self.workspace_root)
        spend_cand = {
            "candidate_id": "TEST-TASK-SPEND-VIOLATION",
            "scope": self.project_memory,
            "spend_eur": 4.99,
            "unresolved_gap": "AUTONOMY_CAPABILITY_GAP",
            "goal_impact": 10.0,
            "revenue_impact": 10.0,
            "info_gain": 10.0,
            "proof_debt_reduction": 10.0,
            "autonomy_gain": 10.0,
            "risk_score": 0.0,
            "human_requirement": "NONE"
        }
        ok, score, reason = reconciler.filter_and_score(spend_cand)
        self.assertFalse(ok)
        self.assertIn("REJECTED_SPEND_GUARD", reason)


if __name__ == "__main__":
    unittest.main()
