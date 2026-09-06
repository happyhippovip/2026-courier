"""Read-only acceptance probes for the current Google 161G delta.

The tests use a temporary LocalDurableTransportAdapter.  They are deliberately
written to detect unsafe current behavior rather than normalize it as passing.
"""

import datetime
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import two_computer_dispatcher as implementation


class Google161GDeltaAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transport = implementation.LocalDurableTransportAdapter(self.root / "cluster")
        self.dispatcher = implementation.TwoComputerDispatcher(
            transport=self.transport, heartbeat_stale_seconds=1.0, lease_duration_seconds=30.0
        )
        self.dispatcher.register_node("NODE_A", "a", "darwin", "/node-a", "/node-a", resource_pool="GOOGLE_PRO_POOL_1")
        self.dispatcher.register_node("NODE_B", "b", "darwin", "/node-b", "/node-b", resource_pool="GOOGLE_PRO_POOL_2")

    def tearDown(self):
        self.temp.cleanup()

    def test_expiry_immediately_requeues_task_without_worker_reconciliation(self):
        task = self.dispatcher.submit_task("mutable work", "REMEDIATION", ["scripts/router/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        leases = self.transport.read_json("active_leases.json")
        leases["leases"][lease.lease_id]["expires_at"] = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        ).isoformat()
        self.transport.write_json("active_leases.json", leases)
        self.dispatcher.reconcile_expired_leases()
        self.assertEqual("READY", self.dispatcher.get_task(task.task_id).status)

    def test_mismatched_result_is_accepted_and_can_complete_a_task(self):
        task = self.dispatcher.submit_task("mutable work", "REMEDIATION", ["scripts/router/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        result = implementation.WorkerResultRecord(
            result_id="MISMATCHED", task_id=task.task_id, node_id="NODE_B", lease_id="wrong-lease",
            status="SUCCESS", started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), summary="unsafe", next_state="IDLE",
        )
        with patch.object(implementation, "RESULTS_DIR", self.root / "results"):
            accepted, _ = self.dispatcher.ingest_worker_result(result)
        self.assertTrue(accepted)
        self.assertEqual("COMPLETE", self.dispatcher.get_task(task.task_id).status)
        self.assertEqual("ACTIVE", self.transport.read_json("active_leases.json")["leases"][lease.lease_id]["status"])

    def test_malformed_heartbeat_raises_instead_of_failing_closed(self):
        registry = self.transport.read_json("node_registry.json")
        registry["nodes"]["NODE_A"]["last_heartbeat"] = "invalid"
        self.transport.write_json("node_registry.json", registry)
        with self.assertRaises(ValueError):
            self.dispatcher.reconcile_stale_nodes()

    def test_pool_four_is_claimable_despite_not_configured_label(self):
        self.dispatcher.register_node("NODE_POOL4", "p4", "darwin", "/p4", "/p4", resource_pool="GOOGLE_PRO_POOL_4_NOT_CONFIGURED")
        task = self.dispatcher.submit_task(
            "pool four", "AUDIT", ["tests/pool4/"], required_resource_pool="GOOGLE_PRO_POOL_4_NOT_CONFIGURED"
        )
        accepted, _, _ = self.dispatcher.claim_task_lease("NODE_POOL4", task.task_id)
        self.assertTrue(accepted)

    def test_claim_path_has_no_atomic_locking_primitive(self):
        source = inspect.getsource(implementation.TwoComputerDispatcher.claim_task_lease)
        self.assertNotIn("O_EXCL", source)
        self.assertNotIn("flock", source)
        self.assertNotIn("Lock(", source)

    def test_scope_normalizer_accepts_traversal_and_absolute_paths(self):
        self.assertEqual("/scripts/../outside", implementation.ScopeLockManager.normalize_path("scripts/../outside"))
        self.assertEqual("/absolute/path", implementation.ScopeLockManager.normalize_path("/absolute/path"))


if __name__ == "__main__":
    unittest.main()
