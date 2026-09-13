"""
test_durable_continuation.py - Test suite for WINDOWS COURIER P0 CRASH/RESUME + weiter IDEMPOTENCY
Verifies:
1. Pre-execution durable state persistence across simulated crashes.
2. Crash recovery: Interrupted running task is detected and reconstructed without false VERIFIED.
3. Idempotent 'weiter': Repeated continuation signals do not duplicate tasks (TASKS_DUPLICATED = 0).
4. No-Repeat Registry: Verified tasks are never rerun; successor is selected.
5. High-frequency burst test: 10x consecutive 'weiter' signals produce 0 task duplicates.
6. System diagnostics capture: Memory load, process health, and thermal evidence status.
"""

import os
import sys
import time
import json
import unittest
from datetime import datetime, timezone

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.durable_continuation import DurableContinuationManager

class TestDurableContinuation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.temp_dir = tempfile.mkdtemp()
        cls.state_file = os.path.join(cls.temp_dir, "test_durable_continuation.json")
        cls.mgr = DurableContinuationManager(state_file=cls.state_file)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        # Reset test metrics
        with self.mgr._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE continuation_metrics SET metric_value = 0")
            cur.execute("DELETE FROM durable_continuation_state WHERE task_id LIKE 'TEST-%'")
            cur.execute("DELETE FROM do_not_repeat_registry WHERE task_id LIKE 'TEST-%'")
            conn.commit()

    def test_01_pre_execution_state_persistence(self):
        """State is persisted before execution begins; survives simulated crash."""
        task_id = f"TEST-TASK-{int(time.time() * 1000)}"
        criteria = ["Test rule 1", "Test rule 2"]
        state = self.mgr.persist_pre_execution_state(
            mission_id="MISSION-TEST",
            goal_id="GOAL-TEST",
            task_id=task_id,
            task_version=1,
            acceptance_criteria=criteria
        )

        self.assertEqual(state["task_id"], task_id)
        self.assertEqual(state["status"], "RUNNING")
        self.assertEqual(state["verification_state"], "UNVERIFIED")

        # Re-instantiate manager (simulating fresh agent session / restart)
        new_mgr = DurableContinuationManager(state_file=self.state_file)
        with new_mgr._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM durable_continuation_state WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "RUNNING")
            self.assertEqual(row["verification_state"], "UNVERIFIED")

    def test_02_idempotent_weiter_while_task_running(self):
        """Repeated 'weiter' while task is actively running is suppressed without creating tasks."""
        task_id = f"TEST-RUNNING-{int(time.time() * 1000)}"
        self.mgr.persist_pre_execution_state(
            mission_id="MISSION-TEST",
            goal_id="GOAL-TEST",
            task_id=task_id,
            task_version=1,
            acceptance_criteria=["Criterion A"]
        )

        # First 'weiter'
        res1 = self.mgr.reconcile_weiter(active_worker_alive=True)
        self.assertEqual(res1["action"], "RECONCILE_RUNNING")
        self.assertTrue(res1["duplicate_suppressed"])

        # Second 'weiter'
        res2 = self.mgr.reconcile_weiter(active_worker_alive=True)
        self.assertEqual(res2["action"], "RECONCILE_RUNNING")
        self.assertTrue(res2["duplicate_suppressed"])

        metrics = self.mgr.get_metrics()
        self.assertEqual(metrics["duplicate_continuations_received"], 2)
        self.assertEqual(metrics["duplicate_continuations_suppressed"], 2)
        self.assertEqual(metrics["tasks_duplicated"], 0)

    def test_03_crash_interruption_recovery(self):
        """Worker crash mid-execution: 'weiter' detects dead worker and reconstructs task."""
        task_id = f"TEST-CRASH-{int(time.time() * 1000)}"
        self.mgr.persist_pre_execution_state(
            mission_id="MISSION-TEST",
            goal_id="GOAL-TEST",
            task_id=task_id,
            task_version=1,
            acceptance_criteria=["Verify crash restart"]
        )

        # Worker dies (active_worker_alive=False)
        rec = self.mgr.reconcile_weiter(active_worker_alive=False)
        self.assertEqual(rec["action"], "RECOVER_INTERRUPTED")
        self.assertEqual(rec["task_id"], task_id)
        self.assertEqual(rec["reason"], "WORKER_CRASHED_MID_EXECUTION")
        self.assertFalse(rec["duplicate_suppressed"])

    def test_04_verified_task_no_repeat_and_successor_selection(self):
        """Verified task is not rerun upon 'weiter'; successor task is selected."""
        task_id = f"TEST-DONE-{int(time.time() * 1000)}"
        successor_id = f"TEST-NEXT-{int(time.time() * 1000)}"
        criteria = ["Complete build", "Pass test suite"]

        self.mgr.persist_pre_execution_state(
            mission_id="MISSION-TEST",
            goal_id="GOAL-TEST",
            task_id=task_id,
            task_version=1,
            acceptance_criteria=criteria
        )

        # Mark verified with successor
        self.mgr.update_verification_and_complete(
            task_id=task_id,
            result_payload={"exitcode": 0, "verified": True},
            is_verified=True,
            successor_id=successor_id
        )

        # Reconcile 'weiter': must advance to successor
        rec = self.mgr.reconcile_weiter(active_worker_alive=False)
        self.assertEqual(rec["action"], "ADVANCE_TO_SUCCESSOR")
        self.assertEqual(rec["completed_task_id"], task_id)
        self.assertEqual(rec["successor_task_id"], successor_id)
        self.assertTrue(rec["duplicate_suppressed"])

        # Check DO_NOT_REPEAT registry
        fp = self.mgr.compute_task_fingerprint(task_id, 1, criteria)
        self.assertTrue(self.mgr.is_task_verified(fp))

    def test_05_rapid_burst_10x_weiter(self):
        """10 consecutive 'weiter' inputs in rapid succession produce 0 task duplicates."""
        task_id = f"TEST-BURST-{int(time.time() * 1000)}"
        self.mgr.persist_pre_execution_state(
            mission_id="MISSION-TEST",
            goal_id="GOAL-TEST",
            task_id=task_id,
            task_version=1,
            acceptance_criteria=["Criterion 1"]
        )

        for _ in range(10):
            res = self.mgr.reconcile_weiter(active_worker_alive=True)
            self.assertEqual(res["action"], "RECONCILE_RUNNING")

        metrics = self.mgr.get_metrics()
        self.assertEqual(metrics["duplicate_continuations_received"], 10)
        self.assertEqual(metrics["duplicate_continuations_suppressed"], 10)
        self.assertEqual(metrics["tasks_duplicated"], 0)

    def test_06_system_diagnostics_evidence(self):
        """System diagnostics return memory load, process health, and thermal evidence status."""
        diag = self.mgr.get_system_diagnostics()
        self.assertIsNotNone(diag["memory_load_pct"])
        self.assertGreater(diag["ram_total_gb"], 0)
        self.assertEqual(diag["thermal_status"], "THERMAL_CAUSE_UNPROVEN")
        self.assertIsNotNone(diag["db_size_bytes"])

if __name__ == "__main__":
    unittest.main()
