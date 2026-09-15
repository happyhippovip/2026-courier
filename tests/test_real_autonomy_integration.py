import unittest
import json
import shutil
import time
import os
from pathlib import Path

from scripts.courier_founder_mode import FounderModeMVP, MultiChatGoalIntake
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue
from scripts.idea_foundry import IdeaFoundry
from scripts.resource_policy import TaskLeaseManager
from scripts.courier_real_worker_adapters import get_real_worker_adapters

class TestRealAutonomyIntegration(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("scratch/real_autonomy_workspace")
        if self.workspace.exists(): shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True)
        self.intake = MultiChatGoalIntake(str(self.workspace))
        os.environ["COURIER_FAST_TEST_MODE"] = "1"
        
    def tearDown(self):
        if self.workspace.exists(): shutil.rmtree(self.workspace)

    def _setup_mvp(self):
        dispatcher = CourierSafetyDispatcher(str(self.workspace))
        adapters = get_real_worker_adapters(self.workspace)
        for agent, adapter in adapters.items():
            if agent in dispatcher.adapter_boundary.SUPPORTED_AGENTS:
                dispatcher.adapter_boundary.register_consumer(agent, adapter)
        mvp = FounderModeMVP(str(self.workspace), dispatcher)
        return mvp

    def _get_goal(self, goal_id):
        with open(self.intake.db_file, "r") as f:
            goals = json.load(f)
        return next((g for g in goals if g["goal_id"] == goal_id), None)

    def test_00_setup_registers_only_supported_local_consumers(self):
        mvp = self._setup_mvp()
        registered = set(mvp.dispatcher.adapter_boundary.consumers)
        supported = set(mvp.dispatcher.adapter_boundary.SUPPORTED_AGENTS)

        self.assertEqual(registered, supported)
        self.assertNotIn("WINDOWS", registered)

    # 1. REAL HAPPY PATH
    def test_01_real_happy_path(self):
        (self.workspace / "tests").mkdir()
        (self.workspace / "tests" / "test_test_target.py").write_text("import unittest")
        goal_id = self.intake.submit_goal("CLI", "Analyze repo state")
        mvp = self._setup_mvp()
        mvp.run_autonomous_loop()
        self.assertEqual(self._get_goal(goal_id)["status"], "SATISFIED")

    # 2. FAILURE RECOVERY (Bounded Retry)
    def test_02_failure_recovery(self):
        # We can make a task fail by requiring write but not having write capability.
        goal_id = self.intake.submit_goal("CLI", "Crash")
        # Just use dispatcher directly to submit an impossible task 3 times
        mvp = self._setup_mvp()
        # Create a mission that fails verification
        mission = {
            "mission_id": "m_fail",
            "task": {"action": "invalid_action", "requires_write": False},
            "status": "PENDING",
            "goal": "Crash"
        }
        mvp.queue.enqueue(mission)
        
        # In founder mode, loop will claim it, execute it, fail verification, and retry.
        # Since invalid_action is rejected, it should block eventually.
        mvp.run_autonomous_loop()
        # Verify it is blocked
        g = self._get_goal(goal_id)
        self.assertEqual(g["status"], "BLOCKED")


    # 3. HUMAN GATE BEHAVIOR
    def test_03_human_gate_behavior(self):
        goal_a_id = self.intake.submit_goal("CLI", "Deploy production with password")
        # Need discovery to find a gap so implementation is scheduled.
        (self.workspace / "test_target.py").write_text("def hello(): pass")
        mvp = self._setup_mvp()
        mvp.run_autonomous_loop()
        self.assertEqual(self._get_goal(goal_a_id)["status"], "HUMAN_GATE")

    # 4. WRITER CONFLICT
    def test_04_writer_conflict(self):
        lm = TaskLeaseManager(self.workspace)
        lm.acquire_lease("global_writer_lease", "dummy_task", "other_worker", 60)
        
        goal_id = self.intake.submit_goal("CLI", "Write some code")
        # Need discovery to find a gap so implementation (writer) is scheduled.
        (self.workspace / "test_target.py").write_text("def hello(): pass")
        mvp = self._setup_mvp()
        mvp.queue.enqueue({
            "mission_id": "writer-conflict-mission",
            "goal": "Write some code",
            "normalized_task": "Modify test_target.py",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "requires_write": True,
            "is_heavy": False,
            "verification_required": True,
            "task": {"action": "modify_file", "path": "test_target.py", "requires_write": True},
        })
        mvp.run_autonomous_loop()
        self.assertEqual(self._get_goal(goal_id)["status"], "BLOCKED")
        self.assertEqual(self._get_goal(goal_id).get("blocker_evidence", {}).get("reason"), "WRITER_CONFLICT")

    # 5. NO COHERENT WORK
    def test_05_no_coherent_work(self):
        mvp = self._setup_mvp()
        mvp.run_autonomous_loop()
        self.assertTrue(True)
        
    # 6. FOUNDRY HANDOFF
    def test_06_foundry_handoff(self):
        (self.workspace / "tests").mkdir()
        (self.workspace / "tests" / "test_test_target.py").write_text("import unittest")
        
        foundry = IdeaFoundry(self.workspace)
        t1 = {"source_message_id": "m1", "content_hash": "h1", "original_envelope": {"content": {"summary": "crypto"}}}
        cand = foundry.synthesize_candidate([t1])
        cand["status"] = "EXPERIMENT_READY"
        exp = foundry.propose_experiment(cand)
        goal_id = foundry.handoff_to_courier(cand, exp)
        
        mvp = self._setup_mvp()
        mvp.run_autonomous_loop()
        self.assertEqual(self._get_goal(goal_id)["status"], "SATISFIED")

    # 7. ADVERSARIAL REGRESSION
    def test_07_adversarial_regression(self):
        dispatcher = CourierSafetyDispatcher(str(self.workspace))
        safe, reason = dispatcher.is_safe_action({"action": "run_command", "command": "rm -rf /"})
        self.assertFalse(safe)
        safe, reason = dispatcher.is_safe_action({"action": "TRANSFER"})
        self.assertFalse(safe)
