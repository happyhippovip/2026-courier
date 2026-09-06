#!/usr/bin/env python3
"""Unit tests for Pre-Switch Workspace Preservation Guard (Mission 147G-SAFE)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.pre_switch_preservation_guard import (
    WorkspacePreservationGuard,
    compute_file_sha256,
)


class TestPreSwitchPreservationGuard(unittest.TestCase):
    """Test suite verifying workspace preservation, verification, and recovery drill."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_preservation_guard_"))
        self.workspace_dir = self.tmp_dir / "workspace"
        self.backup_root = self.tmp_dir / "backups"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.backup_root.mkdir(parents=True, exist_ok=True)

        # Create mock project files
        (self.workspace_dir / "scripts").mkdir()
        (self.workspace_dir / "tests").mkdir()
        (self.workspace_dir / "events").mkdir()

        (self.workspace_dir / "scripts" / "resource_intelligence.py").write_text("# 146C Resource Intelligence\nprint('energy ok')")
        (self.workspace_dir / "tests" / "test_resource_intelligence_mission_146c.py").write_text("# 146C Test\n")
        (self.workspace_dir / "scripts" / "release_acceptance_gate.py").write_text("# 146G Acceptance Gate\n")
        (self.workspace_dir / "scripts" / "private_upload_executor.py").write_text("# 146G Private Upload Executor\n")
        (self.workspace_dir / "scripts" / "publication_engine.py").write_text("# 146G Publication Engine\n")
        (self.workspace_dir / "scripts" / "evidence_provenance.py").write_text("# 146G Evidence Provenance\n")
        (self.workspace_dir / "scripts" / "publication_approval.py").write_text("# 146G Publication Approval\n")
        (self.workspace_dir / "scripts" / "private_upload_dry_run.py").write_text("# 146G Dry Run\n")
        (self.workspace_dir / "tests" / "test_mission_141c_acceptance_oracle.py").write_text("# 146G 141C Oracle\n")
        (self.workspace_dir / "tests" / "test_production_security_remediations_mission_139g.py").write_text("# 146G 139G Remed\n")
        (self.workspace_dir / "tests" / "test_production_trust_and_executor_hardening_mission_137g.py").write_text("# 146G 137G Trust\n")
        (self.workspace_dir / "events" / "heartbeat.json").write_text('{"status": "alive"}')

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_inventory_and_manifest_generation(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        inv = guard.build_inventory()
        self.assertEqual(inv["total_files"], 12)
        self.assertTrue(inv["mission_146c_inventory"]["scripts/resource_intelligence.py"]["exists"])
        self.assertTrue(inv["mission_146g_inventory"]["scripts/release_acceptance_gate.py"]["exists"])

        manifest = guard.generate_manifest(inv)
        self.assertEqual(manifest["file_count"], 12)
        self.assertTrue(manifest["mission_146c_verified"])
        self.assertTrue(manifest["mission_146g_verified"])
        self.assertTrue(len(manifest["manifest_content_hash"]) == 64)

    def test_backup_creation_and_hash_verification(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        manifest = guard.generate_manifest()
        snapshot_dir, meta = guard.create_backup(manifest)

        self.assertTrue(snapshot_dir.is_dir())
        self.assertTrue((snapshot_dir / "preservation_manifest.json").is_file())
        self.assertTrue((snapshot_dir / "SNAPSHOT_METADATA.json").is_file())
        self.assertTrue((snapshot_dir / "scripts" / "resource_intelligence.py").is_file())

        verification = guard.verify_backup(snapshot_dir, manifest)
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["hash_mismatch_count"], 0)
        self.assertEqual(verification["missing_file_count"], 0)
        self.assertEqual(verification["hash_match_count"], 12)

    def test_tampered_backup_file_fails_verification(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        manifest = guard.generate_manifest()
        snapshot_dir, meta = guard.create_backup(manifest)

        # Corrupt a file in the backup snapshot
        tampered_file = snapshot_dir / "scripts" / "resource_intelligence.py"
        tampered_file.write_text("# Corrupted content")

        verification = guard.verify_backup(snapshot_dir, manifest)
        self.assertFalse(verification["verified"])
        self.assertEqual(verification["hash_mismatch_count"], 1)
        self.assertEqual(len(verification["mismatched_details"]), 1)
        self.assertEqual(verification["mismatched_details"][0]["file"], "scripts/resource_intelligence.py")

    def test_missing_backup_file_fails_verification(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        manifest = guard.generate_manifest()
        snapshot_dir, meta = guard.create_backup(manifest)

        # Delete a file from the snapshot
        (snapshot_dir / "scripts" / "release_acceptance_gate.py").unlink()

        verification = guard.verify_backup(snapshot_dir, manifest)
        self.assertFalse(verification["verified"])
        self.assertEqual(verification["missing_file_count"], 1)

    def test_recovery_drill_isolated_reconstruction(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        manifest = guard.generate_manifest()
        snapshot_dir, meta = guard.create_backup(manifest)

        drill = guard.run_recovery_drill(snapshot_dir, manifest)
        self.assertTrue(drill["recovery_drill_passed"])
        self.assertEqual(drill["recovery_manifest_match"], "PASS")
        self.assertEqual(drill["restored_matches"], 12)
        self.assertEqual(drill["restored_mismatches"], 0)

    def test_account_dependencies_classification(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        deps = guard.analyze_account_dependencies()
        self.assertEqual(deps["PROJECT_WORKSPACE_FILES"], "LOCAL_ACCOUNT_INDEPENDENT")
        self.assertEqual(deps["GIT_WORKING_TREE"], "LOCAL_ACCOUNT_INDEPENDENT")
        self.assertEqual(deps["LOCAL_RUNTIME_STATE"], "LOCAL_ACCOUNT_INDEPENDENT")
        self.assertEqual(deps["ANTIGRAVITY_CONVERSATIONS"], "ACCOUNT_DEPENDENT")
        self.assertEqual(deps["ANTIGRAVITY_ARTIFACTS"], "ACCOUNT_DEPENDENT")
        self.assertEqual(deps["AUTHENTICATION_SESSION"], "ACCOUNT_DEPENDENT")
        self.assertEqual(deps["PROVIDER_QUOTA"], "ACCOUNT_DEPENDENT")

    def test_full_preservation_guard_success(self):
        guard = WorkspacePreservationGuard(
            workspace_path=self.workspace_dir,
            backup_root=self.backup_root,
        )
        result = guard.execute_full_preservation_guard()
        self.assertEqual(result["guard_result"], "SAFE_TO_SWITCH_ACCOUNT")
        self.assertEqual(result["safe_to_log_out_of_google"], "YES")
        self.assertEqual(result["safe_to_open_same_workspace_with_account_2"], "YES")
        self.assertEqual(result["verification"]["hash_mismatch_count"], 0)
        self.assertEqual(result["recovery_drill"]["recovery_manifest_match"], "PASS")
        self.assertEqual(result["recheck"]["mission_146c_preserved"], "YES")
        self.assertEqual(result["recheck"]["mission_146g_preserved"], "YES")
        self.assertEqual(result["recheck"]["data_loss_detected"], "NO")

        status_file = self.workspace_dir / "events" / "workspace_preservation_status.json"
        self.assertTrue(status_file.is_file())
        status_data = json.loads(status_file.read_text())
        self.assertEqual(status_data["WORKSPACE_BACKUP_STATUS"], "SAFE")
        self.assertEqual(status_data["ACCOUNT_SWITCH_STATUS"], "SAFE")
        self.assertEqual(status_data["DATA_LOSS_RISK"], "NONE_DETECTED")


if __name__ == "__main__":
    unittest.main()
