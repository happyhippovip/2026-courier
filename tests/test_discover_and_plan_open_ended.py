import unittest
from scripts.courier_founder_mode import FounderModePlanner

class TestDiscoverAndPlanOpenEnded(unittest.TestCase):
    def test_open_ended_goal_implementation_mission_has_criteria(self):
        planner = FounderModePlanner("/tmp/dummy")
        
        goal_record = {"goal": "Build a new feature without specific file regex."}
        completed_missions = ["mission_1"]
        
        def mock_load_result(mid):
            return {
                "task_type": "DISCOVERY",
                "finding": {
                    "finding_id": "IMPROVEMENT_1",
                    "description": "desc",
                    "evidence": "ev",
                    "affected_files": ["new_file.py"],
                    "recommended_action": "Build it",
                    "verification_strategy": "run_tests",
                    "confidence": 0.9
                }
            }
        planner._load_result = mock_load_result
        
        plans = planner.discover_and_plan(goal_record, completed_missions)
        self.assertEqual(len(plans), 1)
        plan = plans[0]
        self.assertEqual(plan["capability_required"], "implementation")
        self.assertNotEqual(plan["task"]["acceptance_criteria"], {})
        self.assertEqual(plan["task"]["acceptance_criteria"]["finding_id"], "IMPROVEMENT_1")

if __name__ == '__main__':
    unittest.main()
