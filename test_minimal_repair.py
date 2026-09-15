import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from chief.coordinator import ChiefCoordinator
from chief.scheduled_cycle import execute_windows_validation_cycle
from chief.control_plane import ControlPlane
from chief.types import TaskStatus, Lane, Host, TwoLevelDone
from chief.ingestor import ChiefIngestor
class TestMinimalRepair(unittest.TestCase):
    
    def setUp(self):
        import uuid
        # Create a fresh DB for each test
        self.db_name = f"test_db_{uuid.uuid4().hex}.sqlite"
        self.cp = ControlPlane(db_path=self.db_name)
        self.handoffs_dir = os.path.join(os.path.dirname(__file__), "test_handoffs")
        os.makedirs(self.handoffs_dir, exist_ok=True)
        with open(os.path.join(self.handoffs_dir, "REQUEST_123.json"), "w") as f:
            f.write('{"windows_validation_request_id": "TASK-123", "assignment_id": "ASSIGN-123"}')
        self.patcher_req = patch('chief.scheduled_cycle.ChiefRequestValidator.validate_request_dict', return_value=(True, []))
        self.patcher_fb = patch('chief.scheduled_cycle.FallbackAssignmentValidator.validate_assignment_dict', return_value=(False, []))
        self.patcher_req.start()
        self.patcher_fb.start()

    def tearDown(self):
        self.patcher_req.stop()
        self.patcher_fb.stop()
        import shutil
        if os.path.exists(self.handoffs_dir):
            shutil.rmtree(self.handoffs_dir)
        archive_dir = os.path.join(os.path.dirname(self.handoffs_dir), "archive")
        if os.path.exists(archive_dir):
            shutil.rmtree(archive_dir)
        # Clear connections
        self.cp = None
        if os.path.exists(self.db_name):
            try:
                os.remove(self.db_name)
            except:
                pass
        if os.path.exists(self.db_name + "-wal"):
            try:
                os.remove(self.db_name + "-wal")
            except:
                pass
        if os.path.exists(self.db_name + "-shm"):
            try:
                os.remove(self.db_name + "-shm")
            except:
                pass

    @patch('chief.scheduled_cycle.ChiefCoordinator.execute_dispatch_with_fallback')
    @patch('chief.scheduled_cycle.ChiefCoordinator.prepare_dispatch')
    @patch('chief.scheduled_cycle.ChiefCoordinator.acquire_resource')
    @patch('chief.scheduled_cycle.ChiefCoordinator.release_resource')
    def test_returncode_absent_fails_closed(self, mock_rel, mock_acq, mock_prep, mock_exec):
        mock_prep.return_value = {"dispatch_id": "DISP-1"}
        mock_exec.return_value = {"success": True, "stdout": "PASS"} # missing returncode
        
        with self.assertRaisesRegex(RuntimeError, "Fail Closed: Real execution evidence lacks an explicit return code"):
            execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)

    @patch('chief.scheduled_cycle.ChiefCoordinator.execute_dispatch_with_fallback')
    @patch('chief.scheduled_cycle.ChiefCoordinator.prepare_dispatch')
    @patch('chief.scheduled_cycle.ChiefCoordinator.acquire_resource')
    @patch('chief.scheduled_cycle.ChiefCoordinator.release_resource')
    def test_returncode_nonzero_with_fake_success_fails_closed(self, mock_rel, mock_acq, mock_prep, mock_exec):
        mock_prep.return_value = {"dispatch_id": "DISP-1"}
        mock_exec.return_value = {"success": False, "returncode": 1, "stdout": "Two-Level Done PASS"}
        
        with self.assertRaisesRegex(RuntimeError, "Result Customs rejected dispatch for TASK-123"):
            execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)

    @patch('chief.scheduled_cycle.ChiefCoordinator.execute_dispatch_with_fallback')
    @patch('chief.scheduled_cycle.ChiefCoordinator.prepare_dispatch')
    @patch('chief.scheduled_cycle.ChiefCoordinator.acquire_resource')
    @patch('chief.scheduled_cycle.ChiefCoordinator.release_resource')
    def test_returncode_zero_with_missing_stdout_fails_closed(self, mock_rel, mock_acq, mock_prep, mock_exec):
        mock_prep.return_value = {"dispatch_id": "DISP-1"}
        mock_exec.return_value = {"success": True, "returncode": 0, "stdout": ""} # missing stdout
        
        with self.assertRaisesRegex(RuntimeError, "Fail Closed: Real worker stdout/evidence is missing"):
            execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)

    def test_coordinator_nonzero_exit_is_not_success(self):
        coord = ChiefCoordinator(cp=self.cp, handoffs_dir=self.handoffs_dir)
        with patch('subprocess.run') as mock_run:
            mock_res = MagicMock()
            mock_res.returncode = 1
            mock_res.stdout = "Two-Level Done PASS"
            mock_res.stderr = ""
            mock_res.__bool__.return_value = True
            mock_run.return_value = mock_res
            
            coord.control_plane.enqueue_dispatch("DISP-1", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-123", "text", {}, Lane.WINDOWS_CLI_1)
            
            res = coord.execute_local_headless_dispatch("DISP-1", handoffs_dir=self.handoffs_dir)
            self.assertFalse(res["success"])
            self.assertEqual(res["returncode"], 1)
            self.assertIn("Execution failed with returncode 1", res["error"])

    def test_A_happy_path_ids_match(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        self.cp.enqueue_dispatch("DISP-A", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-A", "prompt", {})
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertTrue(res["passed"])

    def test_B_missing_dispatch_id(self):
        from chief.result_customs import ResultCustomsJudge
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Missing assignment_id or dispatch_id", res["reason"])

    def test_C_missing_assignment_id(self):
        from chief.result_customs import ResultCustomsJudge
        cand = {"task_id": "TASK-A"}
        evidence = {"dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Missing assignment_id or dispatch_id", res["reason"])

    def test_D_task_does_not_exist(self):
        from chief.result_customs import ResultCustomsJudge
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("does not exist", res["reason"])

    def test_E_task_assignment_mismatch(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-B", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Task assignment_id mismatch", res["reason"])

    def test_F_dispatch_does_not_exist(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Dispatch DISP-A does not exist", res["reason"])

    def test_G_dispatch_assignment_mismatch(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        self.cp.enqueue_dispatch("DISP-A", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-B", "prompt", {})
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])
        self.assertIn("Dispatch assignment_id mismatch", res["reason"])

    def test_H_replay_prevention_fingerprint(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        self.cp.enqueue_dispatch("DISP-A", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-A", "prompt", {})
        self.cp.enqueue_dispatch("DISP-B", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-A", "prompt", {})
        
        cand = {"task_id": "TASK-A"}
        evidence1 = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": "test passed OK"}
        evidence2 = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-B", "returncode": 0, "stdout": "test passed OK"}
        
        res1 = ResultCustomsJudge.evaluate(cand, evidence1, cp=self.cp)
        res2 = ResultCustomsJudge.evaluate(cand, evidence2, cp=self.cp)
        
        self.assertTrue(res1["passed"])
        self.assertTrue(res2["passed"])
        self.assertNotEqual(res1["result_fingerprint"], res2["result_fingerprint"])

    def test_I_exit_code_zero_empty_stdout(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        self.cp.enqueue_dispatch("DISP-A", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-A", "prompt", {})
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 0, "stdout": ""}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])

    def test_J_nonzero_exit_code(self):
        from chief.result_customs import ResultCustomsJudge
        self.cp.upsert_task("TASK-A", "ASSIGN-A", Lane.WINDOWS_GOOGLE, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "NEXT"))
        self.cp.enqueue_dispatch("DISP-A", Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-A", "prompt", {})
        cand = {"task_id": "TASK-A"}
        evidence = {"assignment_id": "ASSIGN-A", "dispatch_id": "DISP-A", "returncode": 1, "stdout": "test OK"}
        res = ResultCustomsJudge.evaluate(cand, evidence, cp=self.cp)
        self.assertFalse(res["passed"])

class TestImmutabilityRepair(unittest.TestCase):
    def setUp(self):
        import uuid
        import os
        import shutil
        self.db_path = f"test_immutability_{uuid.uuid4().hex}.db"
        self.cp = ControlPlane(self.db_path)
        self.handoffs_dir = f"test_handoffs_{uuid.uuid4().hex}"
        os.makedirs(self.handoffs_dir, exist_ok=True)
        self.ingestor = ChiefIngestor(self.cp, self.handoffs_dir)

    def tearDown(self):
        import os, shutil
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass
        if os.path.exists(self.handoffs_dir):
            shutil.rmtree(self.handoffs_dir)

    def test_A_idempotent_replay_allowed(self):
        payload = {
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        self.ingestor._extract_task(payload, Lane.WINDOWS_CLI_1, "ASSIGN-1")
        self.ingestor._extract_task(payload, Lane.WINDOWS_CLI_1, "ASSIGN-1")
        task = self.cp.get_task("TASK-ASSIGN-1")
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], TaskStatus.RUNNING.value)

    def test_B_differing_metadata_ignored_for_idempotency(self):
        payload1 = {
            "some_metadata": "123",
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        payload2 = {
            "some_metadata": "456",
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-2")
        self.ingestor._extract_task(payload2, Lane.WINDOWS_CLI_1, "ASSIGN-2")
        task = self.cp.get_task("TASK-ASSIGN-2")
        self.assertIsNotNone(task)

    def test_C_different_canonical_payload_fails_closed(self):
        payload1 = {
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        payload2 = {
            "two_level_done": {
                "local_step_erledigt": True,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-3")
        with self.assertRaisesRegex(RuntimeError, "Conflict: Task TASK-ASSIGN-3 already exists with a different canonical payload"):
            self.ingestor._extract_task(payload2, Lane.WINDOWS_CLI_1, "ASSIGN-3")

    def test_D_terminal_mutation_rejected(self):
        payload1 = {
            "two_level_done": {
                "local_step_erledigt": True,
                "gesamtaufgabe_erledigt": True,
                "blocker": "NONE",
                "next_step": "DONE"
            }
        }
        payload2 = {
            "two_level_done": {
                "local_step_erledigt": True,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "DONE"
            }
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-4")
        with self.assertRaisesRegex(RuntimeError, "Terminal Mutation Rejected"):
            self.ingestor._extract_task(payload2, Lane.WINDOWS_CLI_1, "ASSIGN-4")

    def test_E_idempotent_replay_on_terminal_allowed(self):
        payload1 = {
            "two_level_done": {
                "local_step_erledigt": True,
                "gesamtaufgabe_erledigt": True,
                "blocker": "NONE",
                "next_step": "DONE"
            }
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-5")
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-5")
        task = self.cp.get_task("TASK-ASSIGN-5")
        self.assertEqual(task["status"], TaskStatus.COMPLETED.value)

    def test_F_original_task_unchanged_on_conflict(self):
        payload1 = {
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        payload2 = {
            "two_level_done": {
                "local_step_erledigt": True,
                "gesamtaufgabe_erledigt": True,
                "blocker": "NONE",
                "next_step": "DONE"
            }
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-6")
        try:
            self.ingestor._extract_task(payload2, Lane.WINDOWS_CLI_1, "ASSIGN-6")
        except RuntimeError:
            pass
        task = self.cp.get_task("TASK-ASSIGN-6")
        self.assertEqual(task["local_step_erledigt"], 0)

    def test_G_missing_canonical_fingerprint_in_db_handles_gracefully(self):
        payload1 = {
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        self.cp.upsert_task("TASK-ASSIGN-7", "ASSIGN-7", Lane.WINDOWS_CLI_1, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "CONTINUE"))
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-7")
        task = self.cp.get_task("TASK-ASSIGN-7")
        self.assertIsNotNone(task["canonical_fingerprint"])

    def test_H_different_assignments_do_not_conflict(self):
        payload1 = {
            "two_level_done": {
                "local_step_erledigt": False,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-8")
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-9")
        task1 = self.cp.get_task("TASK-ASSIGN-8")
        task2 = self.cp.get_task("TASK-ASSIGN-9")
        self.assertIsNotNone(task1)
        self.assertIsNotNone(task2)

    def test_I_failed_state_cannot_be_mutated(self):
        self.cp.upsert_task("TASK-ASSIGN-10", "ASSIGN-10", Lane.WINDOWS_CLI_1, TaskStatus.FAILED, TwoLevelDone(False, False, "NONE", "CONTINUE"), canonical_fingerprint="abc")
        payload = {
            "two_level_done": {
                "local_step_erledigt": True,
                "gesamtaufgabe_erledigt": False,
                "blocker": "NONE",
                "next_step": "CONTINUE"
            }
        }
        with self.assertRaisesRegex(RuntimeError, "Terminal Mutation Rejected"):
            self.ingestor._extract_task(payload, Lane.WINDOWS_CLI_1, "ASSIGN-10")

    def test_J_upsert_direct_conflict_behavior(self):
        self.cp.upsert_task("TASK-ASSIGN-11", "ASSIGN-11", Lane.WINDOWS_CLI_1, TaskStatus.RUNNING, TwoLevelDone(False, False, "NONE", "CONTINUE"), canonical_fingerprint="hash1")
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.cp.upsert_task("TASK-ASSIGN-11", "ASSIGN-11", Lane.WINDOWS_CLI_1, TaskStatus.RUNNING, TwoLevelDone(True, False, "NONE", "CONTINUE"), canonical_fingerprint="hash2")


    def test_K_same_task_different_assignment_rejected(self):
        payload1 = {
            "assignment_id": "ASSIGN-12",
            "windows_validation_request_id": "TASK-12",
            "local_step_erledigt": False,
            "gesamtaufgabe_erledigt": False,
            "two_level_done": {"local_step_erledigt": False, "gesamtaufgabe_erledigt": False, "blocker": "NONE", "next_step": "CONTINUE"}
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-12")
        
        payload2 = {
            "assignment_id": "ASSIGN-13", # Different assignment
            "windows_validation_request_id": "TASK-12", # Same task
            "local_step_erledigt": False,
            "gesamtaufgabe_erledigt": False,
            "two_level_done": {"local_step_erledigt": False, "gesamtaufgabe_erledigt": False, "blocker": "NONE", "next_step": "CONTINUE"}
        }
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.ingestor._extract_task(payload2, Lane.WINDOWS_CLI_1, "ASSIGN-13")

    def test_L_same_assignment_different_task_rejected(self):
        payload1 = {
            "assignment_id": "ASSIGN-14",
            "windows_validation_request_id": "TASK-14",
            "local_step_erledigt": False,
            "gesamtaufgabe_erledigt": False,
            "two_level_done": {"local_step_erledigt": False, "gesamtaufgabe_erledigt": False, "blocker": "NONE", "next_step": "CONTINUE"}
        }
        self.ingestor._extract_task(payload1, Lane.WINDOWS_CLI_1, "ASSIGN-14")
        
        payload2 = {
            "assignment_id": "ASSIGN-14", # Same assignment
            "windows_validation_request_id": "TASK-15", # Different task
            "local_step_erledigt": False,
            "gesamtaufgabe_erledigt": False,
            "two_level_done": {"local_step_erledigt": False, "gesamtaufgabe_erledigt": False, "blocker": "NONE", "next_step": "CONTINUE"}
        }
        with self.assertRaisesRegex(RuntimeError, "Conflict"):
            self.ingestor._extract_task(payload2, Lane.WINDOWS_CLI_1, "ASSIGN-14")

    def test_M_terminal_legacy_mutation_rejected(self):
        # Insert a legacy row (no fingerprint) directly
        now = "2026-09-15T00:00:00Z"
        with self.cp.get_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, assignment_id, origin_lane, status, local_step_erledigt, gesamtaufgabe_erledigt, blocker, next_step, active_agent, canonical_fingerprint, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("TASK-LEGACY", "ASSIGN-LEGACY", "WINDOWS_CLI_1", "COMPLETED", 1, 1, "NONE", "DONE", "CHIEF", None, now, now)
            )
            
        payload = {
            "assignment_id": "ASSIGN-LEGACY",
            "windows_validation_request_id": "TASK-LEGACY",
            "local_step_erledigt": True,
            "gesamtaufgabe_erledigt": True,
            "two_level_done": {"local_step_erledigt": True, "gesamtaufgabe_erledigt": True, "blocker": "NONE", "next_step": "DONE"}
        }
        with self.assertRaisesRegex(RuntimeError, "Terminal Legacy Mutation Rejected"):
            self.ingestor._extract_task(payload, Lane.WINDOWS_CLI_1, "ASSIGN-LEGACY")
            
    def test_N_deterministic_fallback_does_not_claim_success(self):
        from chief.coordinator import ChiefCoordinator
        coord = ChiefCoordinator(self.cp, self.handoffs_dir)
        # Create a mock dispatch
        dispatch_id = "DISP-TEST-123"
        self.cp.enqueue_dispatch(dispatch_id, Lane.WINDOWS_CLI_1, Host.WINDOWS, "ASSIGN-FALLBACK", "PROMPT", {}, Lane.WINDOWS_CLI_1)
        
        # Execute fallback
        res = coord.execute_deterministic_fallback(dispatch_id)
        
        # Check return dict
        self.assertFalse(res["success"])
        
        # Check output payload
        json_path = res["json_path"]
        import json
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        self.assertEqual(data["status"], "FAILED")
        self.assertFalse(data["local_step_erledigt"])
        self.assertFalse(data["two_level_done"]["local_step_erledigt"])
        self.assertEqual(data["two_level_done"]["blocker"], "PRIMARY_RUNNER_FAILED")
        self.assertNotIn("verified", data["evidence"].lower())
        self.assertNotIn("fulfilled", data["evidence"].lower())

if __name__ == "__main__":
    unittest.main()

