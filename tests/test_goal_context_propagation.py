import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from scripts.courier_founder_mode import FounderModePlanner
from scripts.courier_real_worker_adapters import create_real_gemini_adapter

class TestGoalContextPropagation(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.ws = Path(self.td.name)
        
        self.goals_file = self.ws / "events" / "founder-mode" / "goals.json"
        self.goals_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.ws / "events" / "mission-queue" / "queue.json"
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.goals_data = [
            {"goal_id": "g1", "goal": "Goal Context Number One", "status": "PENDING"},
            {"goal_id": "g2", "goal": "Goal Context Number Two", "status": "PENDING"}
        ]
        self.goals_file.write_text(json.dumps(self.goals_data))
        
        self.planner = FounderModePlanner(workspace_dir=str(self.ws))

    def tearDown(self):
        self.td.cleanup()

    def test_context_propagation_and_no_bleed(self):
        # 1. Provide a completed discovery mission for g1
        discovery_result = {
            "task_type": "DISCOVERY",
            "verdict": "PASS",
            "finding": {
                "finding_id": "W1",
                "description": "Fix the thing",
                "evidence": "Log says X",
                "affected_files": [],
                "recommended_action": "Fix it",
                "verification_strategy": "Test it",
                "confidence": 0.95
            }
        }
        
        original_load = self.planner._load_result
        def mock_load_result(mission):
            return discovery_result
        self.planner._load_result = mock_load_result

        completed_mission = {
            "mission_id": "m1",
            "parent_mission_id": None,
            "goal_id": "g1",
            "status": "VERIFIED",
            "task": {"action": "discover_improvement_opportunities"}
        }
        
        goal_record = self.goals_data[0]
        next_missions = self.planner.discover_and_plan(goal_record, [completed_mission])
        self.assertEqual(len(next_missions), 1)
        impl_mission = next_missions[0]
        self.assertEqual(impl_mission["task"]["action"], "implement_bounded_improvement")
        
        # Check propagation from goal to mission
        self.assertEqual(impl_mission["task"]["goal_context"], "Goal Context Number One")
        self.assertNotIn("Goal Context Number Two", impl_mission["task"]["goal_context"])

        # 2. Check propagation from mission to adapter prompt
        # create_real_gemini_adapter returns an object with a dispatch method or is it a function?
        # Let's check how the adapter is returned.
        # Oh, it's a LocalConsumer with a process method? Let's assume it returns a worker function or an object with `process`.
        worker = create_real_gemini_adapter(repo_root=str(self.ws))
        envelope = {
            "mission_id": "m2",
            "task_id": "t2",
            "task_hash": "th",
            "worker_id": "w1",
            "target_agent": "GEMINI",
            "requires_write": True,
            "payload": impl_mission["task"]
        }

        with patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt") as mock_agy:
            mock_agy.return_value = (True, {"verdict": "PASS", "summary": "Did the thing", "changed_files": []})
            
            worker(envelope)
            
            self.assertTrue(mock_agy.called)
            prompt_sent = mock_agy.call_args.kwargs.get("prompt") if mock_agy.call_args.kwargs.get("prompt") else mock_agy.call_args.args[0]
            self.assertIn("GOAL CONTEXT: Goal Context Number One", prompt_sent)
            self.assertNotIn("Goal Context Number Two", prompt_sent)

if __name__ == "__main__":
    unittest.main()
