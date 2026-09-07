import unittest
from scripts.courier_founder_mode import FounderModePlanner

class TestTerminalSatisfactionRepair(unittest.TestCase):
    def setUp(self):
        self.planner = FounderModePlanner("/tmp/workspace")
        self.goal_record = {"goal_id": "g-123", "goal": "Fix the thing"}
        
        self.base_mission = {
            "mission_id": "m-1",
            "goal": "Fix the thing",
            "task_hash": "hash-abc"
        }
        
        self.base_result = {
            "task_type": "DISCOVERY",
            "task_hash": "hash-abc",
            "payload": {
                "verdict": "PASS"
            },
            "finding": {
                "finding_id": "SATISFIED",
                "description": "verified and intact",
                "affected_files": []
            }
        }

    def test_current_goal_current_fingerprint_all_criteria_satisfied(self):
        # SATISFIED directly -> no implementation mission queued
        is_sat = self.planner.is_strictly_satisfied(self.goal_record, self.base_mission, self.base_result)
        self.assertTrue(is_sat)
        
        # Test discover_and_plan returns [] when satisfied
        mock_completed = [self.base_mission]
        # We need to mock _load_result to return base_result
        self.planner._load_result = lambda m: self.base_result
        next_missions = self.planner.discover_and_plan(self.goal_record, mock_completed)
        self.assertEqual(len(next_missions), 0)

    def test_same_evidence_different_goal_id(self):
        # same evidence but different goal text/id -> NOT SATISFIED
        bad_mission = dict(self.base_mission, goal="Fix something else")
        is_sat = self.planner.is_strictly_satisfied(self.goal_record, bad_mission, self.base_result)
        self.assertFalse(is_sat)

    def test_same_goal_stale_fingerprint(self):
        # same goal but stale/different fingerprint -> NOT SATISFIED
        bad_result = dict(self.base_result, task_hash="hash-stale")
        is_sat = self.planner.is_strictly_satisfied(self.goal_record, self.base_mission, bad_result)
        self.assertFalse(is_sat)

    def test_missing_acceptance_criterion(self):
        # missing acceptance criterion -> NOT SATISFIED
        bad_result = dict(self.base_result)
        bad_result["finding"] = {
            "finding_id": "GENERAL_IMPROVEMENT",
            "description": "missing intact",
            "affected_files": []
        }
        is_sat = self.planner.is_strictly_satisfied(self.goal_record, self.base_mission, bad_result)
        self.assertFalse(is_sat)

    def test_unresolved_blocker(self):
        # unresolved blocker -> NOT SATISFIED
        bad_result = dict(self.base_result)
        bad_result["payload"] = {"verdict": "BLOCKED"}
        is_sat = self.planner.is_strictly_satisfied(self.goal_record, self.base_mission, bad_result)
        self.assertFalse(is_sat)

    def test_human_gate(self):
        # human/safety/external gate -> NOT SATISFIED
        bad_result = dict(self.base_result)
        bad_result["payload"] = {"verdict": "HUMAN_GATE"}
        is_sat = self.planner.is_strictly_satisfied(self.goal_record, self.base_mission, bad_result)
        self.assertFalse(is_sat)

    def test_discovery_says_implementation_required(self):
        # discovery says implementation required -> implementation still queues normally
        req_result = dict(self.base_result)
        req_result["finding"] = {
            "finding_id": "GENERAL_IMPROVEMENT",
            "description": "Work remains",
            "evidence": "some ev", "affected_files": ["file.py"],
            "recommended_action": "Fix weakness",
            "verification_strategy": "run tests",
            "confidence": 0.9
        }
        self.planner._load_result = lambda m: req_result
        next_missions = self.planner.discover_and_plan(self.goal_record, [self.base_mission])
        self.assertEqual(len(next_missions), 1)
        self.assertEqual(next_missions[0]["task"]["action"], "implement_bounded_improvement")

if __name__ == '__main__':
    unittest.main()
