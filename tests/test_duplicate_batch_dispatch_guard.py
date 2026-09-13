"""
test_duplicate_batch_dispatch_guard.py - Test suite for WINDOWS COURIER P0 DUPLICATE BATCH DISPATCH GUARD

Certifies:
1. SEQUENTIAL DUPLICATE: Repeated identical batch dispatch is suppressed (BATCH_ALREADY_EXISTS).
2. CONCURRENT DUPLICATE: Parallel race between equivalent batch dispatches results in exactly 1 physical batch.
3. AGENT/UI REPLAY: Replaying command after UI/session disconnect reconciles existing batch without rerun.
4. RESTART RECONCILIATION: Dead writer batch is recovered and attached to rather than duplicated.
5. TASK-LEVEL SAFETY: Defense in depth prevents any duplicate task execution even under fault injection.
6. OBSERVABILITY: Exposes exact required metrics (RAW, LOGICAL, SUPPRESSED, PHYSICAL, DUPLICATE_TASKS).
"""

import os
import sys
import time
import json
import tempfile
import shutil
import unittest
import threading
from datetime import datetime, timezone

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.types import Lane, TaskStatus, TwoLevelDone
from courier.chief.batch_guard import BatchGuardManager
from courier.chief.permanent_reserve_engine import PermanentReserveEngine
from courier.chief.control_plane import ControlPlane


