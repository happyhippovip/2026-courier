#!/usr/bin/env python3
"""Mission 203: Test Suite for Live HQ Telemetry Bridge & Visual Operations Watch."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.hq_telemetry_bridge import (
    HQTelemetryBridge,
    VisualState,
    STATE_TO_VISUAL_MAP,
)
from scripts.live_worker_registry import (
    AvailabilityClass,
    EventType,
    LiveWorkerRegistry,
    WorkerState,
)
from scripts.opportunity_queue import Opportunity, OpportunityQueue


class TestMission203LiveHQTelemetryBridge(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_203_test_"))
        self.registry = LiveWorkerRegistry(repo_dir=self.test_dir)
        self.bridge = HQTelemetryBridge(repo_dir=self.test_dir)
        self.queue_dir = self.test_dir / "events" / "opportunity-queue"
        self.state_dir = self.test_dir / "events" / "runtime-state"
        self.alerts_dir = self.test_dir / "events" / "runtime-alerts"
        self.events_dir = self.test_dir / "events" / "worker-events"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # Visual State Mapping & Speech Bubble Invariants
    # --------------------------------------------------------------------------

    def test_01_visual_state_mappings_and_invariants(self):
        # Progressing & Starting map to WORK
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.PROGRESSING.value), VisualState.WORK)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.STARTING.value), VisualState.WORK)

        # Idle & Available map to IDLE
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.SAFE_IDLE.value), VisualState.IDLE)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.AVAILABLE.value), VisualState.IDLE)

        # Permission & Human waits map to WAIT
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.WAITING_PERMISSION.value), VisualState.WAIT)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.WAITING_HUMAN.value), VisualState.WAIT)

        # Errors & Stalls map to ALERT
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.PROVIDER_ERROR.value), VisualState.ALERT)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.NETWORK_DEGRADED.value), VisualState.ALERT)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.RUNNING_NO_PROGRESS.value), VisualState.ALERT)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.HUNG.value), VisualState.ALERT)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.FAILED.value), VisualState.ALERT)
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.ORPHANED.value), VisualState.ALERT)

        # Completed maps to COMPLETE
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.COMPLETED.value), VisualState.COMPLETE)

        # Expired temporary worker maps to OFFLINE
        self.assertEqual(self.bridge.map_to_visual_state(WorkerState.AVAILABLE.value, is_expired=True), VisualState.OFFLINE)

        # CRITICAL INVARIANT: UNKNOWN must NOT map to WORK!
        vis_unknown = self.bridge.map_to_visual_state(WorkerState.UNKNOWN.value)
        self.assertEqual(vis_unknown, VisualState.UNKNOWN)
        self.assertNotEqual(vis_unknown, VisualState.WORK)

    def test_02_deterministic_speech_bubble_generation(self):
        w_prog = self.registry.register_worker("GOOGLE", "BUILDER", "ANTIGRAVITY", mission_id="M199")
        w_prog.state = WorkerState.PROGRESSING.value
        self.assertEqual(self.bridge.generate_speech_bubble(w_prog), "Arbeite an Mission M199.")

        w_idle = self.registry.register_worker("CODEX", "CHIEF", "CODEX")
        w_idle.state = WorkerState.SAFE_IDLE.value
        self.assertEqual(self.bridge.generate_speech_bubble(w_idle), "SAFE_IDLE — warte auf Arbeit.")

        w_perm = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w_perm.state = WorkerState.WAITING_PERMISSION.value
        self.assertEqual(self.bridge.generate_speech_bubble(w_perm), "Warte auf Berechtigung.")

        w_err = self.registry.register_worker("CLI2", "WORKER", "ANTIGRAVITY_BEATA")
        w_err.state = WorkerState.PROVIDER_ERROR.value
        self.assertEqual(self.bridge.generate_speech_bubble(w_err), "Provider-Verbindung gestört.")

        w_stall = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w_stall.state = WorkerState.RUNNING_NO_PROGRESS.value
        self.assertEqual(self.bridge.generate_speech_bubble(w_stall), "Keine neue Aktivität erkannt.")

        w_avail = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w_avail.state = WorkerState.AVAILABLE.value
        self.assertEqual(self.bridge.generate_speech_bubble(w_avail), "Frei für nächste sichere Aufgabe.")

    # --------------------------------------------------------------------------
    # Telemetry Snapshot & Multi-Worker Fleet Integration
    # --------------------------------------------------------------------------

    def test_03_four_worker_fleet_snapshot(self):
        # 1. Google Progressing on M199
        self.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY", mission_id="M199")
        self.registry.record_progress("GOOGLE", {"step": "active"}, task_id="TASK-199")

        # 2. Codex Reviewing (SAFE_IDLE)
        w_codex = self.registry.register_worker("CODEX", "CHIEF_STRATEGIST", "OPENAI_CODEX", mission_id="ORACLE")
        w_codex.state = WorkerState.SAFE_IDLE.value
        self.registry._save_worker_record(w_codex)

        # 3. CLI1 Progressing on M203
        self.registry.register_worker("CLI1", "OPERATIONS_ENGINEER", "ANTIGRAVITY", mission_id="M203")
        self.registry.record_progress("CLI1", {"step": "bridge"}, task_id="TASK-203")

        # 4. CLI2 Waiting for Permission
        w_cli2 = self.registry.register_worker("CLI2", "SECONDARY_AUTONOMOUS_WORKER", "ANTIGRAVITY_BEATA", mission_id="M201")
        self.registry.record_permission_blocked("CLI2", "Do you want to proceed?")

        snapshot = self.bridge.compile_hq_telemetry()
        self.assertEqual(snapshot["active_worker_count"], 2)  # GOOGLE and CLI1
        self.assertEqual(snapshot["free_worker_count"], 1)    # CODEX
        self.assertEqual(snapshot["alert_count"], 1)          # CLI2 waiting permission

        self.assertEqual(snapshot["workers"]["GOOGLE"]["visual_state"], "WORK")
        self.assertEqual(snapshot["workers"]["CODEX"]["visual_state"], "IDLE")
        self.assertEqual(snapshot["workers"]["CLI1"]["visual_state"], "WORK")
        self.assertEqual(snapshot["workers"]["CLI2"]["visual_state"], "WAIT")

        # Verify output file exists
        snap_path = self.test_dir / "events" / "runtime-state" / "hq_telemetry_snapshot.json"
        self.assertTrue(snap_path.is_file())

    # --------------------------------------------------------------------------
    # Network Incident Lifecycle (Progress -> Error -> Recovered -> Progress)
    # --------------------------------------------------------------------------

    def test_04_network_incident_lifecycle(self):
        w = self.registry.register_worker("CLI1", "OPERATIONS", "ANTIGRAVITY", mission_id="M203")
        self.registry.record_progress("CLI1", {"step": 1}, task_id="TASK-NET")

        # Step 1: Progressing -> Visual State WORK
        snap1 = self.bridge.compile_hq_telemetry()
        self.assertEqual(snap1["workers"]["CLI1"]["visual_state"], "WORK")

        # Step 2: Network error occurs -> Visual State ALERT
        self.registry.record_provider_failure("CLI1", "SSLHandshakeError: Connection dropped", is_network=True)
        snap2 = self.bridge.compile_hq_telemetry()
        self.assertEqual(snap2["workers"]["CLI1"]["visual_state"], "ALERT")
        self.assertEqual(snap2["workers"]["CLI1"]["provider_state"], "DEGRADED")
        self.assertIn("Netzwerkverbindung instabil", snap2["workers"]["CLI1"]["speech_bubble"])

        # Step 3: Network recovers on next progress -> Visual State WORK
        self.registry.record_progress("CLI1", {"step": 2, "reconnected": True}, task_id="TASK-NET")
        snap3 = self.bridge.compile_hq_telemetry()
        self.assertEqual(snap3["workers"]["CLI1"]["visual_state"], "WORK")
        self.assertEqual(snap3["workers"]["CLI1"]["provider_state"], "HEALTHY")

    # --------------------------------------------------------------------------
    # Temporary Resource Expiration
    # --------------------------------------------------------------------------

    def test_05_temporary_resource_expiry_in_telemetry(self):
        w_exp = self.registry.register_worker(
            "CLI2", "WORKER", "ANTIGRAVITY_BEATA",
            availability_class=AvailabilityClass.TEMPORARY_30_DAY,
            available_duration_seconds=-60.0,  # Expired
        )
        self.registry.audit_worker_liveness(w_exp, pid=None)

        snapshot = self.bridge.compile_hq_telemetry()
        self.assertEqual(snapshot["workers"]["CLI2"]["visual_state"], "OFFLINE")
        self.assertEqual(snapshot["workers"]["CLI2"]["availability"], "EXPIRED")
        self.assertIn("abgelaufen", snapshot["workers"]["CLI2"]["speech_bubble"])

    # --------------------------------------------------------------------------
    # Self-Observation, Worker Completion & Next Safe Work Signal
    # --------------------------------------------------------------------------

    def test_06_self_completion_and_next_work_chain(self):
        # 1. Populate safe task in OpportunityQueue
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-SAFE-NEXT",
            source="TEST",
            objective_id="OBJ1",
            project="TEST",
            description="Safe next engineering task",
            priority=10,
            status="READY",
        ))

        # 2. Register CLI1 working on M203
        self.registry.register_worker("CLI1", "OPERATIONS", "ANTIGRAVITY", mission_id="M203")
        self.registry.record_progress("CLI1", {"step": "finalizing"}, task_id="OPP-M203")

        # 3. CLI1 completes mission
        self.registry.record_worker_completed("CLI1", "RES-M203", {"pass": True})

        # 4. Telemetry should reflect CLI1 as IDLE / AVAILABLE and NEXT_SAFE_WORK_AVAILABLE emitted
        snapshot = self.bridge.compile_hq_telemetry()
        self.assertEqual(snapshot["workers"]["CLI1"]["visual_state"], "IDLE")

        feed = snapshot["chief_alert_feed"]
        event_types = [item["event_type"] for item in feed]
        self.assertIn(EventType.WORKER_COMPLETED.value, event_types)
        self.assertIn(EventType.NEXT_SAFE_WORK_AVAILABLE.value, event_types)
        self.assertEqual(self.bridge.telemetry["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
