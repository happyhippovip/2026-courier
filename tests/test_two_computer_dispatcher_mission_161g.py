#!/usr/bin/env python3
"""Unit, Concurrency & Crash Tests for Hardened Two-Computer Dispatcher (Mission 161G, 165G & 166G).

Validates all required acceptance conditions:
1. Node registration
2. Unique node IDs & resource pool isolation
3. Heartbeat
4. Stale heartbeat detection
5. Task lease acquisition
6. Double-claim rejection
7. Real multi-process concurrent claim race (WINNERS == 1, LOSERS == N-1)
8. Crash injection: crash after lease write rolls back split-brain lease on recovery
9. Crash injection: crash before commit marker is deterministically rolled back
10. Fail-closed lease expiry with uncertain worker (NO redispatch, RECONCILIATION_REQUIRED)
11. Caller boolean safe_to_requeue rejected (requires durable authoritative evidence)
12. Timeout / missing heartbeat / restart alone cannot requeue
13. Valid authoritative SafeRequeueEvidenceRecord resets task to READY
14. Forged / mismatched SafeRequeueEvidenceRecord is rejected
15. Expiry reconciliation with matching authoritative completion result (finalizes COMPLETE)
16. Expiry reconciliation with forged wrong-node result REJECTED (no completion, no scope release)
17. Strict result validation: wrong task_id rejected
18. Strict result validation: wrong node_id rejected
19. Strict result validation: wrong lease_id rejected
20. Strict result validation: stale/released lease rejected
21. Result idempotency: identical result with matching SHA-256 digest accepted idempotently
22. Result idempotency: same result_id with altered payload/summary REJECTED
23. Result idempotency: same result_id with altered node_id REJECTED
24. Result idempotency: same result_id with altered lease_id REJECTED
25. Scope lock protection: mismatched result CANNOT release scope lock
26. Node state isolation: mismatched result CANNOT mutate node state
27. Scope non-overlap concurrency allowed
28. Heavy-job limit enforcement (HEAVY_JOB_LIMIT = 1)
29. Resource pool routing & mismatch rejection
30. Restart recovery: active leases and uncertain expired leases preserved
31. Completed task cannot be redispatched
32. Zero credentials / secrets stored.
"""

from __future__ import annotations

import datetime
import json
import multiprocessing
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.two_computer_dispatcher import (
    LocalDurableTransportAdapter, SafeRequeueEvidenceRecord, ScopeLockManager,
    TwoComputerDispatcher, WorkerResultRecord, compute_evidence_digest,
    compute_result_digest,
)

COURIER_DIR = Path(__file__).resolve().parent.parent


def _concurrent_claim_worker(
    cluster_dir_str: str, node_id: str, task_id: str, results_queue: multiprocessing.Queue
) -> None:
    transport = LocalDurableTransportAdapter(root_dir=Path(cluster_dir_str))
    dispatcher = TwoComputerDispatcher(transport=transport)
    success, msg, lease = dispatcher.claim_task_lease(node_id, task_id)
    results_queue.put((node_id, success, msg, lease.lease_id if lease else None))


class CrashInjectingTransportAdapter(LocalDurableTransportAdapter):
    """Transport adapter that injects failures after a specified number of writes."""

    def __init__(self, root_dir: Path, fail_after_writes: int):
        super().__init__(root_dir)
        self.fail_after_writes = fail_after_writes
        self.write_count = 0
        self.enabled = False

    def write_json(self, rel_path: str, data: dict) -> None:
        if self.enabled:
            self.write_count += 1
            if self.write_count > self.fail_after_writes:
                raise RuntimeError(f"Simulated crash after {self.fail_after_writes} writes on {rel_path}")
        return super().write_json(rel_path, data)


