"""
test_finish_first_continuation.py - Test suite for WINDOWS COURIER — P0 FINISH-FIRST / CLEAN weiter CONTINUATION

Certifies:
1. TEST — ONE weiter:
   - Reconciles current task
   - Finishes or verifies current task
   - Checkpoint written with rich structured metadata
   - No duplicate batch or test replay
   - Next real gap selected
   - Successor started only after prior closure
2. TEST — DUPLICATE weiter:
   - First call: accepted/consumed
   - Second call: CONTINUATION_ALREADY_CONSUMED
   - Batches started = 1, duplicate tasks = 0
3. TEST — VERIFIED TASK:
   - Verified task is never rerun; advances to next justified real gap
4. TEST — NO REAL GAP:
   - Two independent portfolio passes detect genuine exhaustion
   - Does NOT manufacture fake work or rerun acceptance court
   - Returns clean LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED
5. TEST — STRUCTURED CHECKPOINT SEMANTICS:
   - Stores TASK_ID, TASK_VERSION, STATE_GENERATION, RESULT_FINGERPRINT, VERIFIED_AT
   - Monotonically protects against state generation and task regression
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.batch_guard import BatchGuardManager
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone


class TestFinishFirstContinuation(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_ff_cont_")
        self.tmp_db = os.path.join(self.tmp_dir, "test_cp.db")
        self.cp = ControlPlane(db_path=self.tmp_db)
        self.batch_guard = BatchGuardManager(db_path=self.tmp_db)
        self.crash_engine = CrashProofMemoryEngine(db_path=self.tmp_db)

        # Create isolated project-memory and safe backlog
        self.pm_dir = os.path.join(self.tmp_dir, "project-memory", "data")
        os.makedirs(self.pm_dir, exist_ok=True)
        self.backlog_file = os.path.join(self.pm_dir, "safe_backlog.json")

        self.sample_tasks = [
            {
                "task_id": "TASK-WIN-REAL-01",
                "goal_id": "GOAL-03",
                "title": "Dual-Transport Sync Circuit Fault Injection and Recovery",
                "status": "PENDING",
                "priority": 9.5,
                "conflict_scope": "DUAL_TRANSPORT",
                "expected_real_delta": "RELIABILITY_GAIN",
                "script_path": "courier/tests/test_dual_transport_sync.py",
                "source_evidence": "courier/chief/control_plane.py"
            },
            {
                "task_id": "TASK-WIN-REAL-02",
                "goal_id": "GOAL-03",
                "title": "Peer Bridge Dispatch Distributed Queue Buffer Limiter",
                "status": "PENDING",
                "priority": 9.0,
                "conflict_scope": "BRIDGE_DISPATCH",
                "expected_real_delta": "PERFORMANCE_GAIN",
                "script_path": "courier/tests/test_peer_bridge_dispatch.py",
                "source_evidence": "courier/chief/control_plane.py"
            }
        ]

        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump({
                "version": "1.0.0",
                "tasks": self.sample_tasks
            }, f, indent=2)

        self.engine = FinishFirstContinuationEngine(
            workspace_root=self.tmp_dir,
            cp=self.cp,
            batch_guard=self.batch_guard,
            crash_engine=self.crash_engine
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_one_weiter_controlled_acceptance(self):
        """TEST 1 — ONE weiter: Reconcile -> Finish -> Checkpoint -> Close -> Select Next Gap."""
        # 1. State A: Simulate an interrupted unverified task left with valid on-disk effect
        interrupted_task = "TASK-INTERRUPTED-01"
        with open(os.path.join(self.tmp_dir, f"{interrupted_task}.done"), "w") as f:
            f.write("Valid effect delivered before crash")

        self.cp.upsert_task(
            task_id=interrupted_task,
            assignment_id=f"ASSIGN-{interrupted_task}",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="CONTINUE"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )


        # 2. Process bare 'weiter'
        res = self.engine.process_continuation(signal="weiter", continuation_generation=1, current_goal="GOAL-03")

        # 3. Verify prior task was finished/closed first
        t_row = self.cp.get_task(interrupted_task)
        self.assertIsNotNone(t_row)
        self.assertEqual(t_row["status"], "COMPLETED")

        # 4. Verify structured checkpoint written
        ckpt = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertIsNotNone(ckpt)
        self.assertIn("task_id", ckpt)
        self.assertIn("state_generation", ckpt)
        self.assertIn("result_fingerprint", ckpt)
        self.assertEqual(ckpt["status"], "VERIFIED")

        # 5. Verify next real gap selected and executed
        self.assertEqual(res["status"], "CURRENT_WORK_VERIFIED_NEXT_REAL_TASK_RUNNING")
        self.assertEqual(res["executed_task"], "TASK-WIN-REAL-01")
        self.assertTrue(res["real_safe_work_remaining"])

    def test_02_duplicate_weiter_suppression(self):
        """TEST 2 — DUPLICATE weiter: First call consumed, second returns CONTINUATION_ALREADY_CONSUMED."""
        # First call
        res1 = self.engine.process_continuation(signal="weiter", continuation_generation=1, current_goal="GOAL-03")
        self.assertEqual(res1["status"], "CURRENT_WORK_VERIFIED_NEXT_REAL_TASK_RUNNING")
        self.assertEqual(res1["executed_task"], "TASK-WIN-REAL-01")

        metrics_after_first = self.batch_guard.get_metrics()
        batches_started_1 = metrics_after_first["physical_batches_started"]
        self.assertEqual(batches_started_1, 1)

        # Immediate second continuation with same state/generation
        res2 = self.engine.process_continuation(signal="weiter", continuation_generation=1, current_goal="GOAL-03")
        self.assertEqual(res2["status"], "CONTINUATION_ALREADY_CONSUMED")
        self.assertTrue(res2["duplicate_suppressed"])

        metrics_after_second = self.batch_guard.get_metrics()
        batches_started_2 = metrics_after_second["physical_batches_started"]
        # Exactly 1 physical batch started, 0 duplicate batches, 0 duplicate tasks
        self.assertEqual(batches_started_2, 1)
        self.assertEqual(metrics_after_second["duplicate_tasks_executed"], 0)

    def test_03_verified_task_never_rerun(self):
        """TEST 3 — VERIFIED TASK: Previously verified task is never replayed; selects next justified gap."""
        # First continuation executes TASK-WIN-REAL-01
        res1 = self.engine.process_continuation(signal="weiter", continuation_generation=1, current_goal="GOAL-03")
        self.assertEqual(res1["executed_task"], "TASK-WIN-REAL-01")

        # Second continuation with new generation must advance to TASK-WIN-REAL-02, NEVER replaying REAL-01
        res2 = self.engine.process_continuation(signal="weiter", continuation_generation=2, current_goal="GOAL-03")
        self.assertEqual(res2["status"], "CURRENT_WORK_VERIFIED_NEXT_REAL_TASK_RUNNING")
        self.assertEqual(res2["executed_task"], "TASK-WIN-REAL-02")
        self.assertNotEqual(res2["executed_task"], "TASK-WIN-REAL-01")

    def test_04_no_real_gap_clean_exhaustion(self):
        """TEST 4 — NO REAL GAP: When portfolio is genuinely exhausted, returns clean LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED."""
        # Execute both available tasks
        self.engine.process_continuation(signal="weiter", continuation_generation=1, current_goal="GOAL-03")
        self.engine.process_continuation(signal="weiter", continuation_generation=2, current_goal="GOAL-03")

        # Now all tasks in backlog are COMPLETED
        res_exhausted = self.engine.process_continuation(signal="weiter", continuation_generation=3, current_goal="GOAL-03")
        self.assertEqual(res_exhausted["status"], "LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED")
        self.assertFalse(res_exhausted["real_safe_work_remaining"])
        self.assertIn("Two independent portfolio passes confirmed", res_exhausted["evidence"])

    def test_05_structured_checkpoint_semantics_and_monotonicity(self):
        """TEST 5 — STRUCTURED CHECKPOINT: Rich metadata and monotonic protection against regression."""
        # 1. Set structured checkpoint at state_generation 10
        ckpt_10 = {
            "task_id": "TASK-WIN-REAL-01",
            "task_version": 1,
            "state_generation": 10,
            "result_fingerprint": "hash10",
            "status": "VERIFIED"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_10)

        record = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(record["task_id"], "TASK-WIN-REAL-01")
        self.assertEqual(record["state_generation"], 10)
        self.assertEqual(record["result_fingerprint"], "hash10")

        # Plain string get_checkpoint returns task_id
        self.assertEqual(self.cp.get_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT"), "TASK-WIN-REAL-01")

        # 2. Attempt to regress state_generation to 5 -> Monotonicity guard rejects regression
        ckpt_regress = {
            "task_id": "TASK-WIN-LOWER",
            "task_version": 1,
            "state_generation": 5,
            "result_fingerprint": "hash5",
            "status": "VERIFIED"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_regress)

        record_after = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(record_after["state_generation"], 10, "State generation regression must be rejected")
        self.assertEqual(record_after["task_id"], "TASK-WIN-REAL-01")


if __name__ == "__main__":
    unittest.main()
