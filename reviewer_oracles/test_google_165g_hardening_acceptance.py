"""Focused independent safety probes for the Google 165G dispatcher delta."""

import datetime
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import two_computer_dispatcher as implementation


NOW = datetime.datetime.now(datetime.timezone.utc)


def _race_claim(root, node_id, task_id, barrier, results):
    dispatcher = implementation.TwoComputerDispatcher(
        transport=implementation.LocalDurableTransportAdapter(Path(root))
    )
    barrier.wait(5)
    accepted, _, lease = dispatcher.claim_task_lease(node_id, task_id)
    results.put((node_id, accepted, lease.lease_id if lease else None))


class FailOnSecondClaimWrite(implementation.LocalDurableTransportAdapter):
    def __init__(self, root_dir):
        super().__init__(root_dir)
        self.claim_writes = 0
        self.enabled = False

    def write_json(self, rel_path, data):
        if self.enabled:
            self.claim_writes += 1
            if self.claim_writes == 2:
                raise RuntimeError("injected persistence interruption")
        return super().write_json(rel_path, data)


class Google165GHardeningAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "cluster"
        self.transport = implementation.LocalDurableTransportAdapter(self.root)
        self.dispatcher = implementation.TwoComputerDispatcher(transport=self.transport, lease_duration_seconds=30)
        self.dispatcher.register_node("NODE_A", "a", "darwin", "/node-a", "/node-a", resource_pool="GOOGLE_PRO_POOL_1")
        self.dispatcher.register_node("NODE_B", "b", "darwin", "/node-b", "/node-b", resource_pool="GOOGLE_PRO_POOL_1")

    def tearDown(self):
        self.temp.cleanup()

    def _expire(self, lease_id):
        leases = self.transport.read_json("active_leases.json")
        leases["leases"][lease_id]["expires_at"] = (NOW - datetime.timedelta(minutes=1)).isoformat()
        self.transport.write_json("active_leases.json", leases)

    def test_real_multiprocess_race_has_one_authoritative_winner(self):
        task = self.dispatcher.submit_task("race", "TEST", ["tests/race/"])
        barrier, results = multiprocessing.Barrier(2), multiprocessing.Queue()
        workers = [
            multiprocessing.Process(target=_race_claim, args=(str(self.root), node, task.task_id, barrier, results))
            for node in ("NODE_A", "NODE_B")
        ]
        for worker in workers: worker.start()
        for worker in workers: worker.join(10)
        outcomes = [results.get(timeout=2) for _ in workers]
        self.assertEqual(1, sum(accepted for _, accepted, _ in outcomes))
        self.assertEqual(1, len(self.dispatcher.get_active_leases()))

    def test_expiry_without_evidence_is_fail_closed(self):
        task = self.dispatcher.submit_task("uncertain", "REMEDIATION", ["scripts/uncertain/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        self._expire(lease.lease_id)
        self.dispatcher.reconcile_expired_leases()
        self.assertEqual("RECONCILIATION_REQUIRED", self.dispatcher.get_task(task.task_id).status)

    def test_claim_crash_can_split_lease_and_task_state(self):
        root = Path(self.temp.name) / "fault-cluster"
        transport = FailOnSecondClaimWrite(root)
        dispatcher = implementation.TwoComputerDispatcher(transport=transport)
        dispatcher.register_node("NODE_A", "a", "darwin", "/a", "/a")
        task = dispatcher.submit_task("fault", "TEST", ["tests/fault/"])
        transport.enabled = True
        with self.assertRaises(RuntimeError):
            dispatcher.claim_task_lease("NODE_A", task.task_id)
        self.assertEqual("READY", dispatcher.get_task(task.task_id).status)
        self.assertEqual(1, len(dispatcher.get_active_leases()))

    def test_forged_matching_task_and_lease_result_finalizes_expiry(self):
        task = self.dispatcher.submit_task("expiry", "TEST", ["tests/expiry/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        forged = {
            "result_id": "FORGED", "task_id": task.task_id, "node_id": "NODE_B",
            "lease_id": lease.lease_id, "status": "SUCCESS",
        }
        self.transport.write_json("results/FORGED.json", forged)
        self._expire(lease.lease_id)
        self.dispatcher.reconcile_expired_leases()
        self.assertEqual("COMPLETE", self.dispatcher.get_task(task.task_id).status)

    def test_unverified_boolean_allows_safe_requeue(self):
        task = self.dispatcher.submit_task("requeue", "TEST", ["tests/requeue/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        self._expire(lease.lease_id)
        self.dispatcher.reconcile_expired_leases({lease.lease_id: {"safe_to_requeue": True, "reason": "unverified"}})
        self.assertEqual("READY", self.dispatcher.get_task(task.task_id).status)

    def test_same_result_id_with_changed_content_is_accepted(self):
        task = self.dispatcher.submit_task("result", "TEST", ["tests/result/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        result = implementation.WorkerResultRecord(
            result_id="RESULT-ONE", task_id=task.task_id, node_id="NODE_A", lease_id=lease.lease_id,
            status="SUCCESS", started_at=NOW.isoformat(), finished_at=NOW.isoformat(), summary="original",
        )
        with patch.object(implementation, "RESULTS_DIR", self.root / "results"):
            self.assertTrue(self.dispatcher.ingest_worker_result(result)[0])
            altered = implementation.WorkerResultRecord(
                result_id="RESULT-ONE", task_id=task.task_id, node_id="NODE_B", lease_id="different",
                status="SUCCESS", started_at=NOW.isoformat(), finished_at=NOW.isoformat(), summary="altered",
            )
            self.assertTrue(self.dispatcher.ingest_worker_result(altered)[0])


if __name__ == "__main__":
    unittest.main()