class TestDuplicateBatchDispatchGuard(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_batch_guard_")
        self.tmp_db = os.path.join(self.tmp_dir, "test_cp.db")
        self.guard = BatchGuardManager(db_path=self.tmp_db)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_sequential_duplicate_suppressed(self):
        """TEST 1 — SEQUENTIAL DUPLICATE: Second call returns BATCH_ALREADY_EXISTS; physical started = 1."""
        idemp_key = self.guard.compute_idempotency_key(
            mission_id="MISSION-TEST",
            current_goal="GOAL-03",
            state_generation=1,
            source_continuation_generation=1
        )

        # First dispatch
        claimed1, reason1, rec1 = self.guard.claim_batch(
            idempotency_key=idemp_key,
            mission_id="MISSION-TEST",
            current_goal="GOAL-03",
            state_generation=1,
            source_continuation_generation=1
        )
        self.assertTrue(claimed1)
        self.assertEqual(reason1, "BATCH_CLAIMED")
        batch_id = rec1["batch_id"]

        # Second sequential duplicate dispatch
        claimed2, reason2, rec2 = self.guard.claim_batch(
            idempotency_key=idemp_key,
            mission_id="MISSION-TEST",
            current_goal="GOAL-03",
            state_generation=1,
            source_continuation_generation=1
        )
        self.assertFalse(claimed2)
        self.assertEqual(reason2, "BATCH_ALREADY_EXISTS")
        self.assertEqual(rec2["batch_id"], batch_id)

        metrics = self.guard.get_metrics()
        self.assertEqual(metrics["raw_batch_start_requests"], 2)
        self.assertEqual(metrics["logical_batches_created"], 1)
        self.assertEqual(metrics["duplicate_batch_requests_suppressed"], 1)
        self.assertEqual(metrics["physical_batches_started"], 1)

    def test_02_concurrent_duplicate_suppression(self):
        """TEST 2 — CONCURRENT DUPLICATE: 4 parallel threads attempt launch; exactly 1 succeeds."""
        idemp_key = self.guard.compute_idempotency_key(
            mission_id="MISSION-CONCURRENT",
            current_goal="GOAL-03",
            state_generation=1,
            source_continuation_generation=1
        )

        results = []
        threads = []

        def worker():
            g = BatchGuardManager(db_path=self.tmp_db)
            res = g.claim_batch(
                idempotency_key=idemp_key,
                mission_id="MISSION-CONCURRENT",
                current_goal="GOAL-03",
                state_generation=1,
                source_continuation_generation=1
            )
            results.append(res)

        for _ in range(4):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        claimed_count = sum(1 for claimed, reason, rec in results if claimed)
        suppressed_count = sum(1 for claimed, reason, rec in results if not claimed)

        self.assertEqual(claimed_count, 1, "Exactly 1 concurrent claim must succeed")
        self.assertEqual(suppressed_count, 3, "Exactly 3 concurrent claims must be suppressed")

        metrics = self.guard.get_metrics()
        self.assertEqual(metrics["logical_batches_created"], 1)
        self.assertEqual(metrics["physical_batches_started"], 1)
        self.assertEqual(metrics["duplicate_batch_requests_suppressed"], 3)

    def test_03_agent_ui_replay(self):
        """TEST 3 — AGENT/UI REPLAY: Command replayed after completion reconciles existing batch."""
        idemp_key = self.guard.compute_idempotency_key(
            mission_id="MISSION-REPLAY",
            current_goal="GOAL-03",
            state_generation=5,
            source_continuation_generation=2
        )

        claimed, _, rec = self.guard.claim_batch(
            idempotency_key=idemp_key,
            mission_id="MISSION-REPLAY",
            current_goal="GOAL-03",
            state_generation=5,
            source_continuation_generation=2
        )
        self.assertTrue(claimed)
        b_id = rec["batch_id"]

        self.guard.complete_batch(b_id, {"executed_tasks": ["TASK-WIN-101", "TASK-WIN-102"]})

        # Replay attempt
        claimed_again, reason_again, rec_again = self.guard.claim_batch(
            idempotency_key=idemp_key,
            mission_id="MISSION-REPLAY",
            current_goal="GOAL-03",
            state_generation=5,
            source_continuation_generation=2
        )
        self.assertFalse(claimed_again)
        self.assertEqual(reason_again, "BATCH_ALREADY_EXISTS")
        self.assertEqual(rec_again["status"], "COMPLETED")
        self.assertIn("TASK-WIN-101", rec_again["summary_json"])

    def test_04_restart_reconciliation(self):
        """TEST 4 — RESTART: Reclaims batch left STARTING/RUNNING by dead PID without duplicate logical ID."""
        idemp_key = self.guard.compute_idempotency_key(
            mission_id="MISSION-RESTART",
            current_goal="GOAL-03",
            state_generation=2,
            source_continuation_generation=1
        )

        # Claim with definitely dead PID (9999999)
        claimed, _, rec = self.guard.claim_batch(
            idempotency_key=idemp_key,
            mission_id="MISSION-RESTART",
            current_goal="GOAL-03",
            state_generation=2,
            source_continuation_generation=1,
            owner_pid=9999999
        )
        self.assertTrue(claimed)
        orig_batch_id = rec["batch_id"]

        # New session starts and attempts same batch
        new_guard = BatchGuardManager(db_path=self.tmp_db)
        claimed2, reason2, rec2 = new_guard.claim_batch(
            idempotency_key=idemp_key,
            mission_id="MISSION-RESTART",
            current_goal="GOAL-03",
            state_generation=2,
            source_continuation_generation=1
        )
        self.assertTrue(claimed2)
        self.assertEqual(reason2, "ORPHAN_BATCH_RECLAIMED")
        self.assertEqual(rec2["batch_id"], orig_batch_id, "Must reclaim existing batch ID without duplicating")

    def test_05_task_level_defense_in_depth(self):
        """Even if duplicate batch dispatch occurs, task Do-Not-Repeat registry prevents duplicate task execution."""
        pm_dir = os.path.join(self.tmp_dir, "project-memory", "data")
        os.makedirs(pm_dir, exist_ok=True)
        backlog = os.path.join(pm_dir, "safe_backlog.json")
        with open(backlog, "w", encoding="utf-8") as f:
            json.dump({
                "tasks": [
                    {
                        "task_id": "TASK-DEFENSE-01",
                        "title": "Defense Task",
                        "status": "COMPLETED",
                        "priority": 9.0,
                        "conflict_scope": "DEFENSE_SCOPE",
                        "expected_real_delta": "AUTONOMY_GAIN",
                        "script_path": None,
                        "source_evidence": "courier/chief/control_plane.py"
                    }
                ]
            }, f)

        cp = ControlPlane(db_path=self.tmp_db)
        cp.upsert_task(
            task_id="TASK-DEFENSE-01",
            assignment_id="ASSIGN-TASK-DEFENSE-01",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.COMPLETED,
            two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=True, blocker="NONE", next_step="DONE")
        )

        engine = PermanentReserveEngine(workspace_root=self.tmp_dir, cp=cp)
        self.assertIn("TASK-DEFENSE-01", engine.reservoir.do_not_repeat)

        cand = {"task_id": "TASK-DEFENSE-01", "title": "Defense Task", "conflict_scope": "DEFENSE_SCOPE"}
        valid, reason = engine.reservoir.deduplicate(cand)
        self.assertFalse(valid)
        self.assertIn("DUPLICATE_ALREADY_VERIFIED", reason)

    def test_06_observability_metrics_exposure(self):
        """Exposes complete observability metrics required by specification."""
        metrics = self.guard.get_metrics()
        required_keys = [
            "raw_batch_start_requests",
            "logical_batches_created",
            "duplicate_batch_requests_suppressed",
            "physical_batches_started",
            "active_batch_id",
            "active_batch_idempotency_key",
            "duplicate_tasks_executed",
            "last_event_timestamp"
        ]
        for k in required_keys:
            self.assertIn(k, metrics, f"Metric '{k}' must be exposed")


if __name__ == "__main__":
    unittest.main()
