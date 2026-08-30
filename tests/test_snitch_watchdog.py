"""Bounded deterministic tests for SNITCH 2.0 runtime classification and dedupe."""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = TESTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

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
            "process_type": "BOUNDED_JOB",
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

    def test_01_four_minute_task_monitoring_no_incident(self):
        """1. 4-minute task -> MONITORING, no incident file."""
        res = self.watchdog.scan(self.observation(elapsed_seconds=240), self.now)
        self.assertEqual(res["classification"], "MONITORING")
        self.assertIsNone(res["alert_path"])
        self.assertFalse((self.repo / "events/runtime-alerts").exists())
        self.assertIn("monitoring", res["speech"].lower())

    def test_02_six_minute_task_with_progress_slow_but_progressing(self):
        """2. 6-minute task + recent progress -> SLOW_BUT_PROGRESSING."""
        res = self.watchdog.scan(self.observation(
            elapsed_seconds=360,
            last_progress_at=(self.now - dt.timedelta(seconds=20)).isoformat(),
        ), self.now)
        self.assertEqual(res["classification"], "SLOW_BUT_PROGRESSING")
        self.assertIsNone(res["alert_path"])
        self.assertIn("exceeded five minutes, but progress is still detected", res["speech"])

    def test_03_studio_server_over_five_minutes_expected_long_running(self):
        """3. Studio server >5 min -> EXPECTED_LONG_RUNNING, no false incident."""
        res = self.watchdog.scan(self.observation(
            process="python3 scripts/run_visual_studio_server.py --port 8088",
            process_type="PERSISTENT_SERVICE",
            elapsed_seconds=3600,
            persistent_service=True,
        ), self.now)
        self.assertEqual(res["classification"], "EXPECTED_LONG_RUNNING")
        self.assertIsNone(res["alert_path"])
        self.assertFalse((self.repo / "events/runtime-alerts").exists())

    def test_04_bounded_task_over_five_minutes_no_progress_stalled(self):
        """4. Bounded task >5 min, no progress -> SUSPECTED_STALL / STALLED with deduplicated alert."""
        res_suspected = self.watchdog.scan(self.observation(
            elapsed_seconds=360,
            last_progress_at=(self.now - dt.timedelta(seconds=350)).isoformat(),
        ), self.now)
        self.assertEqual(res_suspected["classification"], "SUSPECTED_STALL")
        self.assertIsNotNone(res_suspected["alert_path"])

        res_stalled = self.watchdog.scan(self.observation(
            elapsed_seconds=650,
            last_progress_at=(self.now - dt.timedelta(seconds=640)).isoformat(),
        ), self.now)
        self.assertEqual(res_stalled["classification"], "STALLED")
        self.assertIsNotNone(res_stalled["alert_path"])

    def test_05_human_gate_waiting_for_human(self):
        """5. Human Gate -> WAITING_FOR_HUMAN, no alarm alert."""
        res = self.watchdog.scan(self.observation(elapsed_seconds=600, human_gate=True), self.now)
        self.assertEqual(res["classification"], "WAITING_FOR_HUMAN")
        self.assertIsNone(res["alert_path"])

    def test_06_godot_bounded_render_with_progress_slow_but_progressing(self):
        """6. Godot bounded render with progress advancing -> SLOW_BUT_PROGRESSING."""
        res = self.watchdog.scan(self.observation(
            process="godot --headless --movie-maker",
            elapsed_seconds=420,
            expected_max_seconds=600,
            expected_max_frames=192,
            current_frames=120,
            evidence={"frames_progressing": True},
        ), self.now)
        self.assertEqual(res["classification"], "SLOW_BUT_PROGRESSING")
        self.assertIsNone(res["alert_path"])

    def test_07_godot_bounded_render_exceeding_contract_runaway_risk(self):
        """7. Godot bounded render beyond safety contract -> RUNAWAY_RISK."""
        res = self.watchdog.scan(self.observation(
            process="godot --headless --movie-maker",
            elapsed_seconds=700,
            expected_max_seconds=600,
            expected_max_frames=192,
            current_frames=250,
        ), self.now)
        self.assertEqual(res["classification"], "RUNAWAY_RISK")
        self.assertIsNotNone(res["alert_path"])
        alert_data = json.loads(res["alert_path"].read_text(encoding="utf-8"))
        self.assertEqual(alert_data["severity"], "CRITICAL")

    def test_08_orphan_process_after_completed_task_orphaned_process(self):
        """8. Orphan process running after task completion -> ORPHANED_PROCESS."""
        res = self.watchdog.scan(self.observation(
            process="godot --headless",
            elapsed_seconds=120,
            pid=44921,
            task_completed=True,
            is_orphan=True,
        ), self.now)
        self.assertEqual(res["classification"], "ORPHANED_PROCESS")
        self.assertIsNotNone(res["alert_path"])

    def test_09_duplicate_scans_single_incident_only(self):
        """9. Repeated scans of same problem key emit exactly one incident file."""
        stalled = self.observation(elapsed_seconds=360, last_progress_at=(self.now - dt.timedelta(seconds=301)).isoformat())
        first = self.watchdog.scan(stalled, self.now)
        second = self.watchdog.scan(stalled, self.now)
        restarted = SnitchWatchdog(self.repo).scan(stalled, self.now)

        alerts = list((self.repo / "events/runtime-alerts").glob("*.json"))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(first["alert_path"], alerts[0])
        self.assertEqual(second["alert_path"], alerts[0])
        self.assertEqual(restarted["alert_path"], alerts[0])

    def test_10_missing_provenance_unknown_no_cross_thread_alert(self):
        """10. Missing workflow/correlation provenance -> UNKNOWN, no cross-thread alert."""
        res = self.watchdog.scan(self.observation(
            elapsed_seconds=500,
            workflow_id=None,
            correlation_id=None,
        ), self.now)
        self.assertEqual(res["classification"], "UNKNOWN")
        self.assertIsNone(res["alert_path"])
        self.assertFalse((self.repo / "events/runtime-alerts").exists())

    def test_11_incident_recovery_resolves_without_duplication(self):
        """11. Incident resolution transitions status to RESOLVED without creating duplicates."""
        stalled = self.observation(elapsed_seconds=360, last_progress_at=(self.now - dt.timedelta(seconds=301)).isoformat())
        res = self.watchdog.scan(stalled, self.now)
        alert_path = res["alert_path"]
        dedupe_key = json.loads(alert_path.read_text(encoding="utf-8"))["dedupe_key"]

        success = self.watchdog.resolve_incident(dedupe_key, "Chief routed task to reserve Bodyguard Alpha")
        self.assertTrue(success)

        resolved_data = json.loads(alert_path.read_text(encoding="utf-8"))
        self.assertEqual(resolved_data["status"], "RESOLVED")
        self.assertIn("Bodyguard Alpha", resolved_data["resolution"])


if __name__ == "__main__":
    unittest.main()

