import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.courier_founder_mode import FounderModeMVP
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.worker_availability import WorkerState, AvailabilityEvidence

class MockResolver:
    def __init__(self, state=WorkerState.UNAVAILABLE, path=None):
        self.state = state
        self.path = path
    def resolve_gemini(self):
        return AvailabilityEvidence(
            worker="GEMINI", state=self.state,
            executable=self.path, resolution_method="MOCK", detail="mock"
        )

class TestRecoverySemantics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        self.dispatcher = CourierSafetyDispatcher(self.ws)
        self.fm = FounderModeMVP(self.ws, self.dispatcher)

    def tearDown(self):
        self.tmp.cleanup()

    def mock_process_next_mission(self, worker_id, *args, **kwargs):
        m = self.dispatcher.mission_queue.claim_next(worker_id)
        if not m: return {"status": "NO_PENDING_MISSION"}

        safe, reason = self.dispatcher.is_safe_action(m.get("task", {}))
        if not safe:
            self.dispatcher.mission_queue.transition(m["mission_id"], "BLOCKED", claimed_by=worker_id, result_reference=reason)
            return {"status": "BLOCKED", "reason": reason}

        selected = self.dispatcher.router.select_agent(m.get("capability_required"), m.get("preferred_agent"))
        if not selected:
            self.dispatcher.mission_queue.transition(m["mission_id"], "BLOCKED", claimed_by=worker_id, result_reference="WORKER_UNAVAILABLE")
            return {"status": "BLOCKED", "reason": "WORKER_UNAVAILABLE"}

        self.dispatcher.mission_queue.transition(m["mission_id"], "RUNNING")
        self.dispatcher.mission_queue.transition(m["mission_id"], "PENDING_VERIFY")
        self.dispatcher.mission_queue.transition(m["mission_id"], "VERIFIED")
        return {"status": "VERIFIED", "mission_id": m["mission_id"], "agent_dispatched": selected}

    def test_1_unavailable_unchanged_evidence_no_retry(self):
        self.fm.intake.submit_goal("chief", "Test", 10)
        self.fm.planner.discover_and_plan = lambda g, c: [{
            "goal": "Test", "normalized_task": "task", "capability_required": "implementation", "preferred_agent": "GEMINI", "task": {"prompt": "foo", "capability_request": "implementation"}
        }] if not c else []
        self.fm.planner.evaluate_success = lambda *args: False

        with patch("scripts.worker_availability.WorkerAvailabilityResolver", return_value=MockResolver(WorkerState.UNAVAILABLE)):
            with patch.object(self.dispatcher, "process_next_mission", self.mock_process_next_mission):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["blockers"], 1)

            self.fm.stats = {"autonomous_steps": 0, "cli1_tasks": 0, "google_tasks": 0, "human_gates": 0, "blockers": 0}
            with patch.object(self.dispatcher, "process_next_mission", self.mock_process_next_mission):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["autonomous_steps"], 0)

    def test_2_unavailable_to_available_exactly_one_retry(self):
        self.fm.intake.submit_goal("chief", "Test", 10)

        def mock_plan(g, c):
            if not c:
                return [{"goal": "Test", "normalized_task": "task1", "capability_required": "local repo analysis", "preferred_agent": "CLI1", "task": {"action": "discover_improvement_opportunities", "capability_request": "local repo analysis"}}]
            last = c[-1]
            if last["preferred_agent"] == "CLI1":
                return [{"goal": "Test", "normalized_task": "task2", "capability_required": "implementation", "preferred_agent": "GEMINI", "task": {"prompt": "foo", "capability_request": "implementation"}}]
            return []

        self.fm.planner.discover_and_plan = mock_plan
        self.fm.planner.evaluate_success = lambda *args: False

        with patch("scripts.worker_availability.WorkerAvailabilityResolver", return_value=MockResolver(WorkerState.UNAVAILABLE)):
            with patch.object(self.dispatcher, "process_next_mission", self.mock_process_next_mission):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["blockers"], 1)
            self.assertEqual(self.fm.stats["autonomous_steps"], 2) # CLI1 and GEMINI ran

        with patch("scripts.worker_availability.WorkerAvailabilityResolver", return_value=MockResolver(WorkerState.AVAILABLE, "/path/to/agy")):
            self.fm.stats = {"autonomous_steps": 0, "cli1_tasks": 0, "google_tasks": 0, "human_gates": 0, "blockers": 0}
            with patch.object(self.dispatcher, "process_next_mission", self.mock_process_next_mission):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["autonomous_steps"], 1) # GEMINI ran once
            self.assertEqual(self.fm.stats["google_tasks"], 1)


    pass
    pass

    def test_3_repeated_start_unchanged_available_evidence_no_duplicate_retry(self):
        self.fm.intake.submit_goal("chief", "Test", 10)
        self.fm.planner.discover_and_plan = lambda g, c: [{
            "goal": "Test", "normalized_task": "task", "capability_required": "implementation", "preferred_agent": "GEMINI", "task": {"prompt": "foo", "capability_request": "implementation"}
        }] if not c else []
        self.fm.planner.evaluate_success = lambda *args: False

        with patch("scripts.worker_availability.WorkerAvailabilityResolver", return_value=MockResolver(WorkerState.AVAILABLE, "/agy")):
            with patch.object(self.dispatcher, "process_next_mission", self.mock_process_next_mission):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["autonomous_steps"], 1)

            self.fm.stats = {"autonomous_steps": 0, "cli1_tasks": 0, "google_tasks": 0, "human_gates": 0, "blockers": 0}
            with patch.object(self.dispatcher, "process_next_mission", self.mock_process_next_mission):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["autonomous_steps"], 0)

    def test_4_human_gate_unaffected_by_availability_changes(self):
        goal_id = self.fm.intake.submit_goal("chief", "Test", 10)

        def mock_process_hg(worker_id, *args, **kwargs):
            m = self.dispatcher.mission_queue.claim_next(worker_id)
            if not m: return {"status": "NO_PENDING_MISSION"}
            self.dispatcher.mission_queue.transition(m["mission_id"], "HUMAN_GATE", claimed_by=worker_id, result_reference="Required")
            return {"status": "HUMAN_GATE", "reason": "Required"}

        self.fm.planner.discover_and_plan = lambda g, c: [{
            "goal": "Test", "normalized_task": "task", "capability_required": "implementation", "preferred_agent": "GEMINI", "task": {"prompt": "foo", "capability_request": "implementation"}
        }] if not c else []
        self.fm.planner.evaluate_success = lambda *args: False

        with patch("scripts.worker_availability.WorkerAvailabilityResolver", return_value=MockResolver(WorkerState.UNAVAILABLE)):
            with patch.object(self.dispatcher, "process_next_mission", mock_process_hg):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["human_gates"], 1)

        with patch("scripts.worker_availability.WorkerAvailabilityResolver", return_value=MockResolver(WorkerState.AVAILABLE, "/agy")):
            self.fm.stats = {"autonomous_steps": 0, "cli1_tasks": 0, "google_tasks": 0, "human_gates": 0, "blockers": 0}
            with patch.object(self.dispatcher, "process_next_mission", mock_process_hg):
                self.fm.run_autonomous_loop()
            self.assertEqual(self.fm.stats["autonomous_steps"], 0) # Still blocked by HUMAN_GATE
            self.assertEqual(self.fm.stats["human_gates"], 0)

    def test_5_duplicate_goal_submission_cannot_bypass_human_gate(self):
        goal_id = self.fm.intake.submit_goal("chief", "Test", 10)

        def mock_process_hg(worker_id, *args, **kwargs):
            m = self.dispatcher.mission_queue.claim_next(worker_id)
            if not m: return {"status": "NO_PENDING_MISSION"}
            self.dispatcher.mission_queue.transition(m["mission_id"], "HUMAN_GATE", claimed_by=worker_id, result_reference="Required")
            return {"status": "HUMAN_GATE", "reason": "Required"}

        self.fm.planner.discover_and_plan = lambda g, c: [{
            "goal": "Test", "normalized_task": "task", "capability_required": "implementation", "preferred_agent": "GEMINI", "task": {"prompt": "foo", "capability_request": "implementation"}
        }] if not c else []
        self.fm.planner.evaluate_success = lambda *args: False

        with patch.object(self.dispatcher, "process_next_mission", mock_process_hg):
            self.fm.run_autonomous_loop()

        self.fm.intake.submit_goal("chief", "Test", 10)

        self.fm.stats = {"autonomous_steps": 0, "cli1_tasks": 0, "google_tasks": 0, "human_gates": 0, "blockers": 0}
        with patch.object(self.dispatcher, "process_next_mission", mock_process_hg):
            self.fm.run_autonomous_loop()
        self.assertEqual(self.fm.stats["autonomous_steps"], 0) # Still HUMAN_GATE

    pass
    pass

if __name__ == '__main__':
    unittest.main()
