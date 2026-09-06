import json
import multiprocessing
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from two_computer_dispatcher_oracle import (
    can_dispatch,
    claim_lease_atomically,
    classify_transport,
    heartbeat_state,
    lease_recovery_action,
    normalize_scope,
    scopes_overlap,
    task_fingerprint,
    validate_onboarding,
    validate_registry,
    validate_result,
    writable_workspaces_safe,
)


NOW = datetime.now(timezone.utc)


def node(node_id="NODE_A", **overrides):
    value = {
        "node_id": node_id, "hostname": "host", "platform": "macOS", "workspace_path": "/work",
        "status": "READY", "last_heartbeat": NOW.isoformat(), "capabilities": ["local"],
        "resource_pool": "GOOGLE_PRO_POOL_1", "current_task_id": None, "current_lease_id": None,
        "current_file_scope": None, "heavy_job_active": False, "continuation_state": "IDLE", "last_result_id": None,
    }
    value.update(overrides)
    return value


def race_claim(lease_dir, node_id, results):
    results.put((node_id, claim_lease_atomically(lease_dir, "TASK_X", node_id, "lease-" + node_id)))


class TwoComputerDispatcherOracleTests(unittest.TestCase):
    def test_registry_rejects_duplicate_and_malformed_heartbeat(self):
        errors = validate_registry([node(), node("NODE_A", last_heartbeat="not-a-time")])
        self.assertTrue(any("duplicate node_id" in error for error in errors))
        self.assertTrue(any("malformed" in error for error in errors))

    def test_heartbeat_fails_closed_when_missing_or_stale(self):
        self.assertEqual("READY", heartbeat_state(node(), NOW))
        self.assertEqual("OFFLINE", heartbeat_state(node(last_heartbeat=(NOW - timedelta(minutes=3)).isoformat()), NOW))
        self.assertEqual("UNKNOWN", heartbeat_state(node(last_heartbeat=None), NOW))

    def test_atomic_double_claim_has_one_winner(self):
        with tempfile.TemporaryDirectory() as temporary:
            results = multiprocessing.Queue()
            workers = [multiprocessing.Process(target=race_claim, args=(temporary, identifier, results)) for identifier in ("NODE_A", "NODE_B")]
            for worker in workers: worker.start()
            for worker in workers: worker.join(10)
            outcomes = [results.get(timeout=2) for _ in workers]
            self.assertEqual(1, sum(won for _, won in outcomes))
            lease = json.loads((Path(temporary) / "TASK_X.lease").read_text())
            self.assertIn(lease["node_id"], {winner for winner, won in outcomes if won})

    def test_scope_overlap_is_boundary_aware(self):
        self.assertTrue(scopes_overlap("scripts/router/", "scripts/router/core.py"))
        self.assertFalse(scopes_overlap("scripts/router/", "tests/reviewer/"))
        self.assertFalse(scopes_overlap("runtime/project/", "runtime/project2/"))
        with self.assertRaises(ValueError): normalize_scope("scripts/../secrets")

    def test_non_overlapping_parallelism_and_heavy_limit(self):
        task = {"file_scope": "tests/reviewer/", "resource_pool": "GOOGLE_PRO_POOL_1", "heavy": True}
        self.assertEqual((True, "eligible"), can_dispatch(node("NODE_B"), task, ["scripts/router/"]))
        self.assertFalse(can_dispatch(node(heavy_job_active=True), task, [])[0])

    def test_offline_and_pool_mismatch_cannot_dispatch(self):
        task = {"file_scope": "tests/reviewer/", "resource_pool": "GOOGLE_PRO_POOL_1", "heavy": False}
        self.assertFalse(can_dispatch(node(status="OFFLINE"), task, [])[0])
        self.assertFalse(can_dispatch(node(resource_pool="GOOGLE_PRO_POOL_2"), task, [])[0])
        self.assertFalse(can_dispatch(node(), {**task, "resource_pool": "GOOGLE_PRO_POOL_4"}, [])[0])

    def test_duplicate_fingerprint_is_stable(self):
        task = {"task_id": "TASK_X", "file_scope": "scripts/router/", "payload": {"x": 1}}
        self.assertEqual(task_fingerprint(task), task_fingerprint(dict(task)))

    def test_result_requires_matching_lease(self):
        lease = {"task_id": "TASK_X", "node_id": "NODE_A", "lease_id": "LEASE_A"}
        result = {"result_id": "RESULT_A", **lease, "status": "DONE", "started_at": NOW.isoformat(), "finished_at": NOW.isoformat(), "files_changed": [], "checks_run": [], "summary": "ok", "next_state": "IDLE"}
        self.assertEqual([], validate_result(result, lease))
        result["lease_id"] = "LEASE_B"
        self.assertTrue(validate_result(result, lease))

    def test_expired_lease_requires_evidence_instead_of_redispatch(self):
        expired = {"task_id": "TASK_X", "expires_at": (NOW - timedelta(minutes=1)).isoformat()}
        self.assertEqual("INSPECTION_REQUIRED", lease_recovery_action(expired, set(), "OFFLINE", NOW))
        self.assertEqual("COMPLETE_ALREADY_RECORDED", lease_recovery_action(expired, {"TASK_X"}, "OFFLINE", NOW))

    def test_onboarding_and_shared_workspace_safety(self):
        candidate = node("NODE_B", workspace_path="/isolated/node-b")
        transport = {"project_fingerprint": "project-hash", "reachable": True, "result_return": True}
        self.assertEqual([], validate_onboarding(candidate, "/isolated/node-b", "project-hash", transport))
        self.assertTrue(writable_workspaces_safe(node(workspace_path="/isolated/node-a"), candidate))
        self.assertFalse(writable_workspaces_safe(node(workspace_path="/shared/live"), node("NODE_B", workspace_path="/shared/live")))

    def test_transport_is_not_promoted_from_fixture(self):
        self.assertEqual("LOCAL_SIMULATION_ONLY", classify_transport({}))
        self.assertEqual("PARTIAL_TRANSPORT", classify_transport({"transport_declared": True}))
        self.assertEqual("REAL_TWO_MACHINE_TRANSPORT", classify_transport({"transport_verified": True, "authenticated_transport": True}))


if __name__ == "__main__":
    unittest.main()
