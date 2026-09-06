import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("account_switch_continuity_oracle.py")
SPEC = importlib.util.spec_from_file_location("continuity_oracle", MODULE_PATH)
ORACLE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ORACLE)


class AccountSwitchContinuityOracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(self.workspace)], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.email", "oracle@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "config", "user.name", "Oracle"], check=True)
        (self.workspace / "README.md").write_text("oracle", encoding="utf-8")
        (self.workspace / "config").mkdir()
        (self.workspace / "config" / "local_tools.json").write_text("{}", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.workspace), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.workspace), "commit", "-qm", "baseline"], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_identical_snapshots_pass(self):
        before = ORACLE.capture_snapshot(self.workspace, "sandbox test")
        after = ORACLE.capture_snapshot(self.workspace, "sandbox test")
        self.assertEqual("PASS", ORACLE.compare_snapshots(before, after)["result"])

    def test_workspace_change_fails_closed(self):
        before = ORACLE.capture_snapshot(self.workspace, "sandbox test")
        after = json.loads(json.dumps(before))
        after["canonical_workspace"] = "/unexpected/workspace"
        result = ORACLE.compare_snapshots(before, after)
        self.assertEqual("REMEDIATE", result["result"])
        self.assertIn("canonical workspace", result["mismatches"])

    def test_dirty_worktree_loss_fails_closed(self):
        before = ORACLE.capture_snapshot(self.workspace, "sandbox test")
        after = json.loads(json.dumps(before))
        after["workspace_integrity"]["status_digest"] = "different"
        self.assertEqual("REMEDIATE", ORACLE.compare_snapshots(before, after)["result"])

    def test_secret_like_snapshot_is_rejected(self):
        snapshot = {"safe": "sk-abcdefghijklmnopqrstuvwxyz"}
        self.assertFalse(ORACLE.secret_exclusion_check(snapshot)["passed"])


if __name__ == "__main__":
    unittest.main()