class TestTwoComputerDispatcherHardened(unittest.TestCase):
    """Test suite validating two-computer control-plane mechanics with 166G hardening."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cluster_dir = Path(self.tmp_dir.name)
        self.transport = LocalDurableTransportAdapter(root_dir=self.cluster_dir)
        self.dispatcher = TwoComputerDispatcher(
            transport=self.transport,
            heartbeat_stale_seconds=5.0,
            lease_duration_seconds=10.0,
        )

        # Register Node A and Node B baseline
        self.node_a = self.dispatcher.register_node(
            node_id="NODE_A",
            hostname="macbook-a",
            platform="darwin",
            workspace_path="/Users/user/Downloads/2026-courier",
            worktree_path="/Users/user/Downloads/2026-courier",
            capabilities=["local_compute", "python_test", "creator_pipeline", "visual_qc"],
            resource_pool="GOOGLE_PRO_POOL_1",
        )
        self.node_b = self.dispatcher.register_node(
            node_id="NODE_B",
            hostname="macbook-b",
            platform="darwin",
            workspace_path="/Users/user/Downloads/2026-courier",
            worktree_path="/Users/user/Downloads/2026-courier-node-b",
            capabilities=["local_compute", "python_test", "visual_qc"],
            resource_pool="GOOGLE_PRO_POOL_2",
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_node_registration(self):
        nodes = self.dispatcher.list_nodes()
        self.assertEqual(len(nodes), 2)
        node_ids = {n.node_id for n in nodes}
        self.assertIn("NODE_A", node_ids)
        self.assertIn("NODE_B", node_ids)

    def test_02_unique_node_ids_and_pool_isolation(self):
        node_a = self.dispatcher.get_node("NODE_A")
        node_b = self.dispatcher.get_node("NODE_B")
        self.assertIsNotNone(node_a)
        self.assertIsNotNone(node_b)
        self.assertNotEqual(node_a.node_id, node_b.node_id)
        self.assertEqual(node_a.resource_pool, "GOOGLE_PRO_POOL_1")
        self.assertEqual(node_b.resource_pool, "GOOGLE_PRO_POOL_2")

    def test_03_heartbeat(self):
        updated = self.dispatcher.heartbeat("NODE_A", status="READY", continuation_state="IDLE")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, "READY")
        self.assertEqual(updated.continuation_state, "IDLE")

    def test_04_stale_heartbeat_detection(self):
        reg = self.transport.read_json("node_registry.json")
        past_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=20.0)).isoformat()
        reg["nodes"]["NODE_B"]["last_heartbeat"] = past_time
        self.transport.write_json("node_registry.json", reg)

        stale_nodes = self.dispatcher.reconcile_stale_nodes()
        self.assertIn("NODE_B", stale_nodes)
        node_b = self.dispatcher.get_node("NODE_B")
        self.assertEqual(node_b.status, "OFFLINE")

    def test_05_task_lease_acquisition(self):
        task = self.dispatcher.submit_task(
            title="Run Unit Tests",
            task_type="TEST",
            file_scope=["tests/unit/"],
            priority=1,
        )
        success, msg, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        self.assertTrue(success)
        self.assertIsNotNone(lease)
        self.assertEqual(lease.node_id, "NODE_A")
        self.assertEqual(lease.task_id, task.task_id)

        node_a = self.dispatcher.get_node("NODE_A")
        self.assertEqual(node_a.status, "ACTIVE")
        self.assertEqual(node_a.current_task_id, task.task_id)

    def test_06_double_claim_rejection(self):
        task = self.dispatcher.submit_task(
            title="Shared Build Task",
            task_type="BUILD",
            file_scope=["scripts/build/"],
        )
        ok_a, _, _ = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        self.assertTrue(ok_a)

        ok_b, msg_b, lease_b = self.dispatcher.claim_task_lease("NODE_B", task.task_id)
        self.assertFalse(ok_b)
        self.assertIsNone(lease_b)
        self.assertIn("ALREADY_CLAIMED", msg_b)

    def test_07_real_multiprocess_concurrent_claim_race(self):
        task = self.dispatcher.submit_task(
            title="Contended Task",
            task_type="TEST",
            file_scope=["contended/"],
        )
        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(
            target=_concurrent_claim_worker, args=(str(self.cluster_dir), "NODE_A", task.task_id, q)
        )
        p2 = multiprocessing.Process(
            target=_concurrent_claim_worker, args=(str(self.cluster_dir), "NODE_B", task.task_id, q)
        )

        p1.start()
        p2.start()
        p1.join(timeout=5.0)
        p2.join(timeout=5.0)

        results = []
        while not q.empty():
            results.append(q.get())

        self.assertEqual(len(results), 2)
        winners = [r for r in results if r[1] is True]
        losers = [r for r in results if r[1] is False]

        self.assertEqual(len(winners), 1, "Exactly one process must win the lease")
        self.assertEqual(len(losers), 1, "Exactly one process must lose the lease")

        active_leases = self.dispatcher.get_active_leases()
        self.assertEqual(len(active_leases), 1)
        self.assertEqual(active_leases[0].task_id, task.task_id)

    def test_08_crash_after_lease_write_reconciles_split_brain(self):
        crash_transport = CrashInjectingTransportAdapter(self.cluster_dir, fail_after_writes=2)
        crash_dispatcher = TwoComputerDispatcher(transport=crash_transport)
        task = crash_dispatcher.submit_task(title="Crash Task", task_type="TEST", file_scope=["crash/"])

        crash_transport.enabled = True
        with self.assertRaises(RuntimeError):
            crash_dispatcher.claim_task_lease("NODE_A", task.task_id)

        # In recovery, the split-brain lease must be rolled back
        recovered_dispatcher = TwoComputerDispatcher(transport=self.transport)
        recovered_task = recovered_dispatcher.get_task(task.task_id)
        self.assertEqual(recovered_task.status, "READY")
        # No orphan active leases
        self.assertEqual(len(recovered_dispatcher.get_active_leases()), 0)

    def test_09_crash_before_commit_is_deterministically_recovered(self):
        crash_transport = CrashInjectingTransportAdapter(self.cluster_dir, fail_after_writes=3)
        crash_dispatcher = TwoComputerDispatcher(transport=crash_transport)
        task = crash_dispatcher.submit_task(title="Pre-commit Crash", task_type="TEST", file_scope=["precommit/"])

        crash_transport.enabled = True
        with self.assertRaises(RuntimeError):
            crash_dispatcher.claim_task_lease("NODE_A", task.task_id)

        # After recovery, state remains coherent
        rec = self.dispatcher.recover_after_restart()
        self.assertEqual(rec["recovery_status"], "RECOVERED")

    def test_10_fail_closed_lease_expiry_uncertain_worker(self):
        task = self.dispatcher.submit_task(
            title="Uncertain Long Task",
            task_type="RENDER",
            file_scope=["runtime/uncertain/"],
        )
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        # Backdate lease expiry
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        reconciled = self.dispatcher.reconcile_expired_leases()
        self.assertIn(lease.lease_id, reconciled)

        # CRITICAL: Task must NOT be READY. Must be RECONCILIATION_REQUIRED.
        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "RECONCILIATION_REQUIRED")
        self.assertNotEqual(updated_task.status, "READY")

        # Node A remains blocked until reconciled
        node_a = self.dispatcher.get_node("NODE_A")
        self.assertEqual(node_a.status, "BLOCKED")

    def test_11_caller_boolean_safe_to_requeue_rejected(self):
        task = self.dispatcher.submit_task(
            title="Raw Boolean Task", task_type="AUDIT", file_scope=["audit/raw/"]
        )
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        # Backdate expiry
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        # Pass raw unproven boolean dictionary -> Must be REJECTED and remain RECONCILIATION_REQUIRED
        self.dispatcher.reconcile_expired_leases({lease.lease_id: {"safe_to_requeue": True, "reason": "unverified"}})
        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "RECONCILIATION_REQUIRED")

    def test_12_timeout_missing_heartbeat_restart_alone_cannot_requeue(self):
        task = self.dispatcher.submit_task(
            title="Timeout Task", task_type="AUDIT", file_scope=["audit/to/"]
        )
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        # Backdate expiry and make heartbeat stale
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        reg = self.transport.read_json("node_registry.json")
        reg["nodes"]["NODE_A"]["last_heartbeat"] = past_exp
        self.transport.write_json("node_registry.json", reg)

        # Reconcile on restart
        self.dispatcher.recover_after_restart()
        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "RECONCILIATION_REQUIRED")

    def test_13_valid_authoritative_safe_requeue_evidence_accepted(self):
        task = self.dispatcher.submit_task(
            title="Clean Termination Task", task_type="AUDIT", file_scope=["audit/clean/"]
        )
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        # Backdate expiry
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        # Provide authoritative verified SafeRequeueEvidenceRecord
        ev = SafeRequeueEvidenceRecord(
            evidence_id="EV-CLEAN-001",
            task_id=task.task_id,
            lease_id=lease.lease_id,
            node_id="NODE_A",
            evidence_class="AUTHORITATIVE_WORKER_ABORT_BEFORE_MUTATION",
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        ev_dict = {
            "evidence_id": ev.evidence_id,
            "task_id": ev.task_id,
            "lease_id": ev.lease_id,
            "node_id": ev.node_id,
            "evidence_class": ev.evidence_class,
            "evidence_digest": compute_evidence_digest(ev),
        }
        reconciled = self.dispatcher.reconcile_expired_leases(safe_requeue_evidence={lease.lease_id: ev_dict})
        self.assertIn(lease.lease_id, reconciled)

        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "READY")
        node_a = self.dispatcher.get_node("NODE_A")
        self.assertEqual(node_a.status, "READY")

    def test_14_forged_safe_requeue_evidence_rejected(self):
        task = self.dispatcher.submit_task(
            title="Forged Ev Task", task_type="AUDIT", file_scope=["audit/forged/"]
        )
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        # Backdate expiry
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        # Forged evidence with wrong node_id
        forged_ev = {
            "evidence_id": "EV-FORGED",
            "task_id": task.task_id,
            "lease_id": lease.lease_id,
            "node_id": "NODE_B",  # Wrong node!
            "evidence_class": "AUTHORITATIVE_WORKER_ABORT_BEFORE_MUTATION",
        }
        self.dispatcher.reconcile_expired_leases(safe_requeue_evidence={lease.lease_id: forged_ev})
        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "RECONCILIATION_REQUIRED")

    def test_15_expired_lease_with_matching_completion_result(self):
        task = self.dispatcher.submit_task(
            title="Finished Before Reconcile", task_type="TEST", file_scope=["tests/done/"]
        )
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        res = WorkerResultRecord(
            result_id="RES-MATCH-001",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            summary="Completed successfully",
        )
        res_dict = res.__dict__.copy()
        res_dict["result_digest"] = compute_result_digest(res)
        self.transport.write_json(f"results/{res.result_id}.json", res_dict)

        # Backdate lease expiry
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        self.dispatcher.reconcile_expired_leases()
        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "COMPLETE")
        self.assertEqual(updated_task.result_id, "RES-MATCH-001")

    def test_16_forged_wrong_node_expiry_result_rejected(self):
        task = self.dispatcher.submit_task(title="Expiry Forgery", task_type="TEST", file_scope=["tests/forged/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        # Forged result with matching task_id and lease_id but node_id = NODE_B
        forged = {
            "result_id": "FORGED-RESULT",
            "task_id": task.task_id,
            "node_id": "NODE_B",  # Wrong node!
            "lease_id": lease.lease_id,
            "status": "SUCCESS",
        }
        self.transport.write_json("results/FORGED-RESULT.json", forged)

        # Backdate expiry
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][lease.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        self.dispatcher.reconcile_expired_leases()
        updated_task = self.dispatcher.get_task(task.task_id)
        # CRITICAL: Must be RECONCILIATION_REQUIRED, NOT COMPLETE!
        self.assertEqual(updated_task.status, "RECONCILIATION_REQUIRED")
        self.assertNotEqual(updated_task.status, "COMPLETE")

    def test_17_strict_result_validation_wrong_task_id(self):
        task = self.dispatcher.submit_task(title="Real Task", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        bad_res = WorkerResultRecord(
            result_id="RES-WRONG-TASK",
            task_id="NON_EXISTENT_TASK",
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        ok, msg = self.dispatcher.ingest_worker_result(bad_res)
        self.assertFalse(ok)
        self.assertIn("not found in task queue", msg)

    def test_18_strict_result_validation_wrong_node_id(self):
        task = self.dispatcher.submit_task(title="Real Task", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        bad_res = WorkerResultRecord(
            result_id="RES-FORGED-NODE",
            task_id=task.task_id,
            node_id="NODE_B",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        ok, msg = self.dispatcher.ingest_worker_result(bad_res)
        self.assertFalse(ok)
        self.assertIn("Mismatched node_id", msg)

        updated_task = self.dispatcher.get_task(task.task_id)
        self.assertEqual(updated_task.status, "LEASED")
        node_a = self.dispatcher.get_node("NODE_A")
        self.assertEqual(node_a.status, "ACTIVE")

    def test_19_strict_result_validation_wrong_lease_id(self):
        task = self.dispatcher.submit_task(title="Real Task", task_type="AUDIT", file_scope=["docs/"])
        self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        bad_res = WorkerResultRecord(
            result_id="RES-WRONG-LEASE",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id="fake-lease-9999",
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        ok, msg = self.dispatcher.ingest_worker_result(bad_res)
        self.assertFalse(ok)
        self.assertIn("not found in active leases", msg)

    def test_20_strict_result_validation_stale_lease(self):
        task = self.dispatcher.submit_task(title="Real Task", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        valid_res = WorkerResultRecord(
            result_id="RES-VALID",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self.dispatcher.ingest_worker_result(valid_res)

        stale_res = WorkerResultRecord(
            result_id="RES-STALE",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        ok, msg = self.dispatcher.ingest_worker_result(stale_res)
        self.assertFalse(ok)
        self.assertIn("Conflicting or altered second result", msg)

    def test_21_result_idempotency_identical_canonical_digest(self):
        task = self.dispatcher.submit_task(title="Idempotent Task", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        res = WorkerResultRecord(
            result_id="RES-IDEMP-001",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
            summary="Original payload",
        )
        ok1, _ = self.dispatcher.ingest_worker_result(res)
        self.assertTrue(ok1)

        # Same result re-sent -> Idempotent accepted
        ok2, msg2 = self.dispatcher.ingest_worker_result(res)
        self.assertTrue(ok2)
        self.assertIn("idempotently", msg2.lower())

    def test_22_same_result_id_changed_payload_rejected(self):
        task = self.dispatcher.submit_task(title="Payload Tamper", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        res_orig = WorkerResultRecord(
            result_id="RES-IDEMP-TAMPER",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
            summary="Original summary",
        )
        self.dispatcher.ingest_worker_result(res_orig)

        # Altered summary
        res_altered = WorkerResultRecord(
            result_id="RES-IDEMP-TAMPER",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
            summary="ALTERED summary content",
        )
        ok, msg = self.dispatcher.ingest_worker_result(res_altered)
        self.assertFalse(ok)
        self.assertIn("Conflicting or altered second result", msg)

    def test_23_same_result_id_changed_node_rejected(self):
        task = self.dispatcher.submit_task(title="Node Tamper", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        res_orig = WorkerResultRecord(
            result_id="RES-NODE-TAMPER",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
        )
        self.dispatcher.ingest_worker_result(res_orig)

        # Same result_id with changed node
        res_altered = WorkerResultRecord(
            result_id="RES-NODE-TAMPER",
            task_id=task.task_id,
            node_id="NODE_B",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
        )
        ok, msg = self.dispatcher.ingest_worker_result(res_altered)
        self.assertFalse(ok)
        self.assertIn("Conflicting or altered second result", msg)

    def test_24_same_result_id_changed_lease_rejected(self):
        task = self.dispatcher.submit_task(title="Lease Tamper", task_type="AUDIT", file_scope=["docs/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        res_orig = WorkerResultRecord(
            result_id="RES-LEASE-TAMPER",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
        )
        self.dispatcher.ingest_worker_result(res_orig)

        res_altered = WorkerResultRecord(
            result_id="RES-LEASE-TAMPER",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id="different-lease-id",
            status="SUCCESS",
            started_at="2026-08-31T19:00:00+00:00",
            finished_at="2026-08-31T19:01:00+00:00",
        )
        ok, msg = self.dispatcher.ingest_worker_result(res_altered)
        self.assertFalse(ok)
        self.assertIn("Conflicting or altered second result", msg)

    def test_25_mismatched_result_cannot_release_scope_lock(self):
        t1 = self.dispatcher.submit_task(title="Router Task", task_type="REMEDIATION", file_scope=["scripts/router/"])
        _, _, l1 = self.dispatcher.claim_task_lease("NODE_A", t1.task_id)

        bad_res = WorkerResultRecord(
            result_id="RES-FORGED",
            task_id=t1.task_id,
            node_id="NODE_B",  # Wrong node!
            lease_id=l1.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        ok, _ = self.dispatcher.ingest_worker_result(bad_res)
        self.assertFalse(ok)

        active_leases = self.dispatcher.get_active_leases()
        self.assertEqual(len(active_leases), 1)
        self.assertEqual(active_leases[0].lease_id, l1.lease_id)

        t2 = self.dispatcher.submit_task(title="Colliding Task", task_type="TEST", file_scope=["scripts/router/engine.py"])
        ok_claim, msg_claim, _ = self.dispatcher.claim_task_lease("NODE_B", t2.task_id)
        self.assertFalse(ok_claim)
        self.assertIn("collision", msg_claim.lower())

    def test_26_mismatched_result_cannot_mutate_node(self):
        t1 = self.dispatcher.submit_task(title="Node Protection", task_type="AUDIT", file_scope=["p/"])
        _, _, l1 = self.dispatcher.claim_task_lease("NODE_A", t1.task_id)

        bad_res = WorkerResultRecord(
            result_id="RES-WRONG-NODE",
            task_id=t1.task_id,
            node_id="NODE_B",
            lease_id=l1.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            next_state="IDLE",
        )
        self.dispatcher.ingest_worker_result(bad_res)

        # Node A must still be ACTIVE with current task
        node_a = self.dispatcher.get_node("NODE_A")
        self.assertEqual(node_a.status, "ACTIVE")
        self.assertEqual(node_a.current_task_id, t1.task_id)

    def test_27_scope_non_overlap_allowed_concurrently(self):
        t1 = self.dispatcher.submit_task(title="Router Task", task_type="REMEDIATION", file_scope=["scripts/router/"])
        t2 = self.dispatcher.submit_task(title="Reviewer Test", task_type="TEST", file_scope=["tests/reviewer/"])

        ok1, _, _ = self.dispatcher.claim_task_lease("NODE_A", t1.task_id)
        ok2, _, _ = self.dispatcher.claim_task_lease("NODE_B", t2.task_id)

        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertEqual(len(self.dispatcher.get_active_leases()), 2)

    def test_28_heavy_job_limit_enforcement(self):
        t_heavy1 = self.dispatcher.submit_task(title="Heavy 1", task_type="RENDER", file_scope=["r/1/"], heavy_job=True)
        t_heavy2 = self.dispatcher.submit_task(title="Heavy 2", task_type="RENDER", file_scope=["r/2/"], heavy_job=True)

        ok1, _, _ = self.dispatcher.claim_task_lease("NODE_A", t_heavy1.task_id)
        self.assertTrue(ok1)

        ok2, msg2, _ = self.dispatcher.claim_task_lease("NODE_A", t_heavy2.task_id)
        self.assertFalse(ok2)
        self.assertIn("HEAVY_JOB_LIMIT", msg2)

    def test_29_resource_pool_routing_and_mismatch(self):
        t_pool2 = self.dispatcher.submit_task(
            title="Pool 2 Task", task_type="VERIFICATION", file_scope=["events/p2/"],
            required_resource_pool="GOOGLE_PRO_POOL_2",
        )
        ok_a, _, _ = self.dispatcher.claim_task_lease("NODE_A", t_pool2.task_id)
        self.assertFalse(ok_a)

        ok_b, _, _ = self.dispatcher.claim_task_lease("NODE_B", t_pool2.task_id)
        self.assertTrue(ok_b)

    def test_30_restart_recovery_with_active_and_uncertain_leases(self):
        t1 = self.dispatcher.submit_task(title="Active Task", task_type="AUDIT", file_scope=["a/"])
        t2 = self.dispatcher.submit_task(title="Uncertain Task", task_type="AUDIT", file_scope=["b/"])

        _, _, l1 = self.dispatcher.claim_task_lease("NODE_A", t1.task_id)
        _, _, l2 = self.dispatcher.claim_task_lease("NODE_B", t2.task_id)

        # Backdate lease l2 to expire
        lease_data = self.transport.read_json("active_leases.json")
        past_exp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5.0)).isoformat()
        lease_data["leases"][l2.lease_id]["expires_at"] = past_exp
        self.transport.write_json("active_leases.json", lease_data)

        # Restart dispatcher
        new_dispatcher = TwoComputerDispatcher(transport=self.transport)
        rec = new_dispatcher.recover_after_restart()

        self.assertEqual(rec["recovery_status"], "RECOVERED")
        self.assertIn(l2.lease_id, rec["expired_leases_reconciled"])

        task1 = new_dispatcher.get_task(t1.task_id)
        self.assertEqual(task1.status, "LEASED")

        task2 = new_dispatcher.get_task(t2.task_id)
        self.assertEqual(task2.status, "RECONCILIATION_REQUIRED")

    def test_31_completed_task_cannot_be_redispatched(self):
        task = self.dispatcher.submit_task(title="Completed", task_type="AUDIT", file_scope=["c/"])
        _, _, lease = self.dispatcher.claim_task_lease("NODE_A", task.task_id)

        res = WorkerResultRecord(
            result_id="RES-COMP-001",
            task_id=task.task_id,
            node_id="NODE_A",
            lease_id=lease.lease_id,
            status="SUCCESS",
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self.dispatcher.ingest_worker_result(res)

        ok, msg, _ = self.dispatcher.claim_task_lease("NODE_A", task.task_id)
        self.assertFalse(ok)
        self.assertIn("COMPLETE", msg)

    def test_32_zero_credentials_stored(self):
        registry_file = self.cluster_dir / "node_registry.json"
        queue_file = self.cluster_dir / "task_queue.json"
        leases_file = self.cluster_dir / "active_leases.json"

        patterns = [
            re.compile(r"(?i)(password|secret|apikey|api_key|token|auth|bearer)[\s:=]+[\"\x27][A-Za-z0-9_\-\.]{12,}[\"\x27]"),
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            re.compile(r"ya29\.[0-9A-Za-z\-_]+"),
            re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        ]

        for p in [registry_file, queue_file, leases_file]:
            if p.is_file():
                txt = p.read_text(encoding="utf-8")
                for pat in patterns:
                    self.assertEqual(pat.findall(txt), [], f"Secret pattern matched in {p}")


if __name__ == "__main__":
    unittest.main()
