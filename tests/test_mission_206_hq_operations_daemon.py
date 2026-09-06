#!/usr/bin/env python3
"""Mission 206: Acceptance Test Suite for Live HQ Operations Daemon."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.hq_operations_daemon import (
    DaemonEventType,
    DaemonHealth,
    HQOperationsDaemon,
)
from scripts.live_worker_registry import (
    AvailabilityClass,
    EventType,
    LiveWorkerRegistry,
    WorkerState,
)
from scripts.hq_telemetry_bridge import VisualState


class TestMission206HQOperationsDaemon(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_206_test_"))
        self.daemon = HQOperationsDaemon(repo_dir=self.test_dir)
        self.events_dir = self.test_dir / "events"
        self.alerts_dir = self.events_dir / "runtime-alerts"
        self.worker_events_dir = self.events_dir / "worker-events"
        self.state_dir = self.events_dir / "runtime-state"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # Test 1: Worker Progress & Speech Bubble Payloads
    # --------------------------------------------------------------------------

    def test_01_worker_progressing_and_speech_payload(self):
        self.daemon.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY", mission_id="M204", pid=os.getpid())
        self.daemon.registry.record_progress("GOOGLE", {"step": "AUTHORITY_REMEDIATION"}, task_id="OPP-M204")

        self.daemon.run_daemon_cycle()

        snap_file = self.state_dir / "hq_telemetry_snapshot.json"
        self.assertTrue(snap_file.is_file())
        snap = json.loads(snap_file.read_text(encoding="utf-8"))

        google = snap["workers"]["GOOGLE"]
        self.assertEqual(google["visual_state"], "WORK")
        self.assertIn("M204", google["speech_text"])
        self.assertFalse(google["leisure_eligible"])

    # --------------------------------------------------------------------------
    # Test 2: Release Blocker Signal by CLI2
    # --------------------------------------------------------------------------

    def test_02_cli2_release_blocker_detection(self):
        self.daemon.registry.register_worker("CLI2", "SECONDARY_AUTONOMOUS_WORKER", "ANTIGRAVITY_BEATA", mission_id="M205")

        alert_path = self.daemon.record_release_blocker(
            worker_id="CLI2",
            mission_id="M205",
            component="RESOURCE_RESET",
            defect_description="Lock race condition detected during simultaneous account switch",
            severity="HIGH",
            evidence_ref="tests/test_lock_race.py:L45",
        )

        self.assertTrue(alert_path.is_file())
        self.assertEqual(len(self.daemon.unresolved_high_blockers), 1)

        # High priority alert must be in runtime-alerts
        alerts = list(self.alerts_dir.glob("*.json"))
        self.assertGreaterEqual(len(alerts), 1)
        alert_data = json.loads(alert_path.read_text(encoding="utf-8"))
        self.assertEqual(alert_data["event_type"], DaemonEventType.RELEASE_BLOCKER_FOUND.value)
        self.assertEqual(alert_data["severity"], "HIGH")

    # --------------------------------------------------------------------------
    # Test 3: Builder Remediation Complete & Candidate Availability
    # --------------------------------------------------------------------------

    def test_03_builder_remediation_complete_signal(self):
        self.daemon.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY", mission_id="M204")

        self.daemon.record_builder_remediation_complete(
            candidate_hash="a1b2c3d4e5f6",
            google_mission_id="M204",
            ready_for_codex=True,
        )

        self.assertEqual(self.daemon.builder_finished_candidate, "a1b2c3d4e5f6")
        google_worker = self.daemon.registry.get_worker("GOOGLE")
        self.assertEqual(google_worker.state, WorkerState.COMPLETED.value)

        # Verify events emitted
        events = [json.loads(f.read_text(encoding="utf-8")) for f in self.worker_events_dir.glob("*.json")]
        evt_types = [e["event_type"] for e in events]
        self.assertIn(DaemonEventType.BUILDER_REMEDIATION_COMPLETE.value, evt_types)
        self.assertIn(DaemonEventType.CODEX_ACCEPTANCE_CANDIDATE_AVAILABLE.value, evt_types)

    # --------------------------------------------------------------------------
    # Test 4: Final Acceptance Readiness Conditions
    # --------------------------------------------------------------------------

    def test_04_final_acceptance_ready_only_when_both_conditions_met(self):
        self.daemon.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY", mission_id="M204")
        self.daemon.registry.register_worker("CLI2", "SECONDARY_AUTONOMOUS_WORKER", "ANTIGRAVITY_BEATA", mission_id="M205")
        self.daemon.registry.register_worker("CODEX", "CHIEF_STRATEGIST", "OPENAI_CODEX")

        # Scenario A: Builder finished, BUT CLI2 has an active unresolved blocker
        self.daemon.record_release_blocker("CLI2", "M205", "AUTH", "Unresolved auth token leakage", severity="HIGH")
        self.daemon.record_builder_remediation_complete("candidate-hash-123")

        # Must NOT be ready for final acceptance yet!
        self.assertFalse(self.daemon.evaluate_final_acceptance_readiness())

        # Scenario B: Blocker is cleared
        blocker_fp = self.daemon.unresolved_high_blockers[0]["fingerprint"]
        self.daemon.clear_release_blocker(blocker_fp)
        self.daemon.record_adversarial_review_complete("M205", {"all_passed": True})

        # NOW both conditions are satisfied -> Must signal FINAL_ACCEPTANCE_READY
        self.assertTrue(self.daemon.evaluate_final_acceptance_readiness())

        events = [json.loads(f.read_text(encoding="utf-8")) for f in self.worker_events_dir.glob("*.json")]
        evt_types = [e["event_type"] for e in events]
        self.assertIn(DaemonEventType.FINAL_ACCEPTANCE_READY.value, evt_types)

    # --------------------------------------------------------------------------
    # Test 5: Bar & Sauna Leisure Animation Compatibility
    # --------------------------------------------------------------------------

    def test_05_bar_and_sauna_leisure_animation_compatibility(self):
        # 1. Available / Safe Idle Worker -> Leisure Eligible
        w_idle = self.daemon.registry.register_worker("CODEX", "CHIEF", "OPENAI_CODEX")
        w_idle.state = WorkerState.SAFE_IDLE.value
        self.daemon.registry._save_worker_record(w_idle)

        # 2. Progressing Worker -> Leisure Ineligible
        w_prog = self.daemon.registry.register_worker("GOOGLE", "BUILDER", "ANTIGRAVITY")
        w_prog.state = WorkerState.PROGRESSING.value
        self.daemon.registry._save_worker_record(w_prog)

        # 3. Blocked Worker -> Leisure Ineligible
        w_blocked = self.daemon.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w_blocked.state = WorkerState.WAITING_PERMISSION.value
        self.daemon.registry._save_worker_record(w_blocked)

        self.daemon.run_daemon_cycle()

        snap = json.loads((self.state_dir / "hq_telemetry_snapshot.json").read_text(encoding="utf-8"))
        self.assertTrue(snap["workers"]["CODEX"]["leisure_eligible"])
        self.assertFalse(snap["workers"]["GOOGLE"]["leisure_eligible"])
        self.assertFalse(snap["workers"]["CLI1"]["leisure_eligible"])

    # --------------------------------------------------------------------------
    # Test 6: Daemon Health & Restart Deduplication
    # --------------------------------------------------------------------------

    def test_06_daemon_health_and_restart_deduplication(self):
        # Initial cycle publishes health
        self.daemon.run_daemon_cycle()
        health_file = self.state_dir / "daemon_health.json"
        self.assertTrue(health_file.is_file())
        hdata = json.loads(health_file.read_text(encoding="utf-8"))
        self.assertTrue(hdata["observer_alive"])
        self.assertEqual(hdata["registry_health"], "HEALTHY")

        # Emit an alert
        self.daemon.record_release_blocker("CLI2", "M205", "LOCK", "Deadlock test", severity="HIGH")
        alerts_count_before = len(list(self.alerts_dir.glob("*.json")))

        # Simulate Daemon Restart
        restarted_daemon = HQOperationsDaemon(repo_dir=self.test_dir)
        self.assertGreaterEqual(len(restarted_daemon._known_alert_fingerprints), 1)

        # Re-evaluating same condition after restart must NOT spam new alert files
        restarted_daemon.run_daemon_cycle()
        alerts_count_after = len(list(self.alerts_dir.glob("*.json")))
        self.assertEqual(alerts_count_before, alerts_count_after)
        self.assertEqual(restarted_daemon.daemon_model_calls if hasattr(restarted_daemon, "daemon_model_calls") else 0, 0)


if __name__ == "__main__":
    unittest.main()
