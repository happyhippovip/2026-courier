import unittest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_real_worker_adapters import create_real_cli1_adapter, create_real_gemini_adapter

class TestNativeWriteContract(unittest.TestCase):
    def setUp(self):
        self.workspace_dir = Path("./tests/test_workspace_w")
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)
        self.workspace_dir.mkdir(parents=True)
        self.dispatcher = CourierSafetyDispatcher(self.workspace_dir)
        self.gemini_adapter = create_real_gemini_adapter(self.workspace_dir)
        self.dispatcher.adapter_boundary.register_consumer("GEMINI", self.gemini_adapter)

    def tearDown(self):
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)

    def test_w1_pass_without_effect_rejected(self):
        mission_id = "m-w1"
        task_hash = "thash-w1"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "requires_write": True,
            "task_hash": task_hash,
            "preferred_agent": "GEMINI",
            "task": {
                "action": "implement_bounded_improvement",
                "acceptance_criteria": {"file_exists": "new_file.txt"},
                "task_id": "tid1",
                "correlation_id": "corr1"
            }
        })
        
        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            mock_agy.return_value = (True, {
                "correlation_id": "corr1",
                "task_id": "tid1",
                "mission_id": mission_id,
                "task_hash": task_hash,
                "target_agent": "GEMINI",
                "verdict": "PASS",
                "summary": "Done"
            })
            res = self.dispatcher.process_next_mission("w1")
            
            print(res); self.assertEqual(res["status"], "FAILED")
            missions = self.dispatcher.mission_queue.read_all()
            self.assertEqual(missions[0]["result_reference"], "VERIFICATION_PASS_FAIL_CLOSED")

    def test_w2_implement_before_envelope(self):
        mission_id = "m-w2"
        task_hash = "thash-w2"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "requires_write": True,
            "task_hash": task_hash,
            "preferred_agent": "GEMINI",
            "task": {
                "action": "implement_bounded_improvement",
                "acceptance_criteria": {"file_exists": "new_file.txt"},
                "task_id": "tid1",
                "correlation_id": "corr1"
            }
        })
        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            mock_agy.return_value = (True, {
                "correlation_id": "corr1", "task_id": "tid1", "mission_id": mission_id,
                "task_hash": task_hash, "target_agent": "GEMINI", "verdict": "PASS", "summary": "Done"
            })
            self.dispatcher.process_next_mission("w1")
            prompt_called = mock_agy.call_args[1]["prompt"]
            self.assertIn("PHASE 1 (EXECUTION):", prompt_called)
            self.assertIn("PHASE 2 (RESULT ENVELOPE):", prompt_called)
            self.assertIn("ONLY AFTER you have successfully performed", prompt_called)

    def test_w3_read_only_no_write(self):
        mission_id = "m-w3"
        task_hash = "thash-w3"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "requires_write": False,
            "task_hash": task_hash,
            "preferred_agent": "GEMINI",
            "task": {
                "action": "discover_improvement_opportunities",
                "task_id": "tid1",
                "correlation_id": "corr1"
            }
        })
        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            mock_agy.return_value = (True, {
                "correlation_id": "corr1", "task_id": "tid1", "mission_id": mission_id,
                "task_hash": task_hash, "target_agent": "GEMINI", "verdict": "PASS", "summary": "Done"
            })
            self.dispatcher.process_next_mission("w1")
            prompt_called = mock_agy.call_args[1]["prompt"]
            self.assertIn("read-only discovery", prompt_called)
            self.assertNotIn("PHASE 1 (EXECUTION):", prompt_called)

    def test_w4_w5_w6_w7_identity_requirements(self):
        mission_id = "m-w4"
        task_hash = "thash-w4"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "requires_write": True,
            "task_hash": task_hash,
            "preferred_agent": "GEMINI",
            "task": {
                "action": "implement_bounded_improvement",
                "acceptance_criteria": {"file_exists": "new_file.txt"},
                "task_id": "tid1",
                "correlation_id": "corr1"
            }
        })
        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            mock_agy.return_value = (True, {
                "correlation_id": "corr1", "task_id": "tid1", "mission_id": "WRONG",
                "task_hash": task_hash, "target_agent": "GEMINI", "verdict": "PASS", "summary": "Done"
            })
            res = self.dispatcher.process_next_mission("w1")
            m = self.dispatcher.mission_queue.read_all()[0]
            self.assertEqual(m["status"], "FAILED") 

    def test_w9_w10_effect_and_freshness(self):
        mission_id = "m-w10"
        task_hash = "thash-w10"
        target_file = self.workspace_dir / "new_file.txt"
        
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "requires_write": True,
            "task_hash": task_hash,
            "preferred_agent": "GEMINI",
            "task": {
                "action": "implement_bounded_improvement",
                "acceptance_criteria": {"file_exists": "new_file.txt", "content_matches": "FRESH"},
                "task_id": "tid1",
                "correlation_id": "corr1"
            }
        })
        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            def side_effect(*args, **kwargs):
                target_file.write_text("FRESH")
                return (True, {
                    "correlation_id": "corr1", "task_id": "tid1", "mission_id": mission_id,
                    "task_hash": task_hash, "target_agent": "GEMINI", "verdict": "PASS", "summary": "Done"
                })
            mock_agy.side_effect = side_effect
            res = self.dispatcher.process_next_mission("w1")
            self.assertEqual(res["status"], "VERIFIED")

    def test_w11_human_gate_fail_closed(self):
        mission_id = "m-w11"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id, "status": "PENDING", "requires_write": True, "task_hash": "th", "preferred_agent": "GEMINI",
            "task": {"action": "implement_bounded_improvement", "acceptance_criteria": {"file_exists": "a"}, "task_id": "t", "correlation_id": "c"}
        })
        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            mock_agy.return_value = (False, {"verdict": "HUMAN_GATE", "error_type": "AUTHENTICATION_REQUIRED"})
            res = self.dispatcher.process_next_mission("w1")
            self.assertEqual(res["status"], "HUMAN_GATE")

if __name__ == "__main__":
    unittest.main()
