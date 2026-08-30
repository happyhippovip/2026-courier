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

from scripts.run_snitch_watchdog import (
    RuntimeObservation,
    SnitchWatchdog,
    PermissionGuard,
    PermissionMasterlist,
    SandboxAuditor,
)
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


class PermissionGuardTests(unittest.TestCase):
    """Deterministic tests for SNITCH 3.0 Permission Guard and Sandbox Auditor."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.guard = PermissionGuard(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def test_01_known_localhost_curl_already_allowed(self):
        """1. Known localhost curl -> ALREADY_ALLOWED."""
        res_ip = self.guard.audit("curl -s http://127.0.0.1:8088/api/state")
        res_host = self.guard.audit("curl http://localhost:8088/api/state")
        self.assertEqual(res_ip["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_host["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_ip["existing_rule_match"], "LOCALHOST_HEALTH_CHECKS")
        self.assertEqual(res_ip["risk_class"], "SAFE")
        self.assertEqual(res_ip["status_label"], "PERMISSIONS HEALTHY")

    def test_02_known_studio_launcher_already_allowed(self):
        """2. Known Studio launcher -> ALREADY_ALLOWED."""
        res_launcher = self.guard.audit("python3 scripts/launch_visual_studio.py")
        res_status = self.guard.audit("python3 scripts/launch_visual_studio.py --status")
        res_server = self.guard.audit("python3 scripts/run_visual_studio_server.py")
        self.assertEqual(res_launcher["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_status["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_server["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_launcher["existing_rule_match"], "STUDIO_LIFECYCLE")

    def test_03_new_safe_project_script_recommended(self):
        """3. New safe project script in scripts/ -> SAFE_PROJECT_RULE_RECOMMENDED."""
        res = self.guard.audit("python3 scripts/run_custom_optimizer.py")
        self.assertEqual(res["classification"], "SAFE_PROJECT_RULE_RECOMMENDED")
        self.assertEqual(res["status_label"], "NEW SAFE RULE")
        self.assertEqual(res["recommended_action"], "ADD_PERSISTENT_PROJECT_RULE")
        self.assertIn("recurring project rule", res["speech"])

    def test_04_generic_pkill_one_time_only(self):
        """4. Generic or scoped pkill -> ONE_TIME_ONLY (never permanent allow)."""
        res_generic = self.guard.audit("pkill python3")
        self.assertEqual(res_generic["classification"], "ONE_TIME_ONLY")
        self.assertEqual(res_generic["status_label"], "ONE-TIME APPROVAL")
        self.assertIn("One-time approval is safer", res_generic["speech"])

        res_studio = self.guard.audit("pkill -f run_visual_studio_server.py")
        self.assertEqual(res_studio["classification"], "ONE_TIME_ONLY")
        self.assertEqual(res_studio["safer_equivalent"], "python3 scripts/launch_visual_studio.py")

    def test_05_rm_rf_dangerous_do_not_persist(self):
        """5. rm -rf -> DANGEROUS_DO_NOT_PERSIST."""
        res1 = self.guard.audit("rm -rf /tmp/build")
        res2 = self.guard.audit("rm -r -f data/cache")
        self.assertEqual(res1["classification"], "DANGEROUS_DO_NOT_PERSIST")
        self.assertEqual(res2["classification"], "DANGEROUS_DO_NOT_PERSIST")
        self.assertEqual(res1["risk_class"], "CRITICAL")
        self.assertEqual(res1["status_label"], "DANGEROUS REQUEST")
        self.assertIn("Dangerous command detected", res1["speech"])

    def test_06_sudo_dangerous_do_not_persist(self):
        """6. sudo -> DANGEROUS_DO_NOT_PERSIST."""
        res = self.guard.audit("sudo apt-get install ffmpeg")
        self.assertEqual(res["classification"], "DANGEROUS_DO_NOT_PERSIST")
        self.assertEqual(res["risk_class"], "CRITICAL")
        self.assertEqual(res["status_label"], "DANGEROUS REQUEST")

    def test_07_existing_prefix_variation_correct_rule_match(self):
        """7. Existing prefix variations match correct rule family."""
        res_git = self.guard.audit("git push origin main")
        res_status = self.guard.audit("git status --short")
        res_node = self.guard.audit("node tests/test_execution_truth.mjs")
        self.assertEqual(res_git["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_status["classification"], "ALREADY_ALLOWED")
        self.assertEqual(res_node["classification"], "ALREADY_ALLOWED")

    def test_08_duplicate_permission_event_no_alert_spam(self):
        """8. Duplicate permission wait events produce only one incident file."""
        unknown_res = self.guard.audit("unregistered_daemon --run")
        first_alert = self.guard.create_permission_incident(unknown_res, agent_id="Gravity")
        second_alert = self.guard.create_permission_incident(unknown_res, agent_id="Gravity")

        alerts = list((self.repo / "events/runtime-alerts").glob("*.json"))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(first_alert, second_alert)
        self.assertEqual(first_alert, alerts[0])

    def test_09_unknown_command_unknown(self):
        """9. Unknown command -> UNKNOWN."""
        res = self.guard.audit("completely_unknown_cli_tool --action test")
        self.assertEqual(res["classification"], "UNKNOWN")
        self.assertEqual(res["status_label"], "PERMISSION WAIT")
        self.assertIn("not in the project masterlist", res["speech"])

    def test_10_zero_model_calls_pure_deterministic(self):
        """10. Permission Guard audit executes deterministically with 0 model calls."""
        res = self.guard.audit("git status")
        self.assertIsNotNone(res["classification"])
        self.assertIn("requested_command", res)
        # SandboxAuditor alias matches PermissionGuard
        auditor = SandboxAuditor(self.repo)
        self.assertEqual(auditor.audit("git log")["classification"], "ALREADY_ALLOWED")


if __name__ == "__main__":
    unittest.main()


