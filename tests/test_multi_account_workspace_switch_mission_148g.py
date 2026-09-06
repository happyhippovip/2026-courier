#!/usr/bin/env python3
"""Unit tests for Multi-Account Workspace Switching Engine (Mission 148G)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.multi_account_workspace_switch import (
    ALLOWED_POOLS,
    AccountPoolRecord,
    MultiAccountWorkspaceSwitchEngine,
    ThreePoolResourceRegistry,
)


class TestMultiAccountWorkspaceSwitchMission148G(unittest.TestCase):
    """Deterministic tests for 3-account workspace switching continuity."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_multi_acc_switch_"))
        self.workspace_dir = self.tmp_dir / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "events" / "preservation").mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "events" / "resource-intelligence").mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "tests").mkdir(parents=True, exist_ok=True)

        # Create mock critical files
        for rel_f in [
            "scripts/resource_intelligence.py",
            "tests/test_resource_intelligence_mission_146c.py",
            "scripts/release_acceptance_gate.py",
            "scripts/private_upload_executor.py",
            "scripts/publication_engine.py",
            "scripts/evidence_provenance.py",
            "scripts/publication_approval.py",
            "scripts/private_upload_dry_run.py",
            "scripts/pre_switch_preservation_guard.py",
            "tests/test_pre_switch_preservation_guard.py",
            "tests/test_mission_141c_acceptance_oracle.py",
            "tests/test_production_security_remediations_mission_139g.py",
            "tests/test_production_trust_and_executor_hardening_mission_137g.py",
        ]:
            fp = self.workspace_dir / rel_f
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(f"# Content for {rel_f}\n")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_four_separate_resource_pools_after_safe_migration(self):
        reg = ThreePoolResourceRegistry(self.workspace_dir)
        data = reg.load_registry()
        self.assertIn("GOOGLE_PRO_POOL_1", data)
        self.assertIn("GOOGLE_PRO_POOL_2", data)
        self.assertIn("GOOGLE_PRO_POOL_3", data)
        self.assertIn("GOOGLE_PRO_POOL_4", data)
        self.assertEqual(data["GOOGLE_PRO_POOL_4"]["status"], "NOT_CONFIGURED")
        self.assertEqual(len(data), 4)

    def test_02_quotas_never_summed(self):
        reg = ThreePoolResourceRegistry(self.workspace_dir)
        reg.update_pool("GOOGLE_PRO_POOL_1", five_hour_remaining_pct=60.0)
        reg.update_pool("GOOGLE_PRO_POOL_2", five_hour_remaining_pct=80.0)
        reg.update_pool("GOOGLE_PRO_POOL_3", five_hour_remaining_pct=40.0)

        data = reg.load_registry()
        # Ensure pools are independent and not summed into an artificial total
        self.assertEqual(data["GOOGLE_PRO_POOL_1"]["five_hour_remaining_pct"], 60.0)
        self.assertEqual(data["GOOGLE_PRO_POOL_2"]["five_hour_remaining_pct"], 80.0)
        self.assertEqual(data["GOOGLE_PRO_POOL_3"]["five_hour_remaining_pct"], 40.0)
        self.assertNotIn("total_quota", data)

    def test_03_canonical_workspace_independent_from_account(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        fp = engine.compute_workspace_fingerprint()
        self.assertIn("composite_fingerprint", fp)
        self.assertIn("git_fingerprint", fp)
        self.assertEqual(len(fp["critical_files"]), 13)

    def test_04_pre_switch_fingerprint_generation(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        fp_data = engine.compute_workspace_fingerprint()
        self.assertTrue(len(fp_data["composite_fingerprint"]) == 64)
        self.assertTrue(len(fp_data["critical_files_hash"]) == 64)

    def test_05_post_switch_fingerprint_matching(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        fp1 = engine.compute_workspace_fingerprint()
        fp2 = engine.compute_workspace_fingerprint()
        self.assertEqual(fp1["composite_fingerprint"], fp2["composite_fingerprint"])

    def test_06_changed_workspace_triggers_delta_checkpoint(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        # Without a valid manifest, delta is required
        status = engine.verify_preservation_status()
        self.assertEqual(status["status"], "DELTA_REQUIRED")

    def test_07_unchanged_workspace_reuses_verified_checkpoint(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        # Create a mock manifest matching current files
        manifest = {
            "schema_version": "1.0",
            "manifest_id": "test-manifest-147g",
            "manifest_content_hash": "abc123hash",
            "file_count": 13,
            "files": [],
        }
        for rel_f in [
            "scripts/resource_intelligence.py",
            "tests/test_resource_intelligence_mission_146c.py",
            "scripts/release_acceptance_gate.py",
            "scripts/private_upload_executor.py",
            "scripts/publication_engine.py",
            "scripts/evidence_provenance.py",
            "scripts/publication_approval.py",
            "scripts/private_upload_dry_run.py",
            "scripts/pre_switch_preservation_guard.py",
            "tests/test_pre_switch_preservation_guard.py",
            "tests/test_mission_141c_acceptance_oracle.py",
            "tests/test_production_security_remediations_mission_139g.py",
            "tests/test_production_trust_and_executor_hardening_mission_137g.py",
        ]:
            fp = self.workspace_dir / rel_f
            manifest["files"].append({
                "relative_path": rel_f,
                "sha256": MultiAccountWorkspaceSwitchEngine(self.workspace_dir).compute_workspace_fingerprint()["critical_files"][rel_f],
            })
        (self.workspace_dir / "events" / "preservation" / "manifest_current.json").write_text(json.dumps(manifest))

        status = engine.verify_preservation_status()
        self.assertEqual(status["status"], "REUSE_PREVIOUS_VERIFIED_SNAPSHOT")

    def test_08_account_conversation_not_canonical_memory(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        pkg = engine.persist_chief_continuation_package("GOOGLE_PRO_POOL_2")
        self.assertEqual(pkg["schema_version"], "CHIEF_CONTEXT_PACKAGE_V1")
        self.assertEqual(pkg["authoritative_state"]["target_pool"], "GOOGLE_PRO_POOL_2")
        snap_file = self.workspace_dir / "events" / "context-snapshots" / "snapshot-current.json"
        self.assertTrue(snap_file.is_file())

    def test_09_no_auth_secrets_stored(self):
        reg = ThreePoolResourceRegistry(self.workspace_dir)
        data = reg.load_registry()
        raw_json = json.dumps(data)
        self.assertNotIn("password", raw_json.lower())
        self.assertNotIn("cookie", raw_json.lower())
        self.assertNotIn("oauth", raw_json.lower())
        self.assertNotIn("token", raw_json.lower())

    def test_10_repeated_switch_request_is_idempotent(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir, canonical_root=str(self.workspace_dir))
        res1 = engine.prepare_google_account_switch("GOOGLE_PRO_POOL_2")
        res2 = engine.prepare_google_account_switch("GOOGLE_PRO_POOL_2")
        self.assertEqual(res1["status"], res2["status"])
        self.assertEqual(res1["pre_switch_fingerprint"], res2["pre_switch_fingerprint"])

    def test_11_running_unsafe_task_blocks_switch(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        # Simulate active heavy job
        cmd_file = self.workspace_dir / "events" / "resource-intelligence" / "command-fingerprints.json"
        cmd_file.write_text(json.dumps({"fp123": {"state": "RUNNING", "heavy": True}}))

        safety = engine.check_active_task_safety()
        self.assertFalse(safety["can_switch"])
        self.assertEqual(safety["safety_class"], "NOT_SAFE_TO_SWITCH")

    def test_12_persistent_studio_server_does_not_block_switch(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        # Daemon non-heavy tasks should not block switch
        cmd_file = self.workspace_dir / "events" / "resource-intelligence" / "command-fingerprints.json"
        cmd_file.write_text(json.dumps({"fp_daemon": {"state": "RUNNING", "heavy": False}}))

        safety = engine.check_active_task_safety()
        self.assertTrue(safety["can_switch"])
        self.assertEqual(safety["safety_class"], "SAFE_TO_SWITCH")

    def test_13_weiter_can_recommend_but_not_execute_switch(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        # Set low remaining on pool 2
        engine.registry.update_pool("GOOGLE_PRO_POOL_2", five_hour_remaining_pct=5.0)
        engine.registry.update_pool("GOOGLE_PRO_POOL_1", five_hour_remaining_pct=90.0, availability="AVAILABLE")

        weiter_resp = engine.handle_weiter_command(current_pool="GOOGLE_PRO_POOL_2")
        self.assertEqual(weiter_resp["CURRENT_PROVIDER_POOL"], "GOOGLE_PRO_POOL_2")
        self.assertTrue(weiter_resp["ACCOUNT_SWITCH_RECOMMENDED"]["required"])
        self.assertEqual(weiter_resp["ACCOUNT_SWITCH_RECOMMENDED"]["to_pool"], "GOOGLE_PRO_POOL_1")

    def test_14_money_firewall_remains_active(self):
        engine = MultiAccountWorkspaceSwitchEngine(self.workspace_dir)
        pkg = engine.persist_chief_continuation_package("GOOGLE_PRO_POOL_2")
        self.assertEqual(pkg["authoritative_state"]["autonomous_spend_limit_eur"], 0.0)
        self.assertIn("AUTONOMOUS_SPEND_LIMIT_0_EUR", pkg["money_rules"])


if __name__ == "__main__":
    unittest.main()
