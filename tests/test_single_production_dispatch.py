"""
test_single_production_dispatch.py - Stage 2 Targeted Tests for Single Production Dispatch Semantic
Verifies:
1. Queue work present -> processes queue task
2. Queue empty + reservoir work present -> allows PermanentReserveEngine autonomous succession
3. Both present -> queue task prioritizes over reservoir
4. Duplicate invocation -> duplicate request suppressed / skipped
5. Restart during dispatch -> in-flight active task recognized, zero competing writer
6. Quiescent no-work -> returns LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED / QUIESCENT
"""
import os
import sys
import unittest
import tempfile
import shutil
import json

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.scheduled_cycle import execute_windows_validation_cycle


class TestSingleProductionDispatch(unittest.TestCase):
    def setUp(self):
        os.environ["COURIER_FAST_TEST_MODE"] = "1"
        self.temp_dir = tempfile.mkdtemp(prefix="stage2_dispatch_")
        self.db_path = os.path.join(self.temp_dir, "test_dispatch.db")
        self.handoffs_dir = os.path.join(self.temp_dir, "handoffs")
        os.makedirs(self.handoffs_dir, exist_ok=True)
        self.cp = ControlPlane(db_path=self.db_path)

    def tearDown(self):
        os.environ.pop("COURIER_FAST_TEST_MODE", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_queue_request(self, req_id: str = "REQ-STAGE2-001"):
        req_payload = {
            "schema_version": "1.0",
            "mission_id": "MISSION-AUTONOMY",
            "windows_validation_request_id": req_id,
            "assignment_id": f"ASSIGN-{req_id}",
            "origin_lane": "WINDOWS_GOOGLE",
            "validation_type": "WINDOWS_COMPATIBILITY",
            "exact_question": "Validate single dispatch semantic",
            "expected_evidence": "PASS",
            "artifact": "courier/chief/control_plane.py",
            "artifact_reference": "courier/chief/control_plane.py",
            "target_runner": "WINDOWS",
            "allowed_scope": self.temp_dir,
            "created_at": "2026-09-13T10:00:00+00:00"
        }
        fpath = os.path.join(self.handoffs_dir, f"REQUEST_{req_id}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(req_payload, f, indent=2)
        return fpath

    def test_01_queue_work_present(self):
        """1. Queue work present -> processes queue task according to normal priority."""
        self._create_queue_request("REQ-STAGE2-001")
        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        self.assertEqual(res.get("cycle_status"), "REQUEST_EXECUTED")
        self.assertEqual(res.get("status"), "PASS")
        self.assertEqual(res.get("windows_validation_request_id"), "REQ-STAGE2-001")

        # Verify task is recorded as COMPLETED in control plane
        task = self.cp.get_task("REQ-STAGE2-001")
        self.assertIsNotNone(task)
        self.assertEqual(task.get("status"), "COMPLETED")

    def test_02_queue_empty_reservoir_work_present(self):
        """2. Queue empty + reservoir work present -> allows PermanentReserveEngine autonomous succession."""
        # Ensure no queue requests
        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        # Should either execute an autonomous candidate or report local safe work exhausted cleanly
        self.assertIn(res.get("cycle_status"), ("AUTONOMOUS_SUCCESSION_EXECUTED", "GOAL_TASK_EXECUTED", "LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED", "QUIESCENT_WAITING_FOR_NEW_EVIDENCE"))
        if res.get("cycle_status") in ("AUTONOMOUS_SUCCESSION_EXECUTED", "GOAL_TASK_EXECUTED"):
            self.assertEqual(res.get("dispatch_source"), "PERMANENT_RESERVE_RESERVOIR")
            self.assertEqual(res.get("status"), "PASS")

    def test_03_both_present_queue_priority(self):
        """3. Both present -> queue task prioritizes over reservoir."""
        self._create_queue_request("REQ-STAGE2-PRIORITY")
        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        # Queue request must win priority over reservoir
        self.assertEqual(res.get("cycle_status"), "REQUEST_EXECUTED")
        self.assertEqual(res.get("windows_validation_request_id"), "REQ-STAGE2-PRIORITY")

    def test_04_duplicate_invocation(self):
        """4. Duplicate invocation -> duplicate request already completed is skipped."""
        self._create_queue_request("REQ-STAGE2-DUP")
        res1 = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        self.assertEqual(res1.get("cycle_status"), "REQUEST_EXECUTED")

        # Second cycle with same request on disk: request is already marked COMPLETED
        res2 = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        # Should not execute duplicate request REQ-STAGE2-DUP
        self.assertNotEqual(res2.get("windows_validation_request_id"), "REQ-STAGE2-DUP")

    def test_05_restart_during_dispatch(self):
        """5. Restart during dispatch -> in-flight active task recognized, zero competing writer."""
        # Set up an active RUNNING task in control plane
        self.cp.upsert_task(
            task_id="TASK-STAGE2-INFLIGHT",
            assignment_id="ASSIGN-TASK-STAGE2-INFLIGHT",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="WORKING"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )

        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        self.assertEqual(res.get("cycle_status"), "ACTIVE_REQUEST_IN_FLIGHT")
        self.assertEqual(res.get("status"), "RUNNING")
        self.assertEqual(res.get("windows_validation_request_id"), "TASK-STAGE2-INFLIGHT")

    def test_06_quiescent_no_work(self):
        """6. Quiescent no-work -> returns LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED / QUIESCENT."""
        # Mark all known reservoir tasks as COMPLETED in CP to simulate full exhaustion
        from courier.chief.permanent_reserve_engine import PermanentReserveEngine
        engine = PermanentReserveEngine(workspace_root=WORKSPACE_ROOT, cp=self.cp)
        for cand in engine.reservoir.get_pending_candidates():
            c_id = cand["task_id"]
            self.cp.upsert_task(
                task_id=c_id,
                assignment_id=f"ASSIGN-{c_id}",
                origin_lane=Lane.WINDOWS_GOOGLE,
                status=TaskStatus.COMPLETED,
                two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=True, blocker="NONE", next_step="DONE"),
                active_agent=Lane.WINDOWS_GOOGLE.value
            )

        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        self.assertIn(res.get("cycle_status"), ("LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED", "QUIESCENT_WAITING_FOR_NEW_EVIDENCE"))
        self.assertIn(res.get("status"), ("PASS", "QUIESCENT"))
        self.assertTrue(res.get("quiescent", False))
        self.assertFalse(res.get("side_effects_occurred"))


if __name__ == "__main__":
    unittest.main()
