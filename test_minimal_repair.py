import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from chief.coordinator import ChiefCoordinator
from chief.scheduled_cycle import execute_windows_validation_cycle
from chief.control_plane import ControlPlane
from chief.types import TaskStatus, Lane, Host, TwoLevelDone

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

if __name__ == "__main__":
    unittest.main()
