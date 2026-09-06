import unittest
import os
import json
from pathlib import Path
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, canonical_task_hash

class TestVerifyRoutingIdentity(unittest.TestCase):
    def setUp(self):
        self.ws = Path("/tmp/courier_test_verify_routing").resolve()
        self.ws.mkdir(parents=True, exist_ok=True)
        self.dispatcher = CourierSafetyDispatcher(self.ws)
        self.dispatcher.router.worker_status["GEMINI"] = "AVAILABLE"
        self.dispatcher.router.worker_status["CLI1"] = "AVAILABLE"
        
        self.verify_task = {
            "action": "verify_improvement_tests",
            "capability_request": "repo verification",
            "preferred_agent": "GEMINI"
        }
        
    def test_r1_compatible_verify_routing(self):
        target = self.dispatcher.evaluate_routing("repo verification", "GEMINI")
        self.assertEqual(target, "CLI1", "Should route to CLI1 because GEMINI lacks capability")
        
    def test_r2_r5_cli1_authorized_verify_accepted(self):
        # CLI1 selected, CLI1 executes
        res = self.dispatcher.canonical_validate_result("m1", self.verify_task, {
            "mission_id": "m1",
            "task_hash": canonical_task_hash(self.verify_task),
            "status": "COMPLETED",
            "result_fingerprint": "xyz",
            "target_agent": "CLI1"
        }, dispatched_route="CLI1")
        self.assertTrue(res, "CLI1 execution should be accepted if dispatched")

    def test_r3_foreign_worker_rejected(self):
        # CLI1 selected, but CODEX executes
        res = self.dispatcher.canonical_validate_result("m1", self.verify_task, {
            "mission_id": "m1",
            "task_hash": canonical_task_hash(self.verify_task),
            "status": "COMPLETED",
            "result_fingerprint": "xyz",
            "target_agent": "CODEX"
        }, dispatched_route="CLI1")
        self.assertFalse(res, "Foreign worker should be rejected")

    def test_r4_preference_does_not_weaken_identity(self):
        # GEMINI preferred, CLI1 selected, GEMINI executes anyway! (Wait, if CLI1 is selected, GEMINI executing is a foreign worker)
        res = self.dispatcher.canonical_validate_result("m1", self.verify_task, {
            "mission_id": "m1",
            "task_hash": canonical_task_hash(self.verify_task),
            "status": "COMPLETED",
            "result_fingerprint": "xyz",
            "target_agent": "GEMINI"
        }, dispatched_route="CLI1")
        self.assertFalse(res, "GEMINI execution should be rejected if CLI1 was dispatched, even if GEMINI was preferred")

    def test_r6_task_hash_mismatch(self):
        res = self.dispatcher.canonical_validate_result("m1", self.verify_task, {
            "mission_id": "m1",
            "task_hash": "wrong_hash",
            "status": "COMPLETED",
            "result_fingerprint": "xyz",
            "target_agent": "CLI1"
        }, dispatched_route="CLI1")
        self.assertFalse(res)

    def test_r7_mission_id_mismatch(self):
        res = self.dispatcher.canonical_validate_result("m1", self.verify_task, {
            "mission_id": "m2",
            "task_hash": canonical_task_hash(self.verify_task),
            "status": "COMPLETED",
            "result_fingerprint": "xyz",
            "target_agent": "CLI1"
        }, dispatched_route="CLI1")
        self.assertFalse(res)
        
    def test_r8_worker_target_mismatch(self):
        # Dispatched to CLI1, but result envelope is missing target_agent
        res = self.dispatcher.canonical_validate_result("m1", self.verify_task, {
            "mission_id": "m1",
            "task_hash": canonical_task_hash(self.verify_task),
            "status": "COMPLETED",
            "result_fingerprint": "xyz"
        }, dispatched_route="CLI1")
        self.assertFalse(res)

    def test_r9_cli1_read_only(self):
        import subprocess
        from scripts.courier_real_worker_adapters import create_real_cli1_adapter
        adapter = create_real_cli1_adapter(self.ws)
        with self.assertRaisesRegex(RuntimeError, "CLI1_READONLY_CONTRACT_VIOLATED"):
            adapter({
                "task_hash": "th",
                "worker_id": "w1",
                "target_agent": "CLI1",
                "payload": {"action": "implement_bounded_improvement", "capability_request": "implementation"}
            })

    def test_r10_implementation_still_gemini(self):
        impl_task = {
            "action": "implement_bounded_improvement",
            "capability_request": "implementation",
            "preferred_agent": "GEMINI"
        }
        target = self.dispatcher.evaluate_routing("implementation", "GEMINI")
        self.assertEqual(target, "GEMINI", "Implementation should route to GEMINI")

if __name__ == '__main__':
    unittest.main()
