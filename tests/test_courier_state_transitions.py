import unittest
from pathlib import Path
import tempfile
import uuid
from scripts.courier_founder_mode import MultiChatGoalIntake, FounderModeMVP
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue
from scripts.worker_availability import WorkerAvailabilityResolver

class MockDispatcher(CourierSafetyDispatcher):
    def __init__(self, workspace_dir, agent_available=False):
        super().__init__(workspace_dir)
        self.agent_available = agent_available
        self.router = type("MockRouter", (), {"select_agent": lambda self, req, pref: "GEMINI" if agent_available else None})()

    def process_next_mission(self, worker_id: str):
        if not self.agent_available:
            mission = self.mission_queue.claim_next(worker_id)
            if not mission:
                return None
            self.mission_queue.transition(mission["mission_id"], "BLOCKED", claimed_by=worker_id, result_reference="WORKER_UNAVAILABLE")
            return {"status": "BLOCKED", "mission_id": mission["mission_id"], "reason": "WORKER_UNAVAILABLE"}
        else:
            return super().process_next_mission(worker_id)

class TestCourierStateTransitions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = Path(self.temp_dir.name)
        self.intake = MultiChatGoalIntake(self.workspace_dir)
        self.queue = MissionQueue(self.workspace_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_blocked_propagates(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        dispatcher = MockDispatcher(self.workspace_dir, agent_available=False)
        founder = FounderModeMVP(self.workspace_dir, dispatcher)
        self.queue.enqueue({"mission_id": str(uuid.uuid4()), "goal": "test goal", "status": "PENDING", "capability_required": "impl", "requires_write": False})
        founder.run_autonomous_loop()
        goals = self.intake._read_no_lock()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["status"], "BLOCKED")
        self.assertIn("blocker_evidence", goals[0])

    def test_02_unchanged_evidence_no_retry(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        resolver = WorkerAvailabilityResolver()
        ev = resolver.resolve_gemini().to_dict()
        self.intake.set_status(goal_id, "BLOCKED", blocker_evidence={"worker_evidence": ev})
        self.assertIsNone(self.intake.pop_next_goal())

    def test_03_changed_evidence_one_retry(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        self.intake.set_status(goal_id, "BLOCKED", blocker_evidence={"worker_evidence": {"state": "DIFFERENT"}})
        goal = self.intake.pop_next_goal()
        self.assertIsNotNone(goal)
        self.assertEqual(goal["status"], "ACTIVE")
        self.assertIsNone(self.intake.pop_next_goal())

    def test_04_human_gate_sticky(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        self.intake.set_status(goal_id, "HUMAN_GATE")
        self.assertIsNone(self.intake.pop_next_goal())

    def test_05_live_active_goal_not_recovered(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        self.intake.set_status(goal_id, "ACTIVE")
        def _add_running(data):
            data["missions"] = data.get("missions", []) + [{"mission_id": str(uuid.uuid4()), "goal": "test goal", "status": "RUNNING", "capability_required": "impl", "requires_write": False}]
            return True
        self.queue._mutate(_add_running)
        self.assertIsNone(self.intake.pop_next_goal())

    def test_06_stale_active_recovers(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        self.intake.set_status(goal_id, "ACTIVE")
        def _add_blocked(data):
            data["missions"] = data.get("missions", []) + [{"mission_id": str(uuid.uuid4()), "goal": "test goal", "status": "BLOCKED", "result_reference": "WORKER_UNAVAILABLE", "capability_required": "impl", "requires_write": False}]
            return True
        self.queue._mutate(_add_blocked)
        self.intake.set_status(goal_id, "ACTIVE", blocker_evidence={"worker_evidence": {"state": "DIFFERENT"}})
        goal = self.intake.pop_next_goal()
        self.assertIsNotNone(goal)
        self.assertEqual(goal["status"], "ACTIVE")

    def test_07_repeated_start_no_duplicate(self):
        goal_id = self.intake.submit_goal("test", "test goal")
        dup_id = self.intake.submit_goal("test", "test goal")
        self.assertEqual(dup_id, goal_id)
        goals = self.intake._read_no_lock()
        self.assertEqual(len(goals), 1)

if __name__ == '__main__':
    unittest.main()
