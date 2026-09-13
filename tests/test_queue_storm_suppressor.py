"""
test_queue_storm_suppressor.py - Test Suite for TASK-WIN-67:
Autonomous Queue Storm Suppressor, Monotonic Generation Fence & In-Flight Continuation Gate

Certifies the QUEUED INPUT SAFETY OVERRIDE invariants:
1. 250 queued bare continuation messages ("weiter", "continue", "go") collapse into exactly 1 logical continuation intent (duplicate_tasks_created == 0).
2. While a task is RUNNING, further duplicate continuations return COALESCED_IN_FLIGHT (NOOP) without restarting or duplicating the active task.
3. Once a task verifies and generation advances (N -> N+1), stale continuations from older generations (< N+1) are dropped as STALE_CONTINUATION_DROPPED without replaying verified work (verified_tasks_replayed == 0).
4. Genuine new human instructions (e.g. "Implement SQLite retry backoff") are preserved intact (is_new_goal == True) and not collapsed as bare noise.
5. End-to-end GoalReconciler checkpoint_and_persist integration automatically advances QueueCoalescer generation and updates CrashProofMemoryEngine.
6. Full observability report verifies all counters: DUPLICATE_TASKS_PREVENTED >= 250, VERIFIED_TASKS_REPLAYED == 0, SPEND_EUR == 0.00.
"""

import os
import sys
import json
import time
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.queue_coalescer import QueueCoalescer
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine, MAC_RESERVED_SCOPES
from courier.chief.control_plane import ControlPlane
from courier.chief.goal_reconciler import GoalReconciler

class TestQueueStormSuppressor(unittest.TestCase):
    def setUp(self):
        self.coalescer = QueueCoalescer()
        self.crash_engine = CrashProofMemoryEngine()
        self.cp = ControlPlane()

    def test_01_burst_of_250_weiter_collapses_into_one_logical_intent(self):
        """Invariant: 250 identical queued weiter messages represent at most ONE logical intent."""
        burst = ["weiter", "  weiter  ", "WEITER", "continue", "go", "weiter."] * 42  # 252 messages
        res = self.coalescer.process_queue_burst(burst, active_task_status="IDLE")

        self.assertEqual(res["total_messages_processed"], len(burst))
        self.assertEqual(res["logical_continuation_intents_created"], 1, "Exactly 1 logical intent must be materialized")
        self.assertGreaterEqual(res["continuations_coalesced"], len(burst) - 1, "All 251 remaining messages must be coalesced")
        self.assertEqual(res["duplicate_tasks_created"], 0, "Zero duplicate tasks created")
        self.assertEqual(res["verified_tasks_replayed"], 0, "Zero verified tasks replayed")

    def test_02_in_flight_running_task_suppresses_weiter_as_harmless_noop(self):
        """Invariant: If current task is RUNNING, further duplicate weiter = NOOP."""
        # Active task running
        active_task_id = "TASK-WIN-TEST-RUNNING"
        dup_results = []
        for _ in range(50):
            res = self.coalescer.process_raw_input("weiter", active_task_status="RUNNING", active_task_id=active_task_id)
            dup_results.append(res)

        for r in dup_results:
            self.assertEqual(r["decision"], "COALESCED_IN_FLIGHT")
            self.assertEqual(r["duplicate_tasks_created"], 0)
            self.assertEqual(r["action"], "MONITOR_IN_FLIGHT")

    def test_03_stale_generation_continuations_dropped_without_replaying_work(self):
        """Invariant: Never rerun VERIFIED work because older queued weiter arrives."""
        # Get current generation
        metrics_before = self.coalescer.get_metrics()
        gen = metrics_before["current_state_generation"]

        # Advance generation (simulating task completion)
        new_gen = self.coalescer.advance_state_generation("TASK-WIN-TEST-ADVANCE")
        self.assertEqual(new_gen, gen + 1)

        # Ingest 20 stale continuations referencing old generation
        for _ in range(20):
            is_stale = self.coalescer.handle_stale_continuation_check(incoming_generation=gen)
            self.assertTrue(is_stale, "Older generation continuation must be detected as stale")

        metrics_after = self.coalescer.get_metrics()
        self.assertEqual(metrics_after["verified_tasks_replayed"], 0, "Verified tasks replayed must remain strictly 0")
        self.assertGreaterEqual(metrics_after["stale_continuations_dropped"], 20)

    def test_04_genuine_new_human_goal_is_preserved(self):
        """Invariant: Preserve genuine NEW human goals; only collapse continuation noise."""
        instructions = [
            "Implement high-throughput batching for SQLite control plane",
            "Fix payment card layout on landing page",
            "Refactor mutex heartbeat TTL from 30s to 45s"
        ]
        for instr in instructions:
            res = self.coalescer.process_raw_input(instr, active_task_status="IDLE")
            self.assertEqual(res["decision"], "PRESERVE_NEW_GOAL")
            self.assertTrue(res["is_new_goal"])
            self.assertEqual(res["extracted_goal"], instr)
            self.assertEqual(res["duplicate_tasks_created"], 0)

    def test_05_goal_reconciler_checkpoint_advances_coalescer_and_crash_engine(self):
        """Invariant: Verification automatically checkpoints and advances without human input."""
        reconciler = GoalReconciler(cp=self.cp, workspace_root=WORKSPACE_ROOT)
        gen_before = self.coalescer.get_metrics()["current_state_generation"]

        # Simulate customs verification and checkpoint_and_persist
        mock_cand = {
            "candidate_id": "TASK-WIN-TEST-AUTOADVANCE",
            "title": "Automated State Generation Sync Test",
            "category": "CRASH_PROOF_AUTONOMY_ARCHITECTURE"
        }
        mock_customs = {"verified": True, "reason": "All checks passed"}
        mock_exec = {"stdout": "SUCCESS_AUTOADVANCE_VERIFIED", "returncode": 0, "success": True}

        reconciler.checkpoint_and_persist(mock_cand, mock_customs, mock_exec)

        gen_after = self.coalescer.get_metrics()["current_state_generation"]
        self.assertEqual(gen_after, gen_before + 1, "State generation must advance monotonically by 1")

        # Verify durable recovery state was updated
        durable_state = self.crash_engine.load_durable_state()
        self.assertEqual(durable_state["last_verified_task"], "TASK-WIN-TEST-AUTOADVANCE")
        self.assertIn("TASK-WIN-TEST-AUTOADVANCE", durable_state["do_not_repeat"])

    def test_06_full_observability_and_zero_spend_invariants(self):
        """Invariant: Report all required observability counters; spend remains 0.00 EUR."""
        report = self.coalescer.get_observability_report(current_task="TASK-WIN-67", current_goal="GOAL-05")
        required_keys = [
            "RAW_CONTINUATION_EVENTS_RECEIVED",
            "CONTINUATIONS_COALESCED",
            "STALE_CONTINUATIONS_DROPPED",
            "LOGICAL_CONTINUATION_INTENTS",
            "DUPLICATE_TASKS_PREVENTED",
            "VERIFIED_TASKS_REPLAYED",
            "CURRENT_STATE_GENERATION",
            "CURRENT_TASK",
            "CURRENT_GOAL"
        ]
        for k in required_keys:
            self.assertIn(k, report)

        self.assertEqual(report["VERIFIED_TASKS_REPLAYED"], 0)
        self.assertGreaterEqual(report["DUPLICATE_TASKS_PREVENTED"], 250)
        self.assertEqual(GoalReconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(GoalReconciler.MAC_SCOPE_EXCLUDED)

if __name__ == "__main__":
    unittest.main()
