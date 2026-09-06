"""Focused acceptance tests for the Product-1C read-only truth contract."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.live_operations_truth_contract import LiveOperationsTruthContract


class LiveOperationsTruthContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="product_1c_truth_"))
        self.events = self.root / "events"
        (self.events / "autonomy-runtime" / "jobs").mkdir(parents=True)
        (self.events / "anomalies").mkdir(parents=True)
        self.contract = LiveOperationsTruthContract(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_json(self, relative, value):
        path = self.events / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def job(self, task_id="TASK-1", status="DISPATCHED", **extra):
        value = {"task_id": task_id, "status": status, "owner": "agent-a", "provider": "LOCAL", "scope": "scope-a", "resource_class": "LOCAL_DETERMINISTIC", "created_at": "2026-09-01T00:00:00+00:00"}
        value.update(extra)
        return value

    def test_task_owner_active_wait_and_result_reduction(self):
        self.assertEqual(self.contract.reduce_tasks([self.job()], [])[0]["status"], "ACTIVE")
        self.assertEqual(self.contract.reduce_tasks([self.job(status="PREPARED")], [])[0]["status"], "WAITING")
        result = self.contract.reduce_tasks([self.job(status="EXECUTED_SUCCESS", correlation_id="corr-1")], [])[0]
        self.assertEqual(result["status"], "RESULT_READY")
        self.assertEqual(result["result_reference"], "corr-1")

    def test_human_and_money_gate_mapping(self):
        self.write_json("autonomy-runtime/current_session.json", {"human_gates_encountered": [{"task_id": "H", "reason": "approval"}], "money_gates_encountered": [{"task_id": "M", "reason": "budget"}]})
        states = {item["task_id"]: item["status"] for item in self.contract.snapshot()["tasks"]}
        self.assertEqual(states, {"H": "HUMAN_GATE", "M": "MONEY_GATE"})

    def test_missing_and_conflicting_evidence_never_fake_active(self):
        self.assertEqual(self.contract.snapshot()["organization_status"], "IDLE")
        conflict = self.contract.reduce_tasks([self.job(owner="agent-a"), self.job(owner="agent-b")], [])[0]
        self.assertEqual(conflict["status"], "UNKNOWN")
        self.assertIsNone(conflict["owner_agent"])

    def test_duplicate_task_and_anomaly_are_suppressed(self):
        self.write_json("autonomy-runtime/jobs/a.json", self.job())
        self.write_json("autonomy-runtime/jobs/b.json", self.job())
        self.write_json("anomalies/anomaly_ledger.json", {"same": {"severity": "CRITICAL", "affected_branch": "B", "affected_scope": "S"}})
        snapshot = self.contract.snapshot()
        self.assertEqual(len(snapshot["tasks"]), 1)
        self.assertEqual(len(snapshot["anomalies"]), 1)
        self.assertTrue(snapshot["anomalies"][0]["quarantined"])

    def test_188g_status_is_read_only_and_pending_until_completed(self):
        self.write_json("autonomy-runtime/heartbeat.json", {"session_id": "session-188g-endurance-1788216021", "status": "RUNNING", "elapsed_seconds": 100, "duration_target_hours": 8})
        status = self.contract.snapshot()["endurance_188g"]
        self.assertEqual(status["endurance_proven"], "PENDING")
        self.assertEqual(self.contract.model_calls, 0)

    def test_repeated_poll_is_stable_zero_model_and_safe(self):
        self.write_json("autonomy-runtime/jobs/a.json", self.job(provider="GOOGLE_PRO"))
        first, second = self.contract.snapshot(), self.contract.snapshot()
        self.assertEqual(first, second)
        self.assertEqual(self.contract.model_calls, 0)
        self.assertEqual(first["active_provider"], "GOOGLE_PRO")

    def test_snapshot_redacts_sensitive_fields(self):
        self.write_json("autonomy-runtime/event_ledger.json", {"events": [{"task_id": "TASK-1", "client_secret": "not-visible"}]})
        self.write_json("autonomy-runtime/jobs/a.json", self.job(status="EXECUTED_SUCCESS"))
        encoded = json.dumps(self.contract.snapshot())
        self.assertNotIn("not-visible", encoded)
        self.assertIn("[REDACTED]", encoded)


if __name__ == "__main__":
    unittest.main()
