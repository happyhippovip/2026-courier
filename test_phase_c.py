import unittest
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from chief.result_customs import ResultCustomsJudge
from chief.control_plane import ControlPlane
from chief.types import TaskStatus, Lane, TwoLevelDone

class TestPhaseCResultCustoms(unittest.TestCase):
    def setUp(self):
        self.db_name = f"test_phase_c_{uuid.uuid4().hex}.sqlite"
        self.cp = ControlPlane(db_path=self.db_name)
        # Seed basic valid state
        self.cp.upsert_task("TASK-VALID", "ASSIGN-VALID", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        with self.cp.get_connection() as conn:
            conn.execute("""
            INSERT INTO dispatch_queue (dispatch_id, target_lane, target_host, assignment_id, source_lane, prompt_text, envelope_json, status, created_at)
            VALUES ('DISPATCH-VALID', 'WINDOWS_GOOGLE', 'HOST-A', 'ASSIGN-VALID', 'CHIEF', 'run', '{}', 'DISPATCHED', '2026-09-15T00:00:00Z');
            """)

    def tearDown(self):
        self.cp = None
        if os.path.exists(self.db_name):
            try: os.remove(self.db_name)
            except: pass
        if os.path.exists(self.db_name + "-wal"):
            try: os.remove(self.db_name + "-wal")
            except: pass
        if os.path.exists(self.db_name + "-shm"):
            try: os.remove(self.db_name + "-shm")
            except: pass

    def test_01_missing_ids(self):
        cand = {"task_id": "TASK-VALID"}
        ev = {"command": "ls", "stdout": "ok", "returncode": 0} # missing assignment_id/dispatch_id
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Missing assignment_id", res["reason"])

    def test_02_task_does_not_exist(self):
        cand = {"task_id": "TASK-GHOST"}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-VALID", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Task TASK-GHOST does not exist", res["reason"])

    def test_03_task_assignment_mismatch(self):
        cand = {"task_id": "TASK-VALID"}
        ev = {"assignment_id": "ASSIGN-WRONG", "dispatch_id": "DISPATCH-VALID", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Task assignment_id mismatch", res["reason"])

    def test_04_dispatch_does_not_exist(self):
        cand = {"task_id": "TASK-VALID"}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-GHOST", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Dispatch DISPATCH-GHOST does not exist", res["reason"])

    def test_05_dispatch_assignment_mismatch(self):
        with self.cp.get_connection() as conn:
            conn.execute("""
            INSERT INTO dispatch_queue (dispatch_id, target_lane, target_host, assignment_id, source_lane, prompt_text, envelope_json, status, created_at)
            VALUES ('DISPATCH-OTHER', 'WINDOWS_GOOGLE', 'HOST-A', 'ASSIGN-OTHER', 'CHIEF', 'run', '{}', 'DISPATCHED', '2026-09-15T00:00:00Z');
            """)
        cand = {"task_id": "TASK-VALID"}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-OTHER", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Dispatch assignment_id mismatch", res["reason"])

    def test_06_directory_traversal_task_id(self):
        cand = {"task_id": "../etc/passwd"}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-VALID", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("directory traversal", res["reason"])

    def test_07_directory_traversal_target_file(self):
        cand = {"task_id": "TASK-VALID", "target_files": ["dir/../../passwd"]}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-VALID", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("directory traversal", res["reason"])

    def test_08_mac_reserved_scope(self):
        cand = {"task_id": "TASK-VALID", "target_files": ["courier/mac/agent.py"]}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-VALID", "command": "ls", "stdout": "ok", "returncode": 0}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("MAC_RESERVED_SCOPE_VIOLATION", res["reason"])

    def test_09_missing_execution_evidence(self):
        cand = {"task_id": "TASK-VALID"}
        res = ResultCustomsJudge.evaluate(cand, None, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Missing execution evidence", res["reason"])

    def test_10_hollow_self_certification(self):
        cand = {"task_id": "TASK-VALID"}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-VALID", "success": True}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Worker claimed success without command or execution logs", res["reason"])

    def test_11_exit_code_zero_empty_stdout(self):
        cand = {"task_id": "TASK-VALID"}
        ev = {"assignment_id": "ASSIGN-VALID", "dispatch_id": "DISPATCH-VALID", "command": "echo", "returncode": 0, "stdout": ""}
        res = ResultCustomsJudge.evaluate(cand, ev, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Exit code 0 provided but observed behavior is empty", res["reason"])

if __name__ == '__main__':
    unittest.main()
