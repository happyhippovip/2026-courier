#!/usr/bin/env python3
"""Unit Tests for Antigravity Same-PC Account Continuity (Mission 167G).

Validates all 10 required acceptance conditions:
1. Pre-switch checkpoint creation with complete non-secret schema
2. Zero authentication secrets / tokens stored in checkpoint
3. Git HEAD, branch, and porcelain dirty-manifest tracking
4. Critical controller and dispatcher file integrity
5. Autopilot state clean & paused (no active uncommitted task)
6. Dispatcher transaction clean (0 incomplete transactions)
7. Post-switch verifier passes against unmodified canonical workspace
8. Post-switch verifier fails if workspace path is tampered
9. Post-switch verifier fails if critical script is missing or modified
10. Post-switch verifier fails if Git HEAD changes unexpectedly.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.verify_antigravity_same_pc_account_switch import (
    CHECKPOINT_FILE_167G, COURIER_DIR, create_pre_switch_checkpoint,
    scan_for_secrets, verify_post_switch_continuity,
)


class TestSamePCAccountSwitchContinuityMission167G(unittest.TestCase):
    """Test suite for Mission 167G pre-switch freeze and post-switch verifier."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_checkpoint_creation_and_fields(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        self.assertTrue(chk_path.is_file())
        self.assertEqual(chk["machine"], "COMPUTER_A")
        self.assertEqual(chk["canonical_workspace"], str(COURIER_DIR))
        self.assertEqual(chk["antigravity_project_name"], "sandbox test")
        self.assertEqual(chk["git_branch"], "main")
        self.assertFalse(chk["auth_secrets_included"])
        self.assertTrue(chk["safe_to_switch"])
        self.assertFalse(chk["incomplete_transactions_present"])

    def test_02_zero_auth_secrets_stored(self):
        chk_path = self.temp_root / "checkpoint.json"
        create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)
        content = chk_path.read_text(encoding="utf-8")

        secrets = scan_for_secrets(content)
        self.assertEqual(secrets, [], f"Detected potential secrets: {secrets}")

    def test_03_git_head_branch_dirty_tracking(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        self.assertEqual(len(chk["git_head"]), 40)
        self.assertEqual(chk["git_branch"], "main")
        self.assertGreater(chk["git_counts"]["total_dirty"], 0)

    def test_04_critical_files_preservation(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        self.assertIn("scripts/chief_autopilot.py", chk["critical_script_hashes"])
        self.assertIn("scripts/two_computer_dispatcher.py", chk["critical_script_hashes"])
        for script, shash in chk["critical_script_hashes"].items():
            self.assertIsNotNone(shash, f"Hash missing for {script}")
            self.assertEqual(len(shash), 64)

    def test_05_autopilot_paused_clean_state(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)
        self.assertIn(chk["autopilot_status"], ("PAUSED", "STOPPED"))

    def test_06_no_incomplete_transactions(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)
        self.assertFalse(chk["incomplete_transactions_present"])

    def test_07_post_switch_verifier_success(self):
        chk_path = self.temp_root / "checkpoint.json"
        create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        res = verify_post_switch_continuity(workspace_root=COURIER_DIR, checkpoint_path=chk_path)
        self.assertTrue(res["CONTINUITY_VERIFIED"])
        for check_name, passed in res["checks"].items():
            self.assertTrue(passed, f"Check failed: {check_name}")

    def test_08_post_switch_verifier_detects_workspace_path_tamper(self):
        chk_path = self.temp_root / "checkpoint.json"
        create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        tampered_ws = self.temp_root / "empty_ws"
        tampered_ws.mkdir()

        res = verify_post_switch_continuity(workspace_root=tampered_ws, checkpoint_path=chk_path)
        self.assertFalse(res["CONTINUITY_VERIFIED"])
        self.assertFalse(res["checks"]["SAME_WORKSPACE"])

    def test_09_post_switch_verifier_detects_missing_file(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk_data = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        # Alter hash of a critical script in checkpoint
        chk_data["critical_script_hashes"]["scripts/chief_autopilot.py"] = "0" * 64
        chk_path.write_text(json.dumps(chk_data, indent=2), encoding="utf-8")

        res = verify_post_switch_continuity(workspace_root=COURIER_DIR, checkpoint_path=chk_path)
        self.assertFalse(res["CONTINUITY_VERIFIED"])
        self.assertFalse(res["checks"]["CRITICAL_FILES_PRESERVED"])

    def test_10_post_switch_verifier_detects_git_head_tamper(self):
        chk_path = self.temp_root / "checkpoint.json"
        chk_data = create_pre_switch_checkpoint(workspace_root=COURIER_DIR, output_path=chk_path)

        # Alter git HEAD in checkpoint
        chk_data["git_head"] = "f" * 40
        chk_path.write_text(json.dumps(chk_data, indent=2), encoding="utf-8")

        res = verify_post_switch_continuity(workspace_root=COURIER_DIR, checkpoint_path=chk_path)
        self.assertFalse(res["CONTINUITY_VERIFIED"])
        self.assertFalse(res["checks"]["SAME_GIT_HEAD"])


if __name__ == "__main__":
    unittest.main()
