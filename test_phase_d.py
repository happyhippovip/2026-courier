import unittest
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from chief.control_plane import ControlPlane
from chief.types import TaskStatus, Lane, TwoLevelDone, Host
from chief.coordinator import ChiefCoordinator

class TestPhaseDIdempotencyRecovery(unittest.TestCase):
    def setUp(self):
        self.db_name = f"test_phase_d_{uuid.uuid4().hex}.sqlite"
        self.cp = ControlPlane(db_path=self.db_name)
        self.handoffs_dir = os.path.join(os.path.dirname(__file__), "test_handoffs_d")
        os.makedirs(self.handoffs_dir, exist_ok=True)

    def tearDown(self):
        self.cp = None
        if os.path.exists(self.db_name):
            try: os.remove(self.db_name)
            except: pass
        if os.path.exists(self.db_name + "-wal"):
            try: os.remove(self.db_name + "-wal")
            except: pass
        import shutil
        if os.path.exists(self.handoffs_dir):
            shutil.rmtree(self.handoffs_dir)

    def test_D01_identical_duplicate_idempotent(self):
        self.cp.upsert_task("T-1", "A-1", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H1")
        # Identical duplicate should not raise
        self.cp.upsert_task("T-1", "A-1", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H1")
        t = self.cp.get_task("T-1")
        self.assertEqual(t["canonical_fingerprint"], "H1")

    def test_D02_conflicting_duplicate_fails_closed(self):
        self.cp.upsert_task("T-2", "A-2", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"), canonical_fingerprint="H1")
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.cp.upsert_task("T-2", "A-2", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"), canonical_fingerprint="H2")

    def test_D03_stale_dispatch_fails_closed(self):
        # Dispatch code is in chief.scheduled_cycle but we can simulate the rejection here or just test the DB state
        # A completed task cannot be dispatched again.
        self.cp.upsert_task("T-3", "A-3", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H1")
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.cp.upsert_task("T-3", "A-3", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"), canonical_fingerprint="H1")

    def test_D04_replay_cannot_steal_lease(self):
        success, reason = self.cp.acquire_lock("R-1", Lane.WINDOWS_GOOGLE, Host.WINDOWS, "WRITE", 300, True)
        self.assertTrue(success)
        # Another host tries to acquire
        success, reason = self.cp.acquire_lock("R-1", Lane.MAC_GOOGLE, Host.MAC, "WRITE", 300, True)
        self.assertFalse(success)
        self.assertIn("SINGLE_WRITER_CONFLICT", reason)

    def test_D05_terminal_legacy_mutation_rejected(self):
        # Insert legacy row
        with self.cp.get_connection() as conn:
            conn.execute("INSERT INTO tasks (task_id, assignment_id, origin_lane, status, local_step_erledigt, gesamtaufgabe_erledigt, blocker, next_step, active_agent, created_at, updated_at) VALUES ('T-5', 'A-5', 'WINDOWS_GOOGLE', 'COMPLETED', 1, 1, 'NONE', 'NONE', 'WINDOWS_GOOGLE', '2026-09-15T00:00:00Z', '2026-09-15T00:00:00Z')")
        with self.assertRaisesRegex(RuntimeError, "Terminal Legacy Mutation Rejected"):
            self.cp.upsert_task("T-5", "A-5", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H1")

    def test_D06_same_task_different_assignment_rejected(self):
        self.cp.upsert_task("T-6", "A-6A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"), canonical_fingerprint="H1")
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.cp.upsert_task("T-6", "A-6B", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"), canonical_fingerprint="H1")

    def test_D07_failed_state_cannot_be_mutated(self):
        self.cp.upsert_task("T-7", "A-7", Lane.WINDOWS_GOOGLE, TaskStatus.FAILED, TwoLevelDone(False, False, "NONE", "NEXT"), canonical_fingerprint="H1")
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.cp.upsert_task("T-7", "A-7", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H1")

    def test_D08_original_task_unchanged_on_conflict(self):
        self.cp.upsert_task("T-8", "A-8", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H1")
        try:
            self.cp.upsert_task("T-8", "A-8", Lane.WINDOWS_GOOGLE, TaskStatus.COMPLETED, TwoLevelDone(True, True, "NONE", "NONE"), canonical_fingerprint="H2")
        except:
            pass
        t = self.cp.get_task("T-8")
        self.assertEqual(t["canonical_fingerprint"], "H1")

    def test_D09_deterministic_fallback_fails_closed(self):
        coord = ChiefCoordinator(cp=self.cp, handoffs_dir=self.handoffs_dir)
        task_id = "TASK-F"
        res = coord.execute_deterministic_fallback(task_id, handoffs_dir=self.handoffs_dir)
        self.assertFalse(res["success"])
        self.assertEqual(res["runner"], "DETERMINISTIC_CLI1_FALLBACK")
        self.assertTrue(res["fallback_used"])

if __name__ == '__main__':
    unittest.main()
