"""Bounded deterministic tests for SNITCH runtime classification and dedupe."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_snitch_watchdog import RuntimeObservation, SnitchWatchdog
from scripts.run_chief_commander import ChiefCommander


class SnitchWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = dt.datetime(2026, 8, 30, 12, 0, tzinfo=dt.timezone.utc)
        self.watchdog = SnitchWatchdog(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def observation(self, **changes):
        values = {
            "process": "python3 scripts/worker.py",
            "elapsed_seconds": 240,
            "task_id": "task-1",
            "workflow_id": "wf-1",
            "correlation_id": "corr-1",
            "started_at": (self.now - dt.timedelta(seconds=240)).isoformat(),
            "last_progress_at": None,
            "evidence": {"cpu_time_advancing": False},
        }
        values.update(changes)
        return RuntimeObservation(**values)

    def test_normal_progressing_and_persistent_service_do_not_alert(self):
        normal = self.watchdog.scan(self.observation(elapsed_seconds=240), self.now)
        slow = self.watchdog.scan(self.observation(
            elapsed_seconds=360,
            last_progress_at=(self.now - dt.timedelta(seconds=20)).isoformat(),
        ), self.now)
        persistent = self.watchdog.scan(self.observation(
            process="python3 scripts/run_visual_studio_server.py --port 8088",
            elapsed_seconds=3600,
        ), self.now)
        self.assertEqual(normal["classification"], "MONITORING")
        self.assertEqual(slow["classification"], "SLOW_BUT_PROGRESSING")
        self.assertEqual(persistent["classification"], "EXPECTED_LONG_RUNNING")
        self.assertFalse((self.repo / "events/runtime-alerts").exists())

    def test_stall_emits_exactly_one_alert_and_reconstructs_after_restart(self):
        stalled = self.observation(elapsed_seconds=360, last_progress_at=(self.now - dt.timedelta(seconds=301)).isoformat())
        first = self.watchdog.scan(stalled, self.now)
        restarted = SnitchWatchdog(self.repo).scan(stalled, self.now)
        alerts = list((self.repo / "events/runtime-alerts").glob("*.json"))
        self.assertEqual(first["classification"], "STALLED")
        self.assertEqual(restarted["classification"], "STALLED")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(restarted["alert_path"], alerts[0])

    def test_human_gate_and_missing_provenance_never_cross_thread_alert(self):
        gated = self.watchdog.scan(self.observation(elapsed_seconds=360, human_gate=True), self.now)
        unknown = self.watchdog.scan(self.observation(
            elapsed_seconds=360,
            workflow_id=None,
            correlation_id=None,
        ), self.now)
        self.assertEqual(gated["classification"], "WAITING_FOR_HUMAN")
        self.assertEqual(unknown["classification"], "UNKNOWN")
        self.assertFalse((self.repo / "events/runtime-alerts").exists())

    def test_chief_creates_a_bounded_routing_recommendation_for_alert(self):
        stalled = self.watchdog.scan(self.observation(
            elapsed_seconds=360,
            last_progress_at=(self.now - dt.timedelta(seconds=301)).isoformat(),
        ), self.now)
        alert = json.loads(stalled["alert_path"].read_text(encoding="utf-8"))
        chief = ChiefCommander.__new__(ChiefCommander)
        chief.repo_dir = self.repo
        decision = chief.review_runtime_alert(alert)
        self.assertEqual(decision["workflow_id"], "wf-1")
        self.assertEqual(decision["correlation_id"], "corr-1")
        self.assertEqual(decision["action"], "RECOMMEND_SCOPED_DIAGNOSIS")
        self.assertIsNone(decision["next_task"])


if __name__ == "__main__":
    unittest.main()
