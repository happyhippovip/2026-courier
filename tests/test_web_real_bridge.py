"""Desktop START bridge: normal product path must not force LOCAL_FAKE.

REAL_MUSE tasks already in the queue run through the proven motor path.
The local deterministic entry stays available separately via the
mac_adapter --local-fake CLI flag. No provider, no network.
"""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.cannon import web


class RunCountdownTests(unittest.TestCase):
    def setUp(self):
        web.RUN_BASE["done"] = None
        self.addCleanup(web.RUN_BASE.clear)
        self.child = Mock()
        self.child.poll.return_value = None
        self.child.stdin = io.BytesIO()
        self.done_now = 0

        def fake_status():
            return {"overnight": {"erledigt": self.done_now},
                    "state": "IDLE", "task_counts": {}, "invariants": {}}

        self.patches = [patch.multiple(web, CHILD=None, JOB=None),
                        patch.object(web, "launch_gated",
                                     return_value=(self.child, Mock(), {})),
                        patch.object(web.threading, "Thread"),
                        patch.object(web, "get_mac_status", side_effect=lambda: fake_status()),
                        patch.object(web, "build_identity", return_value="test")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_remaining_starts_at_target_without_base(self):
        payload = web.status()
        self.assertEqual(payload["session"]["target"], 1000000000)
        self.assertEqual(payload["session"]["remaining"], 1000000000)

    def test_remaining_counts_down_only_verified_done(self):
        self.done_now = 5000
        web.action({"action": "START"})
        self.assertEqual(web.status()["session"]["remaining"], 1000000000)
        self.done_now = 5001
        self.assertEqual(web.status()["session"]["remaining"], 999999999)
        self.done_now = 5002
        self.assertEqual(web.status()["session"]["remaining"], 999999998)

    def test_remaining_never_allocates_tasks(self):
        with patch.object(web.subprocess, "check_call") as check_call:
            web.action({"action": "START"})
        check_call.assert_not_called()


class WebStartBridgeTests(unittest.TestCase):
    def setUp(self):
        self.commands = []

        def launch(command, cwd, env, **kwargs):
            child = Mock()
            child.poll.return_value = None
            child.stdin = io.BytesIO()
            self.commands.append(list(command))
            return child, Mock(), {"test_only": True}

        self.patches = [patch.multiple(web, CHILD=None, JOB=None),
                        patch.object(web, "launch_gated", side_effect=launch),
                        patch.object(web.threading, "Thread")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_start_spawns_dauerlauf_without_local_fake(self):
        result = web.action({"action": "START"})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(self.commands), 1)
        command = self.commands[-1]
        self.assertIn("dauerlauf", command)
        self.assertNotIn("--local-fake", command)

    def test_start_seeds_nothing_and_keeps_internal_ceiling(self):
        with patch.object(web.subprocess, "check_call") as check_call:
            web.action({"action": "START", "mode": "UNENDLICH", "count": 1})
        check_call.assert_not_called()
        command = self.commands[-1]
        self.assertIn("--art", command)
        self.assertEqual(command[command.index("--art") + 1], "unendlich")

    def test_local_fake_entry_still_exists_separately(self):
        src = Path(web.__file__).read_text(encoding="utf-8")
        cli = Path("scripts/mac_adapter.py").read_text(encoding="utf-8")
        self.assertIn("--local-fake", cli)


if __name__ == "__main__":
    unittest.main()
