import unittest
import tempfile
import json
from pathlib import Path

from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_founder_mode import FounderModePlanner

class TestTaskEffectVerification(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        
        # We can just test the evaluate_success and verify_result directly.
        class MockBoundary:
            def __init__(self, ws):
                self.events_dir = ws / "events"
                self.events_dir.mkdir(parents=True, exist_ok=True)
            def register_consumer(self, *args): pass
        self.boundary = MockBoundary(self.workspace)
        self.dispatcher = CourierSafetyDispatcher(self.workspace, adapter_boundary=self.boundary)
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_t1_missing_canary_file(self):
        # T1: Identity-valid result + MISSING canary file -> MUST evaluate to NOT SATISFIED (FAIL_CLOSED / BLOCKED).
        task = {"requires_write": False,
            "mission_id": "m1",
            "acceptance_criteria": {"file_exists": "canary.txt", "content_matches": "success"}
        }
        from scripts.courier_safety_dispatcher import canonical_hash, canonical_task_hash
        th = canonical_task_hash(task)
        res_data = {
            "task_hash": th,
            "mission_id": "m1",
            "status": "COMPLETED",
            "result_fingerprint": "fprint"
        }
        self.dispatcher._inflight[th] = {"requires_write": False, "is_heavy": False,
            "worker_id": "w1",
            "task": task,
            "mission_id": "m1",
            "result": res_data,
            "route": "GEMINI"
        }
        status = self.dispatcher.verify_result("w1", th, "PASS", res_data)
        self.assertEqual(status, "FAIL_CLOSED")

    def test_t2_incorrect_content(self):
        # T2: Identity-valid result + PRESENT canary file + INCORRECT content -> MUST evaluate to NOT SATISFIED.
        task = {"requires_write": False,
            "mission_id": "m1",
            "acceptance_criteria": {"file_exists": "canary.txt", "content_matches": "success"}
        }
        from scripts.courier_safety_dispatcher import canonical_hash, canonical_task_hash
        th = canonical_task_hash(task)
        res_data = {
            "task_hash": th,
            "mission_id": "m1",
            "status": "COMPLETED",
            "result_fingerprint": "fprint"
        }
        self.dispatcher._inflight[th] = {"requires_write": False, "is_heavy": False,
            "worker_id": "w1",
            "task": task,
            "mission_id": "m1",
            "result": res_data,
            "route": "GEMINI"
        }
        (self.workspace / "canary.txt").write_text("wrong content")
        status = self.dispatcher.verify_result("w1", th, "PASS", res_data)
        self.assertEqual(status, "FAIL_CLOSED")

    def test_t3_exact_content(self):
        # T3: Identity-valid result + PRESENT canary file + EXACT content -> MUST evaluate to VERIFIED/SATISFIED.
        task = {"requires_write": False,
            "mission_id": "m1",
            "acceptance_criteria": {"file_exists": "canary.txt", "content_matches": "success"}
        }
        from scripts.courier_safety_dispatcher import canonical_hash, canonical_task_hash
        th = canonical_task_hash(task)
        res_data = {
            "task_hash": th,
            "mission_id": "m1",
            "status": "COMPLETED",
            "result_fingerprint": "fprint"
        }
        self.dispatcher._inflight[th] = {"requires_write": False, "is_heavy": False,
            "worker_id": "w1",
            "task": task,
            "mission_id": "m1",
            "result": res_data,
            "route": "GEMINI"
        }
        (self.workspace / "canary.txt").write_text("success")
        status = self.dispatcher.verify_result("w1", th, "PASS", res_data)
        self.assertEqual(status, "VERIFIED_AND_CACHED")

    def test_t4_identity_invalid(self):
        # T4: Identity-INVALID result + PRESENT canary file + EXACT content -> MUST evaluate to NOT SATISFIED.
        task = {"requires_write": False,
            "mission_id": "m1",
            "acceptance_criteria": {"file_exists": "canary.txt", "content_matches": "success"}
        }
        from scripts.courier_safety_dispatcher import canonical_hash, canonical_task_hash
        th = canonical_task_hash(task)
        res_data = {
            "task_hash": "hash_wrong",
            "mission_id": "m1",
            "status": "COMPLETED",
            "result_fingerprint": "fprint"
        }
        self.dispatcher._inflight["hash_wrong"] = {"requires_write": False, "is_heavy": False,
            "worker_id": "w1",
            "task": task,
            "mission_id": "m1",
            "result": res_data,
            "route": "GEMINI"
        }
        # Actually task_hash inside task is not used by canonical_validate_result directly except it computes it from task
        # We can just fail mission_id:
        res_data["mission_id"] = "wrong"
        (self.workspace / "canary.txt").write_text("success")
        status = self.dispatcher.verify_result("w1", "hash_wrong", "PASS", res_data)
        self.assertEqual(status, "FAIL_CLOSED")

    def test_t5_verify_missing(self):
        # T5: verify_improvement_tests + missing artifact -> FAIL_CLOSED.
        task = {"requires_write": False,
            "mission_id": "m1",
            "acceptance_criteria": {"file_exists": "canary.txt"}
        }
        from scripts.courier_safety_dispatcher import canonical_hash, canonical_task_hash
        th = canonical_task_hash(task)
        res_data = {
            "task_hash": th,
            "mission_id": "m1",
            "status": "COMPLETED",
            "result_fingerprint": "fprint"
        }
        self.dispatcher._inflight[th] = {"requires_write": False, "is_heavy": False,
            "worker_id": "w1",
            "task": task,
            "mission_id": "m1",
            "result": res_data,
            "route": "GEMINI"
        }
        status = self.dispatcher.verify_result("w1", th, "PASS", res_data)
        self.assertEqual(status, "FAIL_CLOSED")

    def test_t6_verify_present(self):
        # T6: verify_improvement_tests + present artifact -> PASS.
        task = {"requires_write": False,
            "mission_id": "m1",
            "acceptance_criteria": {"file_exists": "canary.txt"}
        }
        from scripts.courier_safety_dispatcher import canonical_hash, canonical_task_hash
        th = canonical_task_hash(task)
        res_data = {
            "task_hash": th,
            "mission_id": "m1",
            "status": "COMPLETED",
            "result_fingerprint": "fprint"
        }
        self.dispatcher._inflight[th] = {"requires_write": False, "is_heavy": False,
            "worker_id": "w1",
            "task": task,
            "mission_id": "m1",
            "result": res_data,
            "route": "GEMINI"
        }
        (self.workspace / "canary.txt").write_text("anything")
        status = self.dispatcher.verify_result("w1", th, "PASS", res_data)
        self.assertEqual(status, "VERIFIED_AND_CACHED")
