"""Adversarial acceptance probes for the completed 171G sandbox delta.

All state lives in TemporaryDirectory instances.  A passing probe records an
observed unsafe behavior; it is not a production acceptance result.
"""
import inspect
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from scripts.disaster_recovery import ChiefRecoveryPackage, DisasterRecoveryManager, verify_recovery_package_integrity


class Google171GAcceptanceProbes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = DisasterRecoveryManager(repo_dir=self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_package_is_integrity_valid_and_restorable(self):
        package = ChiefRecoveryPackage()
        self.assertTrue(verify_recovery_package_integrity(asdict(package))[0])
        result = self.manager.restore_from_package(package, home_node_state="HOME_NODE_LOST")
        self.assertEqual("RECOVERY_SUCCESSFUL", result["STATUS"])
        self.assertEqual(0, result["restored_memories_count"])

    def test_nested_json_secret_key_is_not_rejected_by_current_scanner(self):
        synthetic = "synthetic_value_12345678901234567890"
        package = ChiefRecoveryPackage(brain_state={"metadata": {"access_token": synthetic, "password": synthetic}})
        self.assertTrue(verify_recovery_package_integrity(asdict(package))[0])

    def test_package_hash_does_not_bind_encryption_or_source_workspace(self):
        package = ChiefRecoveryPackage(brain_state={"memories": {}})
        tampered = asdict(package)
        tampered["encryption_status"] = "ENCRYPTED_REMOTE"
        tampered["source_workspace"] = "/untrusted/other-machine"
        tampered["reason"] = "ALTERED_AFTER_HASH"
        self.assertTrue(verify_recovery_package_integrity(tampered)[0])

    def test_diverged_state_is_not_blocked_by_restore(self):
        package = ChiefRecoveryPackage(brain_state={"memories": {}, "tasks": {}, "ideas": {}, "open_loops": []})
        with patch.object(self.manager, "detect_conflict", return_value="DIVERGED"):
            result = self.manager.restore_from_package(package, home_node_state="HOME_NODE_LOST")
        self.assertEqual("RECOVERY_SUCCESSFUL", result["STATUS"])

    def test_index_keeps_corrupted_latest_package_selected(self):
        package = self.manager.create_recovery_package(reason="index-probe")
        path = self.manager.packages_dir / f"{package.package_id}.json"
        path.write_text("{truncated", encoding="utf-8")
        self.assertEqual(package.package_id, self.manager._load_index()["LATEST_VALID_RECOVERY_PACKAGE"])

    def test_only_running_tasks_are_orphaned_on_lost_home_node(self):
        package = ChiefRecoveryPackage(brain_state={"memories": {}, "ideas": {}, "open_loops": [], "tasks": {
            "verifying": {"task_id":"verifying", "state":"VERIFYING", "external_mutation":True},
            "hung": {"task_id":"hung", "state":"HUNG", "external_mutation":True},
            "unknown": {"task_id":"unknown", "state":"UNKNOWN", "external_mutation":True},
        }})
        self.manager.restore_from_package(package, home_node_state="HOME_NODE_LOST")
        restored = self.manager.brain._load_tasks()
        self.assertEqual("VERIFYING", restored["verifying"]["state"])
        self.assertEqual("HUNG", restored["hung"]["state"])
        self.assertEqual("UNKNOWN", restored["unknown"]["state"])

    def test_package_human_gate_payload_is_not_consumed_by_restore(self):
        package = ChiefRecoveryPackage(
            brain_state={"memories": {}, "tasks": {}, "ideas": {}, "open_loops": []},
            human_gates_state=[{"gate_id":"identity-custom", "action":"IDENTITY_REQUIRED", "status":"BLOCKED"}],
        )
        self.manager.restore_from_package(package, home_node_state="HOME_NODE_LOST")
        persisted = "".join(p.read_text() for p in (self.root / "events").rglob("*.json"))
        self.assertNotIn("identity-custom", persisted)

    def test_restore_implementation_has_no_external_replay_reconciliation_model(self):
        source = inspect.getsource(DisasterRecoveryManager.restore_from_package)
        self.assertNotIn("external_operation", source)
        self.assertNotIn("replay", source.lower())


if __name__ == "__main__":
    unittest.main()
