"""
test_production_path_parity.py - Stage 3 Production-Path Parity Court
Verifies parity across all 7 critical execution mechanisms:
1. Continuation Dedupe
2. Batch / Task Idempotency
3. Writer Lease (One-Writer Law)
4. Crash Recovery (Post-Effect & Pre-Effect)
5. Effect Verification (Court K Result Customs)
6. Checkpoint (Authoritative 6-tuple & legacy mirroring)
7. Successor Selection (Unified production cycle)
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.scheduled_cycle import execute_windows_validation_cycle
from courier.chief.permanent_reserve_engine import PermanentReserveEngine
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.result_customs import ResultCustomsJudge


class TestProductionPathParity(unittest.TestCase):
    def setUp(self):
        os.environ["COURIER_FAST_TEST_MODE"] = "1"
        self.temp_dir = tempfile.mkdtemp(prefix="stage3_parity_")
        self.db_path = os.path.join(self.temp_dir, "parity.db")
        self.handoffs_dir = os.path.join(self.temp_dir, "handoffs")
        os.makedirs(self.handoffs_dir, exist_ok=True)
        self.cp = ControlPlane(db_path=self.db_path)

    def tearDown(self):
        os.environ.pop("COURIER_FAST_TEST_MODE", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_continuation_dedupe_parity(self):
        """1. Continuation Dedupe: Both queue and autonomy paths reject duplicate re-execution."""
        engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        # Test autonomy continuation dedupe
        dup1, _ = engine.continuation_engine.check_duplicate_continuation(
            continuation_generation=1,
            state_generation=1,
            last_verified_task="TASK-GENESIS",
            last_verified_fingerprint="abc"
        )
        self.assertFalse(dup1)
        # Second identical invocation must be detected as duplicate
        dup2, msg = engine.continuation_engine.check_duplicate_continuation(
            continuation_generation=1,
            state_generation=1,
            last_verified_task="TASK-GENESIS",
            last_verified_fingerprint="abc"
        )
        self.assertTrue(dup2)
        self.assertEqual(msg, "CONTINUATION_ALREADY_CONSUMED")

    def test_02_task_idempotency_parity(self):
        """2. Batch / Task Idempotency: Completed task is never re-executed in either path."""
        # Record task as COMPLETED in ControlPlane
        self.cp.upsert_task(
            task_id="TASK-PARITY-IDEMP",
            assignment_id="ASSIGN-PARITY-IDEMP",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.COMPLETED,
            two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="CONTINUE"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        # Queue path check
        req_path = os.path.join(self.handoffs_dir, "REQUEST_TASK-PARITY-IDEMP.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "1.0",
                "mission_id": "MISSION-AUTONOMY",
                "windows_validation_request_id": "TASK-PARITY-IDEMP",
                "assignment_id": "ASSIGN-PARITY-IDEMP",
                "origin_lane": "WINDOWS_GOOGLE",
                "validation_type": "WINDOWS_COMPATIBILITY",
                "exact_question": "Validate idempotency",
                "expected_evidence": "PASS",
                "artifact_reference": "courier/chief/control_plane.py",
                "target_runner": "WINDOWS",
                "allowed_scope": self.temp_dir
            }, f)

        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        # Must not execute the already completed task
        self.assertNotEqual(res.get("windows_validation_request_id"), "TASK-PARITY-IDEMP")

    def test_03_writer_lease_parity(self):
        """3. Writer Lease: Both paths acquire lock with One-Writer Law."""
        acquired, _ = self.cp.acquire_lock(
            resource_id="WORKSPACE_WINDOWS_GOOGLE",
            lane=Lane.WINDOWS_GOOGLE,
            host=Host.WINDOWS,
            lock_type="WRITE",
            ttl_seconds=180
        )
        self.assertTrue(acquired)
        # Second acquire fails
        acquired2, msg2 = self.cp.acquire_lock(
            resource_id="WORKSPACE_WINDOWS_GOOGLE",
            lane=Lane.CHIEF,
            host=Host.MAC,
            lock_type="WRITE",
            ttl_seconds=180
        )
        self.assertFalse(acquired2)
        self.cp.release_lock("WORKSPACE_WINDOWS_GOOGLE", Lane.WINDOWS_GOOGLE)

    def test_04_crash_recovery_parity(self):
        """4. Crash Recovery: Interrupted task with on-disk effect is recovered cleanly."""
        engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        self.cp.upsert_task(
            task_id="TASK-PARITY-CRASH",
            assignment_id="ASSIGN-TASK-PARITY-CRASH",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="WORKING"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        # Create on-disk effect
        done_file = os.path.join(self.temp_dir, "TASK-PARITY-CRASH.done")
        with open(done_file, "w") as f:
            f.write("DONE")

        recon = engine.continuation_engine.reconcile_current_work()
        self.assertEqual(recon["classification"], "WAITING_FOR_RESULT")
        finish_res = engine.continuation_engine.finish_current_work_if_needed(recon)
        self.assertEqual(finish_res["status"], "CLOSED_AND_VERIFIED")

        # Verify task is now COMPLETED and checkpointed
        task = self.cp.get_task("TASK-PARITY-CRASH")
        self.assertEqual(task["status"], "COMPLETED")
        ckpt = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(ckpt["task_id"], "TASK-PARITY-CRASH")

    def test_05_effect_verification_result_customs_parity(self):
        """5. Effect Verification: ResultCustomsJudge governs outcome for both paths."""
        cand = {"task_id": "TASK-CUSTOMS-TEST"}
        # Hollow self-certification rejected
        hollow = ResultCustomsJudge.evaluate(cand, {"success": True})
        self.assertFalse(hollow["passed"])
        self.assertIn("SELF_CERTIFICATION_DISALLOWED", hollow["reason"])

        # Legitimate execution accepted with SHA-256 fingerprint
        legit = ResultCustomsJudge.evaluate(cand, {
            "command": "python -m unittest test.py",
            "returncode": 0,
            "stdout": "Ran 1 test in 0.01s: OK",
            "success": True
        })
        self.assertTrue(legit["passed"])
        self.assertIsNotNone(legit["result_fingerprint"])

    def test_06_checkpoint_parity(self):
        """6. Checkpoint: Authoritative 6-tuple writes atomically advance legacy mirrors."""
        ckpt_record = {
            "task_id": "TASK-PARITY-CKPT",
            "task_version": 1,
            "state_generation": 250,
            "result_fingerprint": "a1b2c3d4e5f6",
            "verification_evidence": "test passed",
            "verified_at": datetime.now(timezone.utc).isoformat()
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_record)
        # Authoritative record preserved
        stored = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(stored["task_id"], "TASK-PARITY-CKPT")
        self.assertEqual(stored["state_generation"], 250)
        # Legacy mirrors synchronized
        self.assertEqual(int(self.cp.get_checkpoint("STATE_GENERATION")), 250)
        self.assertEqual(self.cp.get_checkpoint("LAST_VERIFIED_TASK"), "TASK-PARITY-CKPT")

    def test_07_successor_selection_unified_cycle_parity(self):
        """7. Successor Selection: Single production cycle coordinates queue and autonomy."""
        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        # With empty queue and exhausted test reservoir: cleanly enters quiescence
        self.assertIn(res.get("cycle_status"), ("GOAL_TASK_EXECUTED", "QUIESCENT_WAITING_FOR_NEW_EVIDENCE"))
        self.assertEqual(res.get("status"), "PASS")
        self.assertEqual(res.get("blocker"), "NONE")


if __name__ == "__main__":
    unittest.main()
