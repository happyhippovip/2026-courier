#!/usr/bin/env python3
"""Unit Tests for Antigravity Project / Workspace Account-Switch Continuity (Mission 160G).

Tests all 10 required acceptance conditions:
1. Project discovery
2. Folder binding fingerprint
3. Permission fingerprint
4. Sandbox policy fingerprint
5. Non-workspace policy fingerprint
6. Continuation checkpoint
7. Secret exclusion
8. Missing-project fail-safe
9. Changed-setting detection
10. Same-workspace continuation & different-account conceptual transition
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.antigravity_project_snapshot import (
    CANONICAL_WORKSPACE, TARGET_PROJECT_ALIASES, TARGET_PROJECT_ID,
    generate_secret_free_snapshot,
)
from scripts.verify_antigravity_account_switch_continuity import verify_antigravity_continuity

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = COURIER_DIR / "runtime"
PRESERVATION_DIR = RUNTIME_DIR / "preservation"


class TestAntigravityAccountSwitchContinuityMission160G(unittest.TestCase):
    """Test suite validating Antigravity project preservation and account continuity."""

    def test_01_project_discovery(self):
        snapshot = generate_secret_free_snapshot()
        self.assertEqual(snapshot["project"]["id"], TARGET_PROJECT_ID)
        self.assertTrue(snapshot["project"]["project_found"])
        self.assertIn(snapshot["project"]["canonical_name"], TARGET_PROJECT_ALIASES)

    def test_02_folder_binding_fingerprint(self):
        snapshot = generate_secret_free_snapshot()
        bindings = snapshot["workspace"]["folder_bindings"]
        self.assertTrue(len(bindings) >= 1)
        self.assertEqual(bindings[0]["folderUri"], f"file://{CANONICAL_WORKSPACE}")
        self.assertTrue(len(snapshot["fingerprints"]["folder_bindings_hash"]) == 64)

    def test_03_permission_fingerprint(self):
        snapshot = generate_secret_free_snapshot()
        perms = snapshot["permissions"]["project_permission_grants"]
        self.assertTrue(len(perms) > 0)
        self.assertTrue(len(snapshot["fingerprints"]["project_permissions_hash"]) == 64)

    def test_04_sandbox_policy_fingerprint(self):
        snapshot = generate_secret_free_snapshot()
        policies = snapshot["policies"]
        self.assertIn("terminal_execution_policy", policies)
        self.assertIn("terminal_sandbox_mode", policies)
        self.assertTrue(len(snapshot["fingerprints"]["terminal_policy_hash"]) == 64)

    def test_05_non_workspace_policy_fingerprint(self):
        snapshot = generate_secret_free_snapshot()
        policies = snapshot["policies"]
        self.assertIn("non_workspace_file_access_policy", policies)
        self.assertTrue(len(snapshot["fingerprints"]["non_workspace_policy_hash"]) == 64)

    def test_06_continuation_checkpoint(self):
        chk_file = PRESERVATION_DIR / "mission_160g_continuation_checkpoint.json"
        self.assertTrue(chk_file.is_file(), "Continuation checkpoint must exist")
        data = json.loads(chk_file.read_text(encoding="utf-8"))
        self.assertEqual(data["mission_id"], "MISSION_160G")
        self.assertEqual(data["creator_production_state"]["status"], "PAUSED")
        self.assertEqual(data["creator_production_state"]["videos_rendered_in_mission_160g"], 0)
        self.assertTrue(data["continuation_readiness"]["safe_to_switch_google_account"])
        self.assertTrue(data["continuation_readiness"]["continuation_ready"])

    def test_07_secret_exclusion(self):
        snap_file = PRESERVATION_DIR / "antigravity_project_snapshot_sandbox_test.json"
        chk_file = PRESERVATION_DIR / "mission_160g_continuation_checkpoint.json"
        patterns = [
            re.compile(r"(?i)(password|apikey|api_key|bearer)[\s:=]+[\"\x27][A-Za-z0-9_\-\.]{12,}[\"\x27]"),
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            re.compile(r"ya29\.[0-9A-Za-z\-_]+"),
            re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        ]
        for path in [snap_file, chk_file]:
            self.assertTrue(path.is_file())
            content = path.read_text(encoding="utf-8")
            for pat in patterns:
                self.assertEqual(pat.findall(content), [], f"Secret pattern matched in {path}")

    def test_08_missing_project_failsafe(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_cfg = Path(tmp_dir) / "empty_config"
            empty_cfg.mkdir(parents=True)
            (empty_cfg / "projects").mkdir()
            res = verify_antigravity_continuity(config_dir=empty_cfg)
            self.assertEqual(res["verdict"], "FAIL")
            self.assertFalse(res["continuation_ready"])
            self.assertFalse(res["checks"]["PROJECT_FOUND"])

    def test_09_changed_setting_detection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_cfg = Path(tmp_dir) / "fake_config"
            proj_dir = fake_cfg / "projects"
            proj_dir.mkdir(parents=True)
            # Create project with zero permissions to test changed-setting detection
            p_file = proj_dir / f"{TARGET_PROJECT_ID}.json"
            p_file.write_text(json.dumps({
                "id": TARGET_PROJECT_ID,
                "name": "2026-courier",
                "projectResources": {"resources": []},
                "permissionGrants": {"permissionGrants": {"allow": []}},
            }), encoding="utf-8")

            res = verify_antigravity_continuity(config_dir=fake_cfg)
            self.assertFalse(res["checks"]["PROJECT_PERMISSIONS_MATCH"])
            self.assertFalse(res["continuation_ready"])

    def test_10_same_workspace_continuation_and_account_transition(self):
        res = verify_antigravity_continuity()
        self.assertEqual(res["verdict"], "PASS")
        self.assertTrue(res["checks"]["CANONICAL_WORKSPACE_MATCH"])
        self.assertTrue(res["checks"]["LOCAL_FILES_PRESERVED"])
        self.assertTrue(res["checks"]["CONTINUATION_STATE_AVAILABLE"])
        self.assertTrue(res["continuation_ready"])


if __name__ == "__main__":
    unittest.main()
