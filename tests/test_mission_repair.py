import unittest
import tempfile
from pathlib import Path
from scripts.courier_founder_mode import FounderModePlanner
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher

class MockBoundary:
    def __init__(self, ws):
        self.ws = ws
        self.events_dir = ws / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
    def dispatch(self, target, envelope, adapters):
        if envelope.requires_write:
            (self.ws / "canary.txt").write_text("hello")
        return {"status": "DISPATCH_OK", "result_path": "test", "result": {
            "mission_id": envelope.mission_id, "capability_required": "implementation",
            "task_hash": envelope.task_hash, "verdict": "PASS", "worker_agent": "GEMINI",
            "status": "COMPLETED", "result_fingerprint": "123"
        }}

class TestMissionRepair(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.p = FounderModePlanner(workspace_dir=self.td.name)
        self.goal = {"goal_id": "g1", "goal": "Create a file named canary.txt containing exactly: hello"}
        
        # mock load for discovery
        self.original_load = self.p._load_result
        def fake_load(mission):
            if mission.get("mission_id") == "disc_1":
                return {
                    "task_type": "DISCOVERY",
                    "finding": {
                        "finding_id": "F1",
                        "description": "test",
                        "evidence": "test",
                        "affected_files": ["canary.txt"],
                        "recommended_action": "test",
                        "verification_strategy": "test",
                        "confidence": 0.9
                    }
                }
            return {}
        self.p._load_result = fake_load

        self.disc_missions = self.p.discover_and_plan(self.goal)
        self.completed_disc = self.disc_missions[0]
        self.completed_disc["mission_id"] = "disc_1"
        self.completed_disc["status"] = "VERIFIED"
        self.completed_disc["result_reference"] = "mock_disc"
        
        self.impl_missions = self.p.discover_and_plan(self.goal, [self.completed_disc])
        if self.impl_missions:
            self.impl_mission = self.impl_missions[0]
            self.impl_mission["mission_id"] = "impl_1"

    def tearDown(self):
        self.p._load_result = self.original_load
        self.td.cleanup()

    def test_s1_discovery_requires_write_false(self):
        self.assertFalse(self.disc_missions[0].get("requires_write"))

    def test_s2_discovery_no_artifact_criteria(self):
        self.assertFalse(self.disc_missions[0].get("task", {}).get("acceptance_criteria"))

    def test_s3_emits_separate_implementation_mission(self):
        self.assertEqual(len(self.impl_missions), 1)

    def test_s4_implementation_mission_requires_write_true(self):
        self.assertTrue(self.impl_mission.get("requires_write"))

    def test_s5_implementation_task_requires_write_true(self):
        self.assertTrue(self.impl_mission.get("task", {}).get("requires_write"))

    def test_s6_implementation_worker_is_gemini(self):
        self.assertEqual(self.impl_mission.get("preferred_agent"), "GEMINI")

    def test_s7_carries_file_exists_criteria(self):
        criteria = self.impl_mission.get("task", {}).get("acceptance_criteria", {})
        self.assertEqual(criteria.get("file_exists"), "canary.txt")

    def test_s8_carries_content_matches_criteria(self):
        criteria = self.impl_mission.get("task", {}).get("acceptance_criteria", {})
        self.assertEqual(criteria.get("content_matches"), "hello")

    def test_s9_implementation_pass_without_verified_state_fails(self):
        self.impl_mission["status"] = "COMPLETED"
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, self.impl_mission]))

    def test_s10_implementation_pending_fails(self):
        self.impl_mission["status"] = "PENDING"
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, self.impl_mission]))

    def test_s11_implementation_with_requires_write_false_fails_closed(self):
        bad_impl = self.impl_mission.copy()
        bad_impl["status"] = "VERIFIED"
        bad_impl["requires_write"] = False
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, bad_impl]))

    def test_s12_implementation_with_empty_criteria_fails_closed(self):
        bad_impl = self.impl_mission.copy()
        bad_impl["status"] = "VERIFIED"
        bad_impl["task"] = bad_impl["task"].copy()
        bad_impl["task"]["acceptance_criteria"] = {}
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, bad_impl]))

    def test_s13_verified_effect_reaches_verified_and_satisfied(self):
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        res = dispatcher.process_next_mission("GEMINI")
        self.assertEqual(res.get("status"), "VERIFIED")

    def test_s14_verify_real_production_logic(self):
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        res = dispatcher.process_next_mission("GEMINI")
        
        # In production, FounderModePlanner receives the updated mission from the queue.
        # We must fetch it from the queue so it has the enqueue() task mutations.
        missions = dispatcher.mission_queue.read_all()
        updated_impl = [m for m in missions if m["mission_id"] == "impl_1"][0]
        
        self.assertTrue(self.p.evaluate_success(self.goal, {}, [self.completed_disc, updated_impl]))

    def test_s15_discovery_verification_pass_alone_cannot_satisfy(self):
        def fake_load2(mission):
            if mission.get("mission_id") == "ver_1":
                return {"task_type": "VERIFICATION", "acceptance_evidence": {"goal_satisfied": True}}
            return self.original_load(mission)
        self.p._load_result = fake_load2
        
        ver_mission = {"mission_id": "ver_1", "task": {"capability_request": "repo verification"}}
        ver_mission["mission_id"] = "ver_1"
        ver_mission["status"] = "VERIFIED"
        
        # It should fail because the implementation mission is NOT verified.
        self.assertFalse(self.p.evaluate_success(self.goal, {"mission": ver_mission}, [self.completed_disc, ver_mission]))



    def test_r1_direct_verified_rejected(self):
        updated_impl = self.impl_mission.copy()
        updated_impl["status"] = "VERIFIED"
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, updated_impl]))

    def test_r2_foreign_mission_rejected(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        from pathlib import Path
        from tests.test_mission_repair import MockBoundary
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        dispatcher.process_next_mission("GEMINI")
        
        missions = dispatcher.mission_queue.read_all()
        updated_impl = [m for m in missions if m["mission_id"] == "impl_1"][0]
        updated_impl["mission_id"] = "foreign_mission_id"
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, updated_impl]))

    def test_r3_stale_execution_rejected(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        from pathlib import Path
        from tests.test_mission_repair import MockBoundary
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        dispatcher.process_next_mission("GEMINI")
        
        missions = dispatcher.mission_queue.read_all()
        updated_impl = [m for m in missions if m["mission_id"] == "impl_1"][0]
        updated_impl["mission_id"] = "stale_execution_mission"
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, updated_impl]))

    def test_r4_wrong_worker_result_rejected(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        from pathlib import Path
        from tests.test_mission_repair import MockBoundary
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        dispatcher.process_next_mission("GEMINI")
        
        missions = dispatcher.mission_queue.read_all()
        updated_impl = [m for m in missions if m["mission_id"] == "impl_1"][0]
        updated_impl["claimed_by"] = "wrong_worker"
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, updated_impl]))

    def test_r5_current_canonical_proof_accepted(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        from pathlib import Path
        from tests.test_mission_repair import MockBoundary
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        dispatcher.process_next_mission("GEMINI")
        
        missions = dispatcher.mission_queue.read_all()
        updated_impl = [m for m in missions if m["mission_id"] == "impl_1"][0]
        self.assertTrue(self.p.evaluate_success(self.goal, {}, [self.completed_disc, updated_impl]))

    def test_r6_same_hash_replay_rejected(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        from pathlib import Path
        from tests.test_mission_repair import MockBoundary
        dispatcher = CourierSafetyDispatcher(workspace_dir=self.td.name, adapter_boundary=MockBoundary(Path(self.td.name)))
        impl_copy = self.impl_mission.copy()
        impl_copy["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(impl_copy)
        dispatcher.process_next_mission("GEMINI")
        
        new_impl = self.impl_mission.copy()
        new_impl["mission_id"] = "new_replay_mission"
        new_impl["status"] = "PENDING"
        dispatcher.mission_queue.enqueue(new_impl)
        
        missions = dispatcher.mission_queue.read_all()
        unexecuted_new_impl = [m for m in missions if m["mission_id"] == "new_replay_mission"][0]
        unexecuted_new_impl["status"] = "VERIFIED"
        
        self.assertFalse(self.p.evaluate_success(self.goal, {}, [self.completed_disc, unexecuted_new_impl]))

if __name__ == '__main__':
    unittest.main()

    def test_g1_discovery_mission_never_gated(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "login to oauth", "normalized_task": "discover"}
        task = {"action": "discover_improvement_opportunities"}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g2_implementation_with_genuine_gate(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "login to oauth", "normalized_task": "impl"}
        task = {"action": "implement_changes"}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g3_implementation_with_discovery_context_not_gated(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "fix bug", "normalized_task": "impl"}
        task = {"action": "implement_changes", "context": "No oauth login required"}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g4_implementation_with_negated_goal(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "no login required", "normalized_task": "impl"}
        task = {"action": "implement_changes"}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g5_implementation_with_publish_goal(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "publish the code", "normalized_task": "impl"}
        task = {"action": "implement_changes"}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g6_implementation_with_safe_action(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "fix bug", "normalized_task": "impl"}
        task = {"action": "write_file", "files": ["src/main.py"]}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g7_implementation_with_spend_goal(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "real spend 100", "normalized_task": "impl"}
        task = {"action": "implement_changes"}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g8_implementation_with_negated_spend(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "without real spend", "normalized_task": "impl"}
        task = {"action": "implement_changes"}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g9_implementation_with_publication_context(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "write tests", "normalized_task": "impl"}
        task = {"action": "implement_changes", "context": "this is for publication"}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission, task))

    def test_g10_implementation_with_explicit_human_gate(self):
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        mission = {"goal": "write tests", "normalized_task": "impl"}
        task = {"action": "implement_changes", "human_gate_required": True}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission, task))
