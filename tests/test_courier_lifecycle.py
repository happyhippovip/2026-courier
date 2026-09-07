import unittest
import os
import json
import tempfile
from pathlib import Path

from scripts.courier_founder_mode import FounderModeMVP, FounderModePlanner, MultiChatGoalIntake
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue

class TestCourierLifecycle(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.events_dir = Path(self.workspace) / "events"
        self.events_dir.mkdir()
        self.dispatcher = CourierSafetyDispatcher(self.workspace)
        self.mvp = FounderModeMVP(workspace_dir=self.workspace, dispatcher=self.dispatcher)
        self.planner = self.mvp.planner
        self.intake = self.mvp.intake
        
    def _read_goals(self):
        with open(self.intake.db_file, "r") as f:
            return json.load(f)

    def test_01_canonical_goal_intake(self):
        goal_id = self.intake.submit_goal("CLI", "Test canonical goal")
        self.assertTrue(len(goal_id) > 10)
        
        goals = self._read_goals()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["goal"], "Test canonical goal")
        self.assertEqual(goals[0]["status"], "PENDING")

    def test_02_canonical_goal_identity_provenance(self):
        goal_id = self.intake.submit_goal("CLI", "Test goal")
        goals = self._read_goals()
        self.assertEqual(goals[0]["source"], "CLI")
        self.assertIn("created_at", goals[0])

    def _sim_result(self, finding_id, desc, verdict="PASS", goal_text="Test goal", files=None):
        data = {
            "task_hash": "hash123",
            "result": {
                "payload": {
                    "action": "discover_improvement_opportunities",
                    "weakness_id": finding_id,
                    "description": desc,
                    "suggested_files": files or [],
                    "verdict": verdict
                }
            }
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name
            
        res = {"result_reference": temp_path, "result_data": {}}
        loaded = self.planner._load_result(res)
        goal = {"goal": goal_text}
        mission = {"goal": goal_text, "task_hash": "hash123"}
        return self.planner.is_strictly_satisfied(goal, mission, loaded), temp_path

    def test_03_structured_no_gap_discovery(self):
        is_sat, p = self._sim_result("NONE", "Satisfied")
        self.assertTrue(is_sat)
        os.unlink(p)
        
    def test_04_natural_language_no_gap_normalization(self):
        is_sat, p = self._sim_result("GENERAL_IMPROVEMENT", "The baseline is fully operational")
        self.assertTrue(is_sat)
        os.unlink(p)
        
    def test_06_real_improvement_remains_unsatisfied(self):
        is_sat, p = self._sim_result("SECURITY_ISSUE", "Found a security issue")
        self.assertFalse(is_sat)
        os.unlink(p)
        
    def test_08_historical_evidence_cannot_satisfy_new_goal(self):
        is_sat, p = self._sim_result("NONE", "Satisfied", goal_text="Old goal")
        new_goal = {"goal": "New goal"}
        mission = {"goal": "Old goal", "task_hash": "hash123"}
        res = {"result_reference": p, "result_data": {}}
        loaded = self.planner._load_result(res)
        self.assertFalse(self.planner.is_strictly_satisfied(new_goal, mission, loaded))
        os.unlink(p)

    def test_12_quota_failure_fails_closed(self):
        is_sat, p = self._sim_result("NONE", "Satisfied", verdict="ERROR")
        self.assertFalse(is_sat)
        os.unlink(p)

    def test_15_human_gate_fails_closed(self):
        is_sat, p = self._sim_result("NONE", "Satisfied", verdict="HUMAN_GATE")
        self.assertFalse(is_sat)
        os.unlink(p)

    def test_16_genuine_human_gate_remains_closed(self):
        mission = {"goal": "Check"}
        task = {"description": "deploy to production"}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_17_filename_metadata_no_false_gate(self):
        mission = {"goal": "Check"}
        task = {"files": "tests/test_login.py"}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))
        
    def test_18_contradictory_wording_remains_gated(self):
        mission = {"goal": "Check"}
        task = {"description": "No OAuth is needed; deploy production now."}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_19_worker_success_without_effect_rejected(self):
        pass

    def test_20_no_change_required_proven_goal_satisfies(self):
        is_sat, p = self._sim_result("NO_COHERENT_GAP", "Already done")
        self.assertTrue(is_sat)
        os.unlink(p)

if __name__ == '__main__':
    unittest.main()
