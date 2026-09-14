from unittest.mock import patch
from unittest.mock import patch
from scripts.worker_availability import WorkerState, AvailabilityEvidence
class MockResolver:
    def resolve_gemini(self):
        return AvailabilityEvidence(worker='GEMINI', state=WorkerState.AVAILABLE, executable='/agy', resolution_method='MOCK', detail='mock')

from unittest.mock import patch
#!/usr/bin/env python3
"""Mission M232-B01I targeted dispatcher acceptance tests."""
import multiprocessing, tempfile, unittest
from pathlib import Path

from scripts.courier_safety_dispatcher import (
    CourierSafetyDispatcher, LocalWorkerAdapterBoundary, MissionQueue, TaskEnvelope, canonical_hash,
    write_json_atomic,
)
from scripts.resource_policy import TaskLeaseManager


def deterministic_consumer(task):
    identity = {k: task[k] for k in ("task_hash", "worker_id", "target_agent", "mission_id") if k in task}
    payload = {"outcome": "LOCAL_DETERMINISTIC_PASS", "input_hash": task["task_hash"]}
    return {
        "ack": {"schema_version": "1.0", "type": "ACK", "status": "ACCEPTED", **identity},
        "result": {"schema_version": "1.0", "type": "RESULT", "status": "COMPLETED",
                   **identity, "payload": payload, "result_fingerprint": canonical_hash(payload)},
    }


def heavy_claim_process(workspace, worker, start, output):
    boundary = LocalWorkerAdapterBoundary(Path(workspace), {"GEMINI": deterministic_consumer})
    dispatcher = CourierSafetyDispatcher(workspace, boundary)
    start.wait()
    output.put(dispatcher.submit_task(worker, {"capability_request": "code", "name": worker, "is_heavy": True})["status"])


class FailingBoundary(LocalWorkerAdapterBoundary):
    def dispatch(self, target_agent, envelope, adapters):
        raise RuntimeError("deterministic failure")


