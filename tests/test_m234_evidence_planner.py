import unittest
import tempfile
from pathlib import Path
from typing import Any

from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_founder_mode import FounderModeMVP, MultiChatGoalIntake, ExperienceMemory, FounderModePlanner

class TestEvidencePlanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = Path(self.temp_dir.name)
        self.planner = FounderModePlanner(self.workspace_dir)
        self.goal = {"goal": "Reduce how much humans need to coordinate Courier."}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_malformed_evidence_fails_closed(self):
        # Missing keys in finding
        bad_result = {
            "result_data": {
                "task_type": "DISCOVERY",
                "finding": {"finding_id": "f1"} # Missing description, evidence, etc.
            }
        }
        missions = self.planner.discover_and_plan(self.goal, [bad_result])
        self.assertEqual(len(missions), 0)

    def test_generalization_a_queue(self):
        queue_result = {
            "result_data": {
                "task_type": "DISCOVERY",
                "finding": {
                    "finding_id": "FINDING-Q",
                    "description": "Queue issue",
                    "evidence": "Logs show queue starvation",
                    "affected_files": ["queue.py"],
                    "recommended_action": "Fix queue loop",
                    "verification_strategy": "Test queue",
                    "confidence": 0.9
                }
            }
        }
        missions = self.planner.discover_and_plan(self.goal, [queue_result])
        self.assertEqual(len(missions), 1)
        self.assertIn("FINDING-Q", missions[0]["normalized_task"])
        self.assertIn("Fix queue loop", missions[0]["normalized_task"])

    def test_generalization_b_lease(self):
        lease_result = {
            "result_data": {
                "task_type": "DISCOVERY",
                "finding": {
                    "finding_id": "FINDING-L",
                    "description": "Lease issue",
                    "evidence": "Logs show lease contention",
                    "affected_files": ["lease.py"],
                    "recommended_action": "Fix lease manager",
                    "verification_strategy": "Test leases",
                    "confidence": 0.95
                }
            }
        }
        missions = self.planner.discover_and_plan(self.goal, [lease_result])
        self.assertEqual(len(missions), 1)
        self.assertIn("FINDING-L", missions[0]["normalized_task"])
        self.assertIn("Fix lease manager", missions[0]["normalized_task"])

    def test_verification_from_actual_result(self):
        impl_result = {
            "result_data": {
                "task_type": "IMPLEMENTATION",
                "changed_files": ["scripts/courier_founder_mode.py", "tests/test_x.py"]
            }
        }
        missions = self.planner.discover_and_plan(self.goal, [impl_result])
        self.assertEqual(len(missions), 1)
        self.assertEqual(missions[0]["capability_required"], "repo verification")
        self.assertIn("scripts/courier_founder_mode.py", missions[0]["normalized_task"])
        self.assertIn("tests/test_x.py", missions[0]["normalized_task"])

    def test_goal_satisfaction_evidence_based(self):
        # Empty output is NOT success unless explicitly verified
        self.assertFalse(self.planner.evaluate_success(self.goal, {"mission": {"result_data": {}}}))

        verified_success = {
            "mission": {
                "result_data": {
                    "task_type": "VERIFICATION",
                    "acceptance_evidence": {"goal_satisfied": True}
                }
            }
        }
        self.assertTrue(self.planner.evaluate_success(self.goal, verified_success))

if __name__ == "__main__":
    unittest.main()
