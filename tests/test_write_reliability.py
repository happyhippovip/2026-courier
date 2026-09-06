import unittest
from pathlib import Path
import json

from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, TaskEnvelope

class TestWriteReliability(unittest.TestCase):
    def setUp(self):
        import shutil
        self.workspace = Path("test_workspace")
        if self.workspace.exists(): shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.dispatcher = CourierSafetyDispatcher(self.workspace)
        
        # We simulate the worker boundary so we can test the retry loop
        self.dispatch_count = 0
        self.last_envelope = None
        
        class MockBoundary:
            def __init__(self, test_case):
                self.tc = test_case
                self.events_dir = self.tc.workspace / "events"
                self.events_dir.mkdir(exist_ok=True)
                
            def dispatch(self, agent, envelope, adapters):
                self.tc.dispatch_count += 1
                self.tc.last_envelope = envelope
                if self.tc.dispatch_count == 1:
                    self.tc.first_task_hash = envelope.task_hash
                
                # Mock result based on attempt number
                if self.tc.dispatch_count == 1:
                    result = {
                        "status": "COMPLETED",
                        "task_hash": envelope.task_hash,
                        "mission_id": envelope.mission_id,
                        "target_agent": agent,
                        "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS", "summary": "Did it"}
                    }
                else:
                    result = {
                        "status": "COMPLETED",
                        "task_hash": envelope.task_hash,
                        "mission_id": envelope.mission_id,
                        "target_agent": agent,
                        "result_fingerprint": "mock_fp_2", "payload": {"verdict": "PASS", "summary": "Did it on retry"}
                    }
                
                # if the test dictates, create the effect
                if hasattr(self.tc, "create_effect_on_attempt") and self.tc.create_effect_on_attempt == self.tc.dispatch_count:
                    (self.tc.workspace / "effect.txt").write_text("DONE")
                
                return {
                    "dispatched_to": agent,
                    "result": result,
                    "result_path": "dummy.json",
                    "ack_path": "dummy_ack.json",
                    "envelope_path": "dummy_env.json",
                    "route": agent
                }
                
        self.dispatcher.adapter_boundary = MockBoundary(self)
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m1",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "task": {
                "action": "implement_bounded_improvement",
                "requires_write": True,
                "is_heavy": False,
                "acceptance_criteria": {
                    "file_exists": "effect.txt",
                    "content_matches": "DONE"
                }
            }
        })
        
    def tearDown(self):
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
            
    def test_e1_e2_e3_e4_e5_e6_e8(self):
        # E1: Initial Gemini PASS + missing requested effect does NOT become VERIFIED.
        # E2: Missing effect after first attempt causes exactly ONE corrective native Gemini attempt.
        # E3: Second attempt uses same mission_id.
        # E4: Second attempt uses same task_hash.
        # E5: Second attempt uses same authorized worker.
        # E6: If second attempt creates fresh correct effect, mission may proceed.
        # E8: No third attempt occurs.
        self.create_effect_on_attempt = 2
        res = self.dispatcher.process_next_mission("founder")
        
        self.assertEqual(self.dispatch_count, 2)
        self.assertEqual(res["status"], "VERIFIED")
        self.assertEqual(self.last_envelope.native_attempt, 2)
        self.assertEqual(self.last_envelope.mission_id, "m1")
        self.assertEqual(self.last_envelope.target_agent, "GEMINI")
        self.assertEqual(self.last_envelope.task_hash, self.first_task_hash)
        
    def test_e7_e22(self):
        # E7: If second attempt still produces no effect, mission fails closed.
        # E22: attempt count is bounded to maximum 2.
        self.create_effect_on_attempt = 3  # Never creates it in 2 attempts
        res = self.dispatcher.process_next_mission("founder")
        
        self.assertEqual(self.dispatch_count, 2)
        self.assertEqual(res["status"], "FAILED")

    def test_e9_first_attempt_human_gate(self):
        # E9: HUMAN_GATE on first attempt -> no retry
        def mock_dispatch(agent, env, adp):
            self.dispatch_count += 1
            return {"result": {"status": "HUMAN_GATE", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "HUMAN_GATE")
        
    def test_e12_unsafe_prestate(self):
        # E12: unsafe path/prestate failure -> no corrective retry
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m2",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "task": {
                "action": "implement_bounded_improvement",
                "requires_write": True,
                "acceptance_criteria": {
                    "file_exists": "../out_of_bounds.txt"
                }
            }
        })
        # clear first one
        self.dispatcher.mission_queue.claim_next("founder")
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(self.dispatch_count, 0)

    def test_e13_read_only(self):
        # E13: read-only mission never uses write retry
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m3",
            "capability_required": "implementation",
            "preferred_agent": "GEMINI",
            "task": {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "acceptance_criteria": {
                    "file_exists": "effect.txt"
                }
            }
        })
        self.dispatcher.mission_queue.claim_next("founder")
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(self.dispatch_count, 1)




    def test_e10_second_attempt_human_gate(self):
        def mock_dispatch(agent, env, adp):
            self.dispatch_count += 1
            if self.dispatch_count == 1:
                return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
            else:
                return {"result_path": "dummy.json", "route": agent, "result": {"status": "HUMAN_GATE", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp_2", "payload": {"verdict": "HUMAN_GATE"}, "error_type": "AUTHENTICATION_REQUIRED"}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 2)
        self.assertIn(res["status"], ["HUMAN_GATE", "FAILED"])
        self.assertNotEqual(res["status"], "VERIFIED")

    def test_e11_identity_mismatch_no_retry(self):
        def mock_dispatch(agent, env, adp):
            self.dispatch_count += 1
            return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": "WRONG_HASH", "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "FAILED")

    def test_e14_cli1_no_write_retry(self):
        # process m1 to get it out of the way
        self.dispatcher.mission_queue.claim_next("founder")
        self.dispatcher.mission_queue.transition("m1", "BLOCKED", claimed_by="founder")
        
        self.dispatcher.mission_queue.enqueue({
            "mission_id": "m_cli1",
            "capability_required": "local repo analysis",
            "preferred_agent": "CLI1",
            "task": {
                "action": "implement_bounded_improvement",
                "requires_write": True,
                "acceptance_criteria": {"file_exists": "effect.txt"}
            }
        })
        def mock_dispatch(agent, env, adp):
            if agent == "CLI1":
                raise RuntimeError("CLI1_READONLY_CONTRACT_VIOLATED")
            self.dispatch_count += 1
            return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
        self.dispatcher.adapter_boundary.dispatch = mock_dispatch
        try:
            res = self.dispatcher.process_next_mission("founder")
        except Exception:
            res = {"status": "FAILED"}
        self.assertLessEqual(self.dispatch_count, 0) # never dispatched successfully
        self.assertNotEqual(res["status"], "VERIFIED")

    def test_e15_courier_never_writes_effect(self):
        self.create_effect_on_attempt = 3
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 2)
        self.assertNotEqual(res["status"], "VERIFIED")
        self.assertFalse((self.workspace / "effect.txt").exists())

    def test_e16_stale_effect_rejected(self):
        (self.workspace / "effect.txt").write_text("DONE")
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "FAILED")

    def test_e17_freshness_required(self):
        (self.workspace / "effect.txt").write_text("DONE")
        self.create_effect_on_attempt = 1
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(self.dispatch_count, 1)
        self.assertEqual(res["status"], "FAILED")

    def test_e18_ledger_binds_final_execution(self):
        self.create_effect_on_attempt = 2
        res = self.dispatcher.process_next_mission("founder")
        self.assertEqual(res["status"], "VERIFIED")
        
        ledger_data = self.dispatcher.ledger._load_ledger()
        reviews = ledger_data.get("reviews", {})
        self.assertTrue(len(reviews) > 0)
        last_review = list(reviews.values())[-1]
        
        # Check result fingerprint hash matches the mock result data hash
        from scripts.review_budget import canonical_json_dumps, compute_sha256
        result_data_1 = {"status": "COMPLETED", "task_hash": self.last_envelope.task_hash, "mission_id": "m1", "target_agent": "GEMINI", "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS", "summary": "Did it"}}
        result_data_2 = {"status": "COMPLETED", "task_hash": self.last_envelope.task_hash, "mission_id": "m1", "target_agent": "GEMINI", "result_fingerprint": "mock_fp_2", "payload": {"verdict": "PASS", "summary": "Did it on retry"}}
        fp1 = compute_sha256(canonical_json_dumps(result_data_1))
        fp2 = compute_sha256(canonical_json_dumps(result_data_2))
        
        self.assertEqual(last_review["file_hashes"]["result_fingerprint"], fp2)
        self.assertNotEqual(last_review["file_hashes"]["result_fingerprint"], fp1)
        self.assertEqual(last_review["file_hashes"]["effect_verified"], "True")
        self.assertEqual(last_review["file_hashes"]["freshness_verified"], "True")
        self.assertEqual(last_review["file_hashes"]["worker_id"], "GEMINI")
        self.assertEqual(last_review["file_hashes"]["coordinator_worker_id"], "founder")
        self.assertEqual(last_review["file_hashes"]["dispatched_route"], "GEMINI")
        self.assertEqual(last_review["file_hashes"]["native_attempt"], "2")
        self.assertEqual(last_review["file_hashes"]["mission_id"], "m1")

    def test_e21_no_canary_specific_production_logic(self):
        import pathlib
        prod_files = [
            Path("scripts/courier_safety_dispatcher.py"),
            Path("scripts/courier_real_worker_adapters.py"),
            Path("scripts/native_agy_runner.py")
        ]
        forbidden = [
            "courier_freeze_native_canary_",
            "CANARY_4", "CANARY_5", "CANARY_6", "CANARY_7", "CANARY_8",
            "COURIER_NATIVE_AUTONOMY_PROVEN_"
        ]
        for fpath in prod_files:
            if not fpath.exists(): continue
            text = fpath.read_text()
            for token in forbidden:
                self.assertNotIn(token, text, f"Forbidden token {token} found in {fpath}")