@patch('scripts.worker_availability.WorkerAvailabilityResolver', new=MockResolver)
@patch('scripts.worker_availability.WorkerAvailabilityResolver', new=MockResolver)
class TestCourierSafetyDispatcher(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.boundary = LocalWorkerAdapterBoundary(
            self.root, {agent: deterministic_consumer for agent in ("CLI1", "CODEX", "GEMINI")}
        )
        self.dispatcher = CourierSafetyDispatcher(self.root, self.boundary)
        self.dispatcher.router._worker_executable_available = lambda a, r: True

    def tearDown(self): self.temp.cleanup()

    def result(self, submission): return submission["dispatch_info"]["result"]

    def test_atomic_json_publish_preserves_prior_state_on_replace_failure(self):
        target = self.root / "events" / "task-envelopes" / "prestate.json"
        write_json_atomic(target, {"state": "old"})

        with patch(
            "scripts.courier_safety_dispatcher.os.replace",
            side_effect=OSError("DISPOSABLE_REPLACE_FAILURE"),
        ):
            with self.assertRaisesRegex(OSError, "DISPOSABLE_REPLACE_FAILURE"):
                write_json_atomic(target, {"state": "new"})

        self.assertEqual(target.read_text(encoding="utf-8"), '{\n  "state": "old"\n}')
        self.assertEqual(list(target.parent.glob(f".{target.name}.tmp.*")), [])

    def test_corrupt_lease_state_blocks_recovery(self):
        corrupt = self.dispatcher.lease_manager.locks_dir / "writer.lease"
        corrupt.parent.mkdir(parents=True, exist_ok=True)
        corrupt.write_text('{"owner_pid":', encoding="utf-8")

        with self.assertRaisesRegex(
            RuntimeError,
            "CORRUPT_LEASE_STATE_FAIL_CLOSED: writer.lease",
        ):
            self.dispatcher.reconcile_orphans()

    @patch('scripts.courier_safety_dispatcher.DynamicAgentRouter._worker_executable_available', return_value=True)
    def test_routes_have_real_local_consumer_contract(self, mock_avail):
        for request, expected in (("local repo analysis", "CLI1"), ("legacy implementation", "CODEX"), ("architecture", "GEMINI")):
            with self.subTest(expected):
                boundary = LocalWorkerAdapterBoundary(self.root, {expected: deterministic_consumer})
                dispatcher = CourierSafetyDispatcher(self.root, boundary)
                got = dispatcher.submit_task(f"worker-{expected}", {"capability_request": "code", "name": expected, "capability_request": request})
                self.assertEqual(got["status"], "EXECUTED")
                self.assertEqual(got["route"], expected)
                self.assertTrue(got["dispatch_info"]["worker_accepted"])
                self.assertTrue(Path(got["dispatch_info"]["ack_path"]).exists())
                self.assertTrue(Path(got["dispatch_info"]["result_path"]).exists())

    def test_no_registered_consumer_fails_closed(self):
        got = CourierSafetyDispatcher(self.root).submit_task("w", {"capability_request": "code", "name": "x"})
        self.assertEqual(got["status"], "FAIL_CLOSED")

    def test_missing_ack_fails_closed(self):
        def no_ack(task): return {"result": deterministic_consumer(task)["result"]}
        boundary = LocalWorkerAdapterBoundary(self.root, {"GEMINI": no_ack})
        got = CourierSafetyDispatcher(self.root, boundary).submit_task("w", {"capability_request": "code", "name": "x"})
        self.assertEqual(got["status"], "FAIL_CLOSED")
        self.assertIn("ACK", got["reason"])

    def test_mismatched_ack_fails_closed(self):
        def forged(task):
            value = deterministic_consumer(task); value["ack"]["task_hash"] = "forged"; return value
        got = CourierSafetyDispatcher(self.root, LocalWorkerAdapterBoundary(self.root, {"GEMINI": forged})).submit_task("w", {"capability_request": "code", "name": "x"})
        self.assertEqual(got["status"], "FAIL_CLOSED")

    def test_missing_or_tampered_result_fails_closed(self):
        for mutation in ("missing", "tampered"):
            def bad(task, mutation=mutation):
                value = deterministic_consumer(task)
                if mutation == "missing": value.pop("result")
                else: value["result"]["payload"]["outcome"] = "changed"
                return value
            got = CourierSafetyDispatcher(self.root, LocalWorkerAdapterBoundary(self.root, {"GEMINI": bad})).submit_task("w", {"capability_request": "code", "name": mutation})
            self.assertEqual(got["status"], "FAIL_CLOSED")

    def test_recursive_safety_matrix(self):
        unsafe = [
            {"payload": {"nested": {"external_action": True}}}, {"action": "WITHDRAW"},
            {"payload": [{"spend_eur": "10"}]}, {"real_spend_eur": float("nan")},
            {"payment": {"mode": "LIVE"}}, {"nested": {"publish": True}},
            {"customer_contact": {"send": True}}, {"wallet_signing": True},
            {"account_rotation": True}, {"trade_mode": "LIVE"}, {"real_trades": 1},
            {"nested": {"operation": "TRANSFER"}},
        ]
        for case in unsafe:
            with self.subTest(case=case):
                self.assertEqual(self.dispatcher.submit_task("w", case)["status"], "FAIL_CLOSED")

    def test_zero_spend_safe(self):
        self.assertEqual(self.dispatcher.submit_task("w", {"capability_request": "code", "name": "safe", "spend_eur": 0})["status"], "EXECUTED")

    def test_two_dispatcher_instances_share_heavy_lease(self):
        first = self.dispatcher.submit_task("w1", {"capability_request": "code", "name": "h1", "is_heavy": True})
        second = CourierSafetyDispatcher(self.root, LocalWorkerAdapterBoundary(self.root, {"GEMINI": deterministic_consumer}))
        blocked = second.submit_task("w2", {"capability_request": "code", "name": "h2", "is_heavy": True})
        self.assertEqual(first["status"], "EXECUTED")
        self.assertEqual(blocked, {"status": "QUEUED", "reason": "HEAVY_JOB_LIMIT_EXCEEDED"})

    def test_multiprocess_heavy_lease_single_winner(self):
        context = multiprocessing.get_context("spawn")
        start, output = context.Event(), context.Queue()
        processes = [context.Process(target=heavy_claim_process, args=(str(self.root), f"w{i}", start, output)) for i in range(2)]
        for process in processes: process.start()
        start.set()
        statuses = [output.get(timeout=10) for _ in processes]
        for process in processes: process.join(10)
        self.assertEqual(statuses.count("EXECUTED"), 1)
        self.assertEqual(statuses.count("QUEUED"), 1)

    def test_heavy_released_only_after_matching_verification(self):
        first = self.dispatcher.submit_task("w1", {"capability_request": "code", "name": "h1", "is_heavy": True})
        self.assertEqual(self.dispatcher.verify_result("wrong", first["task_hash"], "PASS", self.result(first)), "FAIL_CLOSED")
        self.assertTrue(TaskLeaseManager(self.root).is_task_claimed("global_heavy_job_lease"))
        self.assertEqual(self.dispatcher.verify_result("w1", first["task_hash"], "PASS", self.result(first)), "VERIFIED_AND_CACHED")
        self.assertFalse(TaskLeaseManager(self.root).is_task_claimed("global_heavy_job_lease"))

    def test_verify_before_next_and_unverified_not_cached(self):
        first = self.dispatcher.submit_task("w1", {"capability_request": "code", "name": "first"})
        self.assertEqual(self.dispatcher.submit_task("w2", {"capability_request": "code", "name": "next"})["status"], "BLOCKED")
        self.assertIsNone(self.dispatcher.ledger.get_reviewed_entry(first["task_hash"]))
        self.assertEqual(self.dispatcher.verify_result("w1", first["task_hash"], "FAIL", self.result(first)), "FAIL_CLOSED")
        self.assertIsNone(self.dispatcher.ledger.get_reviewed_entry(first["task_hash"]))

    def test_verified_result_cached_and_deduped(self):
        first = self.dispatcher.submit_task("w1", {"capability_request": "code", "name": "cache"})
        self.assertEqual(self.dispatcher.verify_result("w1", first["task_hash"], "PASS", self.result(first)), "VERIFIED_AND_CACHED")
        restarted = CourierSafetyDispatcher(self.root)
        self.assertEqual(restarted.submit_task("w2", {"capability_request": "code", "name": "cache"})["status"], "DEDUPED")

    def test_wrong_result_or_worker_not_cached(self):
        first = self.dispatcher.submit_task("w1", {"capability_request": "code", "name": "wrong"})
        wrong = dict(self.result(first)); wrong["payload"] = {"outcome": "forged"}
        self.assertEqual(self.dispatcher.verify_result("w1", first["task_hash"], "PASS", wrong), "FAIL_CLOSED")
        self.assertIsNone(self.dispatcher.ledger.get_reviewed_entry(first["task_hash"]))

    def test_dispatch_exception_releases_leases_and_blocks_next(self):
        dispatcher = CourierSafetyDispatcher(self.root, FailingBoundary(self.root))
        got = dispatcher.submit_task("w", {"capability_request": "code", "name": "x", "requires_write": True, "is_heavy": True})
        self.assertEqual(got["status"], "FAIL_CLOSED")
        self.assertFalse(TaskLeaseManager(self.root).is_task_claimed("global_writer_lease"))
        self.assertFalse(TaskLeaseManager(self.root).is_task_claimed("global_heavy_job_lease"))
        self.assertEqual(dispatcher.submit_task("w", {"capability_request": "code", "name": "next"})["status"], "BLOCKED")




    def test_intent_aware_human_gate(self):
        mission_positive = {"goal": "Please login to the server and do stuff."}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission_positive, {}))

        mission_negative = {"goal": "Do your work. NO login allowed. Avoid autonomous purchase."}
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission_negative, {}))

        mission_mixed = {
            "goal": "Go ahead and process the queue. "
                    "SAFETY / EXTERNAL BOUNDARIES: NO publication. "
                    "HUMAN_GATE remains required for: login, oauth, publication. "
        }
        self.assertFalse(CourierSafetyDispatcher._requires_human_gate(mission_mixed, {}))

        mission_ambiguous = {"goal": "I need you to handle publication of the new module."}
        self.assertTrue(CourierSafetyDispatcher._requires_human_gate(mission_ambiguous, {}))

    def test_mission_queue_lock_is_exclusive_and_crash_stale_marker_is_reusable(self):
        queue = MissionQueue(self.root)
        lock_fd = queue._lock()
        try:
            with self.assertRaisesRegex(RuntimeError, "MISSION_QUEUE_BUSY_FAIL_CLOSED"):
                MissionQueue(self.root).enqueue({"mission_id": "busy", "goal": "must not race"})
        finally:
            queue._unlock(lock_fd)

        # The rendezvous file deliberately survives. A crashed process cannot leave
        # stale authority because the kernel releases its flock on process exit.
        self.assertTrue(queue.lock_file.exists())
        stored = MissionQueue(self.root).enqueue({"mission_id": "recovered", "goal": "resume safely"})
        self.assertEqual(stored["status"], "PENDING")

if __name__ == "__main__":
    unittest.main()

    def test_identity_path_executes_without_nameerror(self):
        from scripts.courier_safety_dispatcher import TaskEnvelope, LocalWorkerAdapterBoundary
        env = TaskEnvelope(
            task_hash="th", worker_id="w", target_agent="GEMINI", capability="code",
            requires_write=False, is_heavy=False, verification_required=True,
            safety_decision="APPROVED", payload={}, correlation_id="cor1", task_id="tid1",
            mission_id="m1"
        )
        res = LocalWorkerAdapterBoundary._identity("ACK", "ACCEPTED", env)
        self.assertEqual(res["correlation_id"], "cor1")
        self.assertEqual(res["task_id"], "tid1")
