import unittest
import tempfile
from pathlib import Path
from typing import Any, Optional

from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, TaskEnvelope
from scripts.courier_founder_mode import FounderModeMVP, MultiChatGoalIntake, ExperienceMemory

class DummyConsumer:
    def __call__(self, task_spec: dict[str, Any], envelope: TaskEnvelope) -> dict[str, Any]:
        return {"status": "SUCCESS", "message": "Executed dummy task"}

class MockDispatcher(CourierSafetyDispatcher):
    def __init__(self, workspace_dir):
        super().__init__(workspace_dir)
        # Mock process_next_mission for testing the autonomous loop
        from scripts.courier_safety_dispatcher import MissionQueue, DynamicAgentRouter
        self.q = MissionQueue(workspace_dir)
        self.router = DynamicAgentRouter()

    def process_next_mission(self, worker_id: str):
        mission = self.q.claim_next(worker_id)
        if not mission:
            return None

        capability = mission["capability_required"]
        # Correct routing: implementation -> GEMINI, everything else -> CLI1
        if "implementation" in capability:
            agent = "GEMINI"
        else:
            agent = "CLI1"

        self.q.transition(mission["mission_id"], "RUNNING")
        self.q.transition(mission["mission_id"], "PENDING_VERIFY")

        # Feed evidence to satisfy the new planner
        if "repo analysis" in capability:
            result_data = {
                "task_type": "DISCOVERY",
                "finding": {
                    "finding_id": "F-01",
                    "description": "desc",
                    "evidence": "ev",
                    "affected_files": ["f"],
                    "recommended_action": "do",
                    "verification_strategy": "test",
                    "confidence": 1.0
                }
            }
        elif "implementation" in capability:
            result_data = {
                "task_type": "IMPLEMENTATION",
                "changed_files": ["f"]
            }
        else:
            result_data = {
                "task_type": "VERIFICATION",
                "acceptance_evidence": {"goal_satisfied": True}
            }

        self.q.transition(mission["mission_id"], "VERIFIED", result_data=result_data)
        return {"status": "PASS", "mission_id": mission["mission_id"], "agent_dispatched": agent, "mission": {"normalized_task": mission["normalized_task"], "result_data": result_data}}

class TestFounderModeMVP(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = Path(self.temp_dir.name)

        # Setup DBs
        self.intake = MultiChatGoalIntake(self.workspace_dir)
        self.memory = ExperienceMemory(self.workspace_dir)
        self.dispatcher = MockDispatcher(self.workspace_dir)
        self.founder = FounderModeMVP(self.workspace_dir, self.dispatcher)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_autonomous_loop(self):
        # 1. Human Goal
        goal_id = self.intake.submit_goal(
            source="user_chat",
            goal="Improve Courier so humans need to coordinate agents less."
        )

        # 2. Run Autonomous Loop
        self.founder.run_autonomous_loop()

        # 3. Assertions
        goals = self.intake._read_no_lock()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["status"], "SATISFIED")

        lessons = self.memory._read()
        self.assertEqual(len(lessons), 3) # 3 verified missions

        self.assertEqual(self.founder.stats["autonomous_steps"], 3)
        self.assertEqual(self.founder.stats["cli1_tasks"], 2)
        self.assertEqual(self.founder.stats["google_tasks"], 1)

if __name__ == "__main__":
    unittest.main()
