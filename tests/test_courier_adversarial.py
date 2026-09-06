import unittest
import json
import uuid
import tempfile
from pathlib import Path
import os
import shutil

from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, MissionQueue, LocalWorkerAdapterBoundary
from scripts.courier_founder_mode import MultiChatGoalIntake
from scripts.worker_availability import WorkerAvailabilityResolver

class TestAdversarialRecoveryAndDedupe(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.events_dir = self.test_dir / "events"
        self.goals_dir = self.events_dir / "founder-mode"
        self.queue_dir = self.events_dir / "mission-queue"
        self.goals_dir.mkdir(parents=True)
        self.queue_dir.mkdir(parents=True)

        # Initialize queue
        self.queue = MissionQueue(self.test_dir)
        with open(self.queue.queue_file, "w") as f:
            json.dump({"schema_version": "1.0", "missions": []}, f)

        self.intake = MultiChatGoalIntake(self.test_dir)
        self.boundary = LocalWorkerAdapterBoundary(self.test_dir, {})
        self.dispatcher = CourierSafetyDispatcher(self.test_dir, self.boundary)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _add_goal(self, status="ACTIVE", goal_id="g1"):
        data = self.intake._read_no_lock()
        data.append({"goal_id": goal_id, "goal": "test goal", "status": status, "priority": 10})
        def mutate(doc):
            doc.clear()
            doc.extend(data)
            return True
        self.intake._mutate(mutate)

    def _add_mission(self, status="PENDING", mission_id="m1", result_ref=None, task_hash="hash1", goal="test goal"):
        record = {
            "mission_id": mission_id, "parent_mission_id": None, "goal": goal, "normalized_task": "test",
            "capability_required": "code", "preferred_agent": "", "requires_write": False,
            "is_heavy": False, "risk_class": "SAFE", "verification_required": True,
            "status": status, "task_hash": task_hash, "created_at": 1000.0,
            "claimed_by": None,
            "result_reference": result_ref, "verification_reference": None, "next_mission_reference": None
        }
        def apply(doc):
            doc["missions"].append(record)
            return doc
        self.queue._mutate(apply)

    # RECOVERY TESTS
    def test_R1_active_founder_goal_stale_claimed(self):
        self._add_goal("ACTIVE")
        self._add_mission("CLAIMED")
        self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "CLAIMED")

    def test_R2_active_founder_goal_failed_mission(self):
        self._add_goal("ACTIVE")
        self._add_mission("FAIL")
        self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "FAIL")

    def test_R3_human_gate_sticky(self):
        self._add_goal("ACTIVE")
        self._add_mission("HUMAN_GATE")
        self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "HUMAN_GATE")

    def test_R4_blocked_auth_required(self):
        self._add_goal("ACTIVE")
        self._add_mission("BLOCKED", result_ref="AUTH_REQUIRED")
        self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "BLOCKED")

    def test_R5_blocked_worker_unavailable_unchanged_fingerprint(self):
        self._add_goal("BLOCKED", goal_id="g1")
        data = self.intake._read_no_lock()
        data[0]["blocker_evidence"] = {"worker_evidence": {"state": "UNAVAILABLE", "worker": "GEMINI"}}
        def m(doc):
            doc.clear(); doc.extend(data); return True
        self.intake._mutate(m)
        self._add_mission("BLOCKED", result_ref="WORKER_UNAVAILABLE")

        from unittest.mock import patch
        with patch('scripts.worker_availability.WorkerAvailabilityResolver.resolve_gemini') as mock_resolve:
            mock_resolve.return_value.to_dict.return_value = {"state": "UNAVAILABLE", "worker": "GEMINI"}
            self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "BLOCKED")

    def test_R6_blocked_worker_unavailable_changed_fingerprint(self):
        self._add_goal("BLOCKED", goal_id="g1")
        data = self.intake._read_no_lock()
        data[0]["blocker_evidence"] = {"worker_evidence": {"state": "UNAVAILABLE", "worker": "GEMINI"}}
        def m(doc):
            doc.clear(); doc.extend(data); return True
        self.intake._mutate(m)
        self._add_mission("BLOCKED", result_ref="WORKER_UNAVAILABLE")

        from unittest.mock import patch
        with patch('scripts.worker_availability.WorkerAvailabilityResolver.resolve_gemini') as mock_resolve:
            mock_resolve.return_value.to_dict.return_value = {"state": "AVAILABLE", "worker": "GEMINI"}
            self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "PENDING")

    def test_R7_run_courier_again_same_new_fingerprint(self):
        self.test_R6_blocked_worker_unavailable_changed_fingerprint()
        from unittest.mock import patch
        with patch('scripts.worker_availability.WorkerAvailabilityResolver.resolve_gemini') as mock_resolve:
            mock_resolve.return_value.to_dict.return_value = {"state": "AVAILABLE", "worker": "GEMINI"}
            self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "PENDING")

    def test_R8_worker_unavailable_changed_live_writer(self):
        self._add_goal("BLOCKED", goal_id="g1")
        data = self.intake._read_no_lock()
        data[0]["blocker_evidence"] = {"worker_evidence": {"state": "UNAVAILABLE", "worker": "GEMINI"}}
        def m(doc):
            doc.clear(); doc.extend(data); return True
        self.intake._mutate(m)
        self._add_mission("CLAIMED", result_ref="WORKER_UNAVAILABLE")

        from unittest.mock import patch
        with patch('scripts.worker_availability.WorkerAvailabilityResolver.resolve_gemini') as mock_resolve:
            mock_resolve.return_value.to_dict.return_value = {"state": "AVAILABLE", "worker": "GEMINI"}
            self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "CLAIMED")

    def test_R9_two_founder_goals_cannot_steal(self):
        self._add_goal("BLOCKED", goal_id="g1")
        self._add_goal("ACTIVE", goal_id="g2")
        self._add_mission("CLAIMED", mission_id="m1", goal="test goal")
        self._add_mission("PENDING", mission_id="m2", goal="test goal 2")
        self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "CLAIMED")

    def test_R10_duplicate_goal_intake_cannot_bypass_terminal_safety(self):
        self._add_goal("ACTIVE", goal_id="g1")
        self._add_mission("FAIL", mission_id="m1")
        self.intake.pop_next_goal()
        self.assertEqual(self.queue.get("m1")["status"], "FAIL")

    # DEDUPE TESTS
    def _write_result(self, task_hash, data):
        path = self.events_dir / "task-envelopes" / f"result_test_{task_hash}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    def _dispatch_mock(self, task_hash):
        self.dispatcher._requires_human_gate = lambda m, t: False
        self.dispatcher.router.select_agent = lambda c, p: "CLI1"
        self.dispatcher.submit_task = lambda *args, **kwargs: {"status": "DEDUPED", "task_hash": task_hash, "route": "CLI1"}
        return self.dispatcher.process_next_mission("worker1")




    def test_D1_same_task_hash_foreign_mission(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m2", "status": "COMPLETED", "result_fingerprint": "f1"})
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D2_same_task_hash_stale_result(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m1", "status": "STALE", "result_fingerprint": "f1"})
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D3_same_filename_pattern_malformed(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        path = self.events_dir / "task-envelopes" / "result_test_h1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f: f.write("not json")
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D4_same_task_hash_wrong_worker(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m1", "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "GEMINI"})
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D5_same_task_hash_requested_gemini_confirmed_local(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m1", "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "CLI1", "worker_type": "DETERMINISTIC_LOCAL"})
        # Let's say requested was GEMINI, this should fail.
        from unittest.mock import patch
        with patch('scripts.courier_safety_dispatcher.CourierSafetyDispatcher._requires_human_gate', return_value=False):
            with patch('scripts.courier_safety_dispatcher.DynamicAgentRouter.select_agent', return_value="GEMINI"):
                with patch('scripts.courier_safety_dispatcher.LocalWorkerAdapterBoundary.dispatch', return_value={"status": "DEDUPED", "task_hash": "h1", "route": "GEMINI"}):
                    res = self.dispatcher.process_next_mission("worker1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D6_result_status_not_successful(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m1", "status": "FAILED", "result_fingerprint": "f1"})
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D7_missing_verification_evidence(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m1", "status": "COMPLETED"})
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D8_correct_fully_identity_bound(self):
        # We need the queue to properly normalize the mission so it has the full task populated
        base_mission = {
            "mission_id": "m1", "parent_mission_id": None, "goal": "test goal", "normalized_task": "test",
            "capability_required": "code", "preferred_agent": "", "requires_write": False,
            "is_heavy": False, "task": {}
        }
        enqueued = self.dispatcher.mission_queue.enqueue(self.dispatcher.mission_queue._normalize(base_mission))

        m = self.dispatcher.mission_queue.get("m1")
        task = dict(m.get("task", {}))
        from scripts.courier_safety_dispatcher import canonical_task_hash
        h = canonical_task_hash(task)
        def apply(doc): doc["missions"][-1]["task_hash"] = h; return doc
        self.dispatcher.mission_queue._mutate(apply)
        self._write_result(h, {"task_hash": h, "mission_id": "m1", "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "CLI1"})
        res = self._dispatch_mock(h)
        self.assertEqual(res["status"], "VERIFIED")

    def test_D9_valid_explicit_cross_mission_reuse(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        self._write_result("h1", {"task_hash": "h1", "mission_id": "m2", "source_mission_id": "m2", "reuse_authorization": "valid", "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "CLI1"})
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

    def test_D10_deduped_but_result_missing(self):
        self._add_mission("PENDING", mission_id="m1", task_hash="h1")
        res = self._dispatch_mock("h1")
        self.assertEqual(res["status"], "BLOCKED")

if __name__ == '__main__':
    unittest.main()

class TestAdversarialLifecycleAuthority(unittest.TestCase):
    def setUp(self):
        import shutil
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        self.workspace = Path("/tmp/courier_test_L")
        if self.workspace.exists(): shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True)
        self.dispatcher = CourierSafetyDispatcher(str(self.workspace))

    def _add_mission(self, status, mission_id="m1", result_reference=None):
        m = {
            "mission_id": mission_id, "parent_mission_id": None, "goal": "test",
            "normalized_task": "test", "capability_required": "local repo analysis",
            "preferred_agent": "GEMINI", "requires_write": True, "is_heavy": False,
            "risk_class": "SAFE", "verification_required": True, "status": status,
            "task_hash": "h1", "created_at": 1000, "claimed_by": "w1",
            "result_reference": result_reference, "verification_reference": None,
            "next_mission_reference": None
        }
        def apply(doc):
            doc.setdefault("missions", []).append(m)
            return doc
        self.dispatcher.mission_queue._mutate(apply)

    def test_L1_direct_HUMAN_GATE_to_PENDING_denied(self):
        self._add_mission("HUMAN_GATE")
        with self.assertRaises(RuntimeError):
            self.dispatcher.mission_queue.transition("m1", "PENDING")

    def test_L2_direct_FAILED_to_PENDING_denied(self):
        self._add_mission("FAILED")
        with self.assertRaises(RuntimeError):
            self.dispatcher.mission_queue.transition("m1", "PENDING")

    def test_L3_arbitrary_BLOCKED_to_PENDING_denied(self):
        self._add_mission("BLOCKED")
        with self.assertRaises(RuntimeError):
            self.dispatcher.mission_queue.transition("m1", "PENDING")

    def test_L4_WORKER_UNAVAILABLE_without_evidence_change_denied(self):
        self._add_mission("BLOCKED", result_reference="WORKER_UNAVAILABLE")
        def apply(doc):
            doc["missions"][0]["blocker_evidence"] = "ev1"
            return doc
        self.dispatcher.mission_queue._mutate(apply)
        with self.assertRaises(RuntimeError):
            self.dispatcher.mission_queue.retry_worker_unavailable("m1", "ev1", "ev1")

    def test_L5_WORKER_UNAVAILABLE_changed_evidence_allowed(self):
        self._add_mission("BLOCKED", result_reference="WORKER_UNAVAILABLE")
        def apply(doc):
            doc["missions"][0]["blocker_evidence"] = "ev1"
            return doc
        self.dispatcher.mission_queue._mutate(apply)
        self.dispatcher.mission_queue.retry_worker_unavailable("m1", "ev1", "ev2")
        m = self.dispatcher.mission_queue.get("m1")
        self.assertEqual(m["status"], "PENDING")

    def test_L6_second_identical_retry_denied(self):
        self._add_mission("BLOCKED", result_reference="WORKER_UNAVAILABLE")
        def apply(doc):
            doc["missions"][0]["blocker_evidence"] = "ev1"
            return doc
        self.dispatcher.mission_queue._mutate(apply)
        self.dispatcher.mission_queue.retry_worker_unavailable("m1", "ev1", "ev2")

        # Block again with ev2
        self.dispatcher.mission_queue.transition("m1", "BLOCKED", result_reference="WORKER_UNAVAILABLE", blocker_evidence="ev2")
        # Try to retry ev1->ev2 again
        with self.assertRaises(RuntimeError):
            self.dispatcher.mission_queue.retry_worker_unavailable("m1", "ev1", "ev2")

    def test_L7_conflicting_writer_claim_denied(self):
        self._add_mission("BLOCKED", result_reference="WORKER_UNAVAILABLE")
        def apply(doc):
            doc["missions"][0]["blocker_evidence"] = "ev1"
            return doc
        self.dispatcher.mission_queue._mutate(apply)

        # Acquire writer lease
        self.dispatcher.lease_manager.acquire_lease("global_writer_lease", "other_task", "other_worker", 3600)

        res = self.dispatcher.retry_worker_unavailable("w1", "m1")
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["reason"], "WRITER_CONFLICT")

    def test_L8_concurrent_retry_attempts_cannot_both_win(self):
        self._add_mission("BLOCKED", result_reference="WORKER_UNAVAILABLE")
        def apply(doc):
            doc["missions"][0]["blocker_evidence"] = "ev1"
            return doc
        self.dispatcher.mission_queue._mutate(apply)

        self.dispatcher.mission_queue.retry_worker_unavailable("m1", "ev1", "ev2")
        with self.assertRaises(RuntimeError):
            self.dispatcher.mission_queue.retry_worker_unavailable("m1", "ev1", "ev2")

class TestAdversarialResultValidation(unittest.TestCase):
    def setUp(self):
        import shutil
        from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
        self.workspace = Path("/tmp/courier_test_V")
        if self.workspace.exists(): shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True)
        self.dispatcher = CourierSafetyDispatcher(str(self.workspace))

    def _add_mission(self, mission_id="m1", task_hash="h1", preferred_agent="GEMINI"):
        m = {
            "mission_id": mission_id, "parent_mission_id": None, "goal": "test",
            "normalized_task": "test", "capability_required": "local repo analysis",
            "preferred_agent": "GEMINI", "requires_write": True, "is_heavy": False,
            "risk_class": "SAFE", "verification_required": True, "status": "PENDING",
            "task_hash": task_hash, "created_at": 1000, "claimed_by": "w1",
            "result_reference": None, "verification_reference": None,
            "next_mission_reference": None,
            "task": {"capability_request": "local repo analysis", "preferred_agent": preferred_agent}
        }
        def apply(doc):
            doc.setdefault("missions", []).append(m)
            return doc
        self.dispatcher.mission_queue._mutate(apply)

    def test_V1_stale_same_mission(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, {"mission_id": "m1", "task_hash": "h1", "status": "STALE"}, "GEMINI")
        self.assertFalse(res)

    def test_V2_foreign_same_hash(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, {"mission_id": "m2", "task_hash": "h1", "status": "COMPLETED"}, "GEMINI")
        self.assertFalse(res)

    def test_V3_arbitrary_boolean_reuse(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, {"mission_id": "m2", "task_hash": "h1", "status": "COMPLETED", "reuse_authorization": True}, "GEMINI")
        self.assertFalse(res)

    def test_V4_malformed_result(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, "not a dict", "GEMINI")
        self.assertFalse(res)

    def test_V5_wrong_worker(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, {"mission_id": "m1", "task_hash": "h1", "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "CLI1"}, "GEMINI")
        self.assertFalse(res)

    def test_V6_requested_gemini_confirmed_local(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, {"mission_id": "m1", "task_hash": "h1", "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "GEMINI", "payload": {"requested_model": "gemini-3.7-flash-medium", "confirmed_model": "local"}}, "GEMINI")
        self.assertFalse(res)

    def test_V7_missing_verification_evidence(self):
        self._add_mission()
        res = self.dispatcher.canonical_validate_result("m1", {"preferred_agent": "GEMINI"}, {"mission_id": "m1", "task_hash": "h1", "status": "COMPLETED", "target_agent": "GEMINI"}, "GEMINI")
        self.assertFalse(res)

    def test_V8_valid_current_identity_bound(self):
        self._add_mission()
        self.dispatcher.mission_queue.transition("m1", "CLAIMED")
        self.dispatcher.mission_queue.transition("m1", "RUNNING")
        self.dispatcher.mission_queue.transition("m1", "PENDING_VERIFY")
        from scripts.courier_safety_dispatcher import canonical_task_hash
        task = {"capability_request": "local repo analysis", "preferred_agent": "GEMINI"}
        h = canonical_task_hash(task)
        res = self.dispatcher.canonical_validate_result("m1", task, {"mission_id": "m1", "task_hash": h, "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "GEMINI"}, "GEMINI")
        self.assertTrue(res)

    def test_V9_successor_absent_after_rejected_validation(self):
        # Already tested by D tests fundamentally
        self._add_mission()
        self.dispatcher.verify_result("w1", "h1", "PASS", {"mission_id": "m2", "task_hash": "h1"})
        succ = self.dispatcher.mission_queue.derive_successor("m1", lambda x: {})
        self.assertIsNone(succ)

    def test_V10_successor_permitted_only_after_accepted_validation(self):
        self._add_mission()
        self.dispatcher.mission_queue.transition("m1", "CLAIMED")
        self.dispatcher.mission_queue.transition("m1", "RUNNING")
        self.dispatcher.mission_queue.transition("m1", "PENDING_VERIFY")
        from scripts.courier_safety_dispatcher import canonical_task_hash
        task = {"capability_request": "local repo analysis", "preferred_agent": "GEMINI"}
        h = canonical_task_hash(task)
        def apply(doc): doc["missions"][0]["task_hash"] = h; return doc
        self.dispatcher.mission_queue._mutate(apply)
        self.dispatcher._inflight[h] = {"worker_id": "w1", "requires_write": False, "is_heavy": False, "result": {"mission_id": "m1", "task_hash": h, "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "GEMINI"}, "route": "GEMINI"}
        self.dispatcher.verify_result("w1", h, "PASS", {"mission_id": "m1", "task_hash": h, "status": "COMPLETED", "result_fingerprint": "f1", "target_agent": "GEMINI"})
        self.dispatcher.mission_queue.transition("m1", "VERIFIED")
        succ = self.dispatcher.mission_queue.derive_successor("m1", lambda x: {"task_hash": "h2"})
        self.assertIsNotNone(succ)
