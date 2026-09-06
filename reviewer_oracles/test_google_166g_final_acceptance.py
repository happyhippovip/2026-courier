"""Adversarial, read-only acceptance probes for the 166G dispatcher delta.

The probes use only temporary cluster directories.  They intentionally record
whether the production implementation currently accepts unsafe state; a green
test here is evidence of the observed behavior, not an acceptance approval.
"""

import datetime
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from scripts import two_computer_dispatcher as impl


def _claim_worker(root, node_id, task_id, queue):
    dispatcher = impl.TwoComputerDispatcher(impl.LocalDurableTransportAdapter(Path(root)))
    accepted, _, lease = dispatcher.claim_task_lease(node_id, task_id)
    queue.put((accepted, lease.lease_id if lease else None))


class FailAfterClaimWrites(impl.LocalDurableTransportAdapter):
    def __init__(self, root_dir, fail_after):
        super().__init__(root_dir)
        self.enabled = False
        self.writes = 0
        self.fail_after = fail_after

    def write_json(self, rel_path, data):
        if self.enabled:
            self.writes += 1
            if self.writes > self.fail_after:
                raise RuntimeError("injected claim persistence crash")
        return super().write_json(rel_path, data)


class Google166GFinalAcceptanceProbes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "cluster"
        self.transport = impl.LocalDurableTransportAdapter(self.root)
        self.dispatcher = impl.TwoComputerDispatcher(self.transport, lease_duration_seconds=30)
        for node_id in ("NODE_A", "NODE_B"):
            self.dispatcher.register_node(node_id, node_id, "darwin", "/workspace", "/worktree")

    def tearDown(self):
        self.temp.cleanup()

    def _expire(self, lease_id):
        leases = self.transport.read_json("active_leases.json")
        leases["leases"][lease_id]["expires_at"] = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        ).isoformat()
        self.transport.write_json("active_leases.json", leases)

    def test_multiprocess_claim_still_has_exactly_one_winner(self):
        task = self.dispatcher.submit_task("race", "TEST", ["review/race/"])
        queue = multiprocessing.Queue()
        workers = [
            multiprocessing.Process(target=_claim_worker, args=(str(self.root), node, task.task_id, queue))
            for node in ("NODE_A", "NODE_B")
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
        outcomes = [queue.get(timeout=2) for _ in workers]
        self.assertEqual(1, sum(accepted for accepted, _ in outcomes))
        self.assertEqual(1, len(self.dispatcher.get_active_leases()))

    def test_expiry_accepts_matching_identity_with_unverified_digest(self):
        task = self.dispatcher.submit_task("forged result", "TEST", ["review/result/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        forged = {
            "result_id": "forged-matching-identity",
            "task_id": task.task_id,
            "node_id": "NODE_A",
            "lease_id": lease.lease_id,
            "status": "SUCCESS",
            "result_digest": "not-a-recomputed-canonical-digest",
        }
        self.transport.write_json("results/forged-matching-identity.json", forged)
        self._expire(lease.lease_id)
        self.dispatcher.reconcile_expired_leases()
        self.assertEqual("COMPLETE", self.dispatcher.get_task(task.task_id).status)

    def test_matching_caller_evidence_can_requeue_without_authority_verification(self):
        task = self.dispatcher.submit_task("forged evidence", "TEST", ["review/evidence/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        self._expire(lease.lease_id)
        caller_constructed = {
            "evidence_id": "caller-controlled",
            "task_id": task.task_id,
            "lease_id": lease.lease_id,
            "node_id": "NODE_A",
            "evidence_class": "EXECUTION_NEVER_STARTED_PROVEN",
        }
        self.dispatcher.reconcile_expired_leases({lease.lease_id: caller_constructed})
        self.assertEqual("READY", self.dispatcher.get_task(task.task_id).status)

    def test_crash_after_task_write_leaves_prepared_transaction_as_active_claim(self):
        root = Path(self.temp.name) / "crash-cluster"
        fault = FailAfterClaimWrites(root, fail_after=3)  # journal, lease, task; fail node write
        dispatcher = impl.TwoComputerDispatcher(fault)
        dispatcher.register_node("NODE_A", "a", "darwin", "/a", "/a")
        task = dispatcher.submit_task("crash", "TEST", ["review/crash/"])
        fault.enabled = True
        with self.assertRaises(RuntimeError):
            dispatcher.claim_task_lease("NODE_A", task.task_id)
        recovered = impl.TwoComputerDispatcher(impl.LocalDurableTransportAdapter(root))
        recovered_task = recovered.get_task(task.task_id)
        active = recovered.get_active_leases()
        transactions = recovered.transport.read_json("claim_transactions.json")["transactions"]
        self.assertEqual("LEASED", recovered_task.status)
        self.assertEqual(1, len(active))
        self.assertEqual("PREPARED", next(iter(transactions.values()))["status"])


if __name__ == "__main__":
    unittest.main()
