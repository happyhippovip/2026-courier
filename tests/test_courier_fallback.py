import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_real_worker_adapters import get_real_worker_adapters, create_real_local_cheap_adapter

class TestCourierFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dispatcher = CourierSafetyDispatcher(workspace_dir=self.tmp.name)
        Path(self.tmp.name, "events", "mission-queue").mkdir(parents=True, exist_ok=True)
        with open(Path(self.tmp.name, "events", "mission-queue", "queue.json"), "w") as f:
            f.write('{"schema_version": "1.0", "missions": []}')
            
        scripts_dir = Path(self.tmp.name) / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "autonomy_supervisor.py").write_text("def run(): pass\n")

        self.adapters = get_real_worker_adapters(self.tmp.name)
        for agent, adapter in self.adapters.items():
            self.dispatcher.adapter_boundary.register_consumer(agent, adapter)
            
    def tearDown(self):
        self.tmp.cleanup()
        
    def test_transient_gemini_failure_deterministic_local_cheap_succeeds(self):
        mission_id = "test-fallback-1"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "task": {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "GEMINI"
            }
        })
        
        submit_calls = []
        original_submit_task = self.dispatcher.submit_task
        
        def mocked_submit_task(worker_id, task, mission_id=""):
            target = self.dispatcher.evaluate_routing(task.get("capability_request", ""), task.get("preferred_agent"))
            submit_calls.append(target)
            if len(submit_calls) == 1:
                self.dispatcher.last_result_status = "DISPATCH_EXCEPTION"
                return {"status": "FAIL_CLOSED", "reason": "MISSING_ACK_OR_DISPATCH_FAIL: DISPATCH_FAILED: GEMINI_NATIVE_AGY_FAILED: ERROR timeout"}
            
            # For the second call, let's actually use the real LOCAL_CHEAP adapter to prove it works
            return original_submit_task(worker_id, task, mission_id)
            
        self.dispatcher.submit_task = mocked_submit_task
        # We need verify_result to pass since LOCAL_CHEAP produces a valid envelope
        self.dispatcher.verify_result = MagicMock(return_value="VERIFIED_AND_CACHED")
        
        result = self.dispatcher.process_next_mission("worker-1")
        
        self.assertEqual(submit_calls, ["GEMINI", "LOCAL_CHEAP"])
        self.assertEqual(result["status"], "VERIFIED")

    @patch("scripts.courier_real_worker_adapters.execute_native_agy_prompt")
    def test_local_cheap_makes_zero_native_agy_calls(self, mock_agy):
        mission_id = "test-fallback-zero-agy"
        task = {
            "action": "discover_improvement_opportunities",
            "requires_write": False,
            "capability_request": "local repo analysis",
            "preferred_agent": "LOCAL_CHEAP"
        }
        envelope = {
            "task_hash": "hash123",
            "worker_id": "w1",
            "target_agent": "LOCAL_CHEAP",
            "mission_id": mission_id,
            "payload": task
        }
        adapter = create_real_local_cheap_adapter(self.tmp.name)
        res = adapter(envelope)
        
        # Must succeed and NOT call agy
        self.assertEqual(res.get("result", {}).get("status"), "COMPLETED")
        mock_agy.assert_not_called()

    def test_unrelated_error_blocked(self):
        mission_id = "test-fallback-2"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "task": {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "GEMINI"
            }
        })
        
        submit_calls = []
        def mocked_submit_task(worker_id, task, mission_id=""):
            target = self.dispatcher.evaluate_routing(task.get("capability_request", ""), task.get("preferred_agent"))
            submit_calls.append(target)
            self.dispatcher.last_result_status = "DISPATCH_EXCEPTION"
            return {"status": "FAIL_CLOSED", "reason": "MISSING_ACK_OR_DISPATCH_FAIL: DISPATCH_FAILED: something else"}
            
        self.dispatcher.submit_task = mocked_submit_task
        result = self.dispatcher.process_next_mission("worker-2")
        self.assertEqual(submit_calls, ["GEMINI"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_write_task_no_fallback(self):
        mission_id = "test-fallback-write"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "task": {
                "action": "discover_improvement_opportunities", 
                "requires_write": True,
                "capability_request": "local repo analysis",
                "preferred_agent": "GEMINI",
                "acceptance_criteria": {"finding_id": "1"}
            }
        })
        
        submit_calls = []
        def mocked_submit_task(worker_id, task, mission_id=""):
            target = self.dispatcher.evaluate_routing(task.get("capability_request", ""), task.get("preferred_agent"))
            submit_calls.append(target)
            self.dispatcher.last_result_status = "DISPATCH_EXCEPTION"
            return {"status": "FAIL_CLOSED", "reason": "MISSING_ACK_OR_DISPATCH_FAIL: DISPATCH_FAILED: GEMINI_NATIVE_AGY_FAILED: ERROR timeout"}
            
        self.dispatcher.submit_task = mocked_submit_task
        result = self.dispatcher.process_next_mission("worker-write")
        self.assertEqual(submit_calls, ["GEMINI"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_human_gate_no_fallback(self):
        mission_id = "test-fallback-human"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "task": {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "GEMINI",
                "payment_mode": "LIVE"
            }
        })
        
        result = self.dispatcher.process_next_mission("worker-human")
        self.assertEqual(result["status"], "BLOCKED")
        
    def test_safety_denial_no_fallback(self):
        mission_id = "test-fallback-safety"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "task": {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "GEMINI",
                "trade_mode": "LIVE" # triggers is_safe_action denial
            }
        })
        
        result = self.dispatcher.process_next_mission("worker-safety")
        self.assertEqual(result["status"], "BLOCKED")

    def test_malformed_local_result_fail_closed(self):
        mission_id = "test-fallback-malformed"
        self.dispatcher.mission_queue.enqueue({
            "mission_id": mission_id,
            "status": "PENDING",
            "task": {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "GEMINI"
            }
        })
        
        def mocked_submit_task(worker_id, task, mission_id=""):
            target = self.dispatcher.evaluate_routing(task.get("capability_request", ""), task.get("preferred_agent"))
            if target == "GEMINI":
                self.dispatcher.last_result_status = "DISPATCH_EXCEPTION"
                return {"status": "FAIL_CLOSED", "reason": "MISSING_ACK_OR_DISPATCH_FAIL: DISPATCH_FAILED: GEMINI_NATIVE_AGY_FAILED: ERROR"}
            else:
                self.dispatcher.last_result_status = "PENDING_VERIFY"
                return {
                    "status": "EXECUTED",
                    "route": "LOCAL_CHEAP",
                    "dispatch_info": {
                        "result": {"payload": {}}, # malformed!
                        "result_path": "/fake/path"
                    },
                    "task_hash": "testhash",
                    "requires_verify": True
                }
                
        self.dispatcher.submit_task = mocked_submit_task
        # Don't mock verify_result, let it handle the malformed result naturally!
        # Actually verify_result will fail because state mapping is checked.
        
        # We need to manually set inflight state because mocked submit_task didn't do it
        original_submit = self.dispatcher.submit_task
        def wrapper(worker_id, task, mission_id=""):
            res = original_submit(worker_id, task, mission_id)
            if res["status"] == "EXECUTED":
                self.dispatcher._inflight[res["task_hash"]] = {
                    "worker_id": worker_id, 
                    "requires_write": False, 
                    "is_heavy": False, 
                    "result": res["dispatch_info"]["result"], 
                    "route": "LOCAL_CHEAP", 
                    "task": task, 
                    "mission_id": mission_id, 
                    "prestate": {}
                }
            return res
            
        self.dispatcher.submit_task = wrapper
        
        result = self.dispatcher.process_next_mission("worker-malformed")
        
        # It should fail verifying
        self.assertEqual(result["status"], "FAILED")

    def test_local_cheap_generic_discovery_with_evidence(self):
        import tempfile
        from pathlib import Path
        from scripts.courier_real_worker_adapters import create_real_local_cheap_adapter
        with tempfile.TemporaryDirectory() as tmp_dir:
            scripts_dir = Path(tmp_dir) / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "autonomy_supervisor.py").write_text("def run(): pass\n")
            
            task = {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "LOCAL_CHEAP"
            }
            envelope = {
                "task_hash": "hash123",
                "worker_id": "w1",
                "target_agent": "LOCAL_CHEAP",
                "mission_id": "test-generic",
                "payload": task
            }
            adapter = create_real_local_cheap_adapter(tmp_dir)
            res = adapter(envelope)
            self.assertEqual(res.get("result", {}).get("status"), "COMPLETED")
            payload = res["result"]["payload"]
            self.assertEqual(payload.get("action"), "discover_improvement_opportunities")

    def test_local_cheap_generic_discovery_no_evidence(self):

        import tempfile
        from pathlib import Path
        from scripts.courier_real_worker_adapters import create_real_local_cheap_adapter
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Empty repo, no python files, should return no evidence
            task = {
                "action": "discover_improvement_opportunities",
                "requires_write": False,
                "capability_request": "local repo analysis",
                "preferred_agent": "LOCAL_CHEAP"
            }
            envelope = {
                "task_hash": "hash123",
                "worker_id": "w1",
                "target_agent": "LOCAL_CHEAP",
                "mission_id": "test-generic-empty",
                "payload": task
            }
            adapter = create_real_local_cheap_adapter(tmp_dir)
            res = adapter(envelope)
            self.assertIn("result", res)
            self.assertEqual(res["result"]["payload"]["weakness_id"], "NONE")

if __name__ == "__main__":
    unittest.main()
