#!/usr/bin/env python3
"""Mission 200: Live Operations Control, Worker Registry & Snitch Test Suite."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.live_worker_registry import (
    AvailabilityClass,
    EventType,
    LiveWorkerRegistry,
    WorkerRecord,
    WorkerState,
)
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.queue_hygiene_manager import QueueHygieneManager


class TestMission200LiveOperationsControl(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_200_test_"))
        self.registry = LiveWorkerRegistry(repo_dir=self.test_dir)
        self.queue_dir = self.test_dir / "events" / "opportunity-queue"
        self.alerts_dir = self.test_dir / "events" / "runtime-alerts"
        self.events_dir = self.test_dir / "events" / "worker-events"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_worker_registration_and_temporary_resource_policy(self):
        # Register CLI1 as Temporary 30-Day Resource
        w1 = self.registry.register_worker(
            worker_id="CLI1",
            role="OPERATIONS_ENGINEER",
            provider="ANTIGRAVITY",
            availability_class=AvailabilityClass.TEMPORARY_30_DAY,
            available_duration_seconds=30 * 86400,
            mission_id="M200",
        )
        self.assertEqual(w1.worker_id, "CLI1")
        self.assertEqual(w1.availability_class, "TEMPORARY_30_DAY")
        self.assertIsNotNone(w1.available_until)
        self.assertFalse(w1.is_expired())

        # Register Codex as Persistent Host
        w2 = self.registry.register_worker(
            worker_id="CODEX",
            role="CHIEF_STRATEGIST",
            provider="OPENAI_CODEX",
            availability_class=AvailabilityClass.PERSISTENT_HOST,
            mission_id="ORACLE",
        )
        self.assertEqual(w2.worker_id, "CODEX")
        self.assertEqual(w2.availability_class, "PERSISTENT_HOST")
        self.assertIsNone(w2.available_until)
        self.assertFalse(w2.is_expired())

    def test_02_temporary_resource_expiry_behavior(self):
        # Register a temporary worker with -10s duration (already expired)
        w_exp = self.registry.register_worker(
            worker_id="CLI2",
            role="SECONDARY_AUTONOMOUS_WORKER",
            provider="ANTIGRAVITY_BEATA",
            availability_class=AvailabilityClass.TEMPORARY_30_DAY,
            available_duration_seconds=-10.0,
        )
        self.assertTrue(w_exp.is_expired())

        # Auditing the expired worker should mark it EXPIRED / UNKNOWN
        audited = self.registry.audit_worker_liveness(w_exp, pid=None)
        self.assertEqual(audited.availability_class, AvailabilityClass.EXPIRED.value)
        self.assertEqual(audited.state, WorkerState.UNKNOWN.value)
        self.assertEqual(audited.blocked_reason, "30_DAY_RESOURCE_WINDOW_EXPIRED")

    def test_03_meaningful_progress_and_deduplicated_events(self):
        w = self.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY")

        # Record verified meaningful progress
        evidence1 = {"test_pass_count": 84, "step": "SAFETY_ORACLE"}
        self.registry.record_progress(
            worker_id="GOOGLE",
            evidence=evidence1,
            task_id="TASK-SAFETY-1",
            mission_id="M199",
        )

        w_updated = self.registry.get_worker("GOOGLE")
        self.assertEqual(w_updated.state, WorkerState.PROGRESSING.value)
        self.assertEqual(w_updated.task_id, "TASK-SAFETY-1")
        self.assertEqual(w_updated.mission_id, "M199")

        # Emitting identical event must be deduplicated
        fp1 = self.registry.compute_event_fingerprint(EventType.WORKER_PROGRESS, w_updated, evidence1)
        self.registry.emit_event(EventType.WORKER_PROGRESS, w_updated, evidence1)
        self.assertEqual(self.registry.telemetry["duplicate_events_suppressed"], 1)

    def test_04_permission_prompt_detection(self):
        w = self.registry.register_worker("CLI1", "OPERATIONS", "ANTIGRAVITY")
        self.registry.record_permission_blocked(
            worker_id="CLI1",
            prompt_text="Do you want to proceed with tool call? [y/N]",
            requested_command="python3 -m unittest",
        )

        w_updated = self.registry.get_worker("CLI1")
        self.assertEqual(w_updated.state, WorkerState.WAITING_PERMISSION.value)
        self.assertIn("TOOL_PERMISSION_PROMPT", w_updated.blocked_reason)

        # High severity alert must be written to runtime-alerts
        alerts = list(self.alerts_dir.glob("*.json"))
        self.assertGreaterEqual(len(alerts), 1)

    def test_05_provider_error_and_recovery_with_task_preservation(self):
        w = self.registry.register_worker("CLI1", "OPERATIONS", "ANTIGRAVITY")
        self.registry.record_progress("CLI1", {"step": 1}, task_id="TASK-IN-FLIGHT")

        # Simulate provider network disconnection
        self.registry.record_provider_failure(
            worker_id="CLI1",
            failure_reason="HTTPSConnectionPool: Connection reset by peer",
            is_network=True,
        )

        w_degraded = self.registry.get_worker("CLI1")
        self.assertEqual(w_degraded.state, WorkerState.NETWORK_DEGRADED.value)
        # Task ID must be strictly preserved!
        self.assertEqual(w_degraded.task_id, "TASK-IN-FLIGHT")

        # On next meaningful progress, must emit RECOVERED and return to PROGRESSING
        self.registry.record_progress("CLI1", {"step": 2, "resumed": True})
        w_recovered = self.registry.get_worker("CLI1")
        self.assertEqual(w_recovered.state, WorkerState.PROGRESSING.value)
        self.assertEqual(w_recovered.task_id, "TASK-IN-FLIGHT")

    def test_06_stall_detection_and_orphaned_process_detection(self):
        w = self.registry.register_worker("CLI1", "OPERATIONS", "ANTIGRAVITY")
        w.state = WorkerState.PROGRESSING.value

        # Stale activity on live PID -> RUNNING_NO_PROGRESS
        now_ts = time.time()
        audited_stall = self.registry.audit_worker_liveness(
            worker=w,
            pid=os.getpid(),
            last_activity_ts=now_ts - 200.0,
            stall_threshold_seconds=100.0,
        )
        self.assertEqual(audited_stall.state, WorkerState.RUNNING_NO_PROGRESS.value)

        # Dead PID on active worker -> ORPHANED
        w.state = WorkerState.PROGRESSING.value
        audited_orphan = self.registry.audit_worker_liveness(
            worker=w,
            pid=99999999,  # Non-existent dead PID
            last_activity_ts=now_ts,
        )
        self.assertEqual(audited_orphan.state, WorkerState.ORPHANED.value)

    def test_07_worker_completed_to_available_and_next_safe_work_chain(self):
        # 1. Populate active OpportunityQueue with a safe ready task
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-TEST-NEXT-SAFE",
            source="TEST",
            objective_id="OBJ1",
            project="TEST_PROJECT",
            description="Verified safe next unit of work",
            priority=9,
            status="READY",
        ))

        # 2. Register worker in progress
        w = self.registry.register_worker("CLI1", "OPERATIONS", "ANTIGRAVITY")
        self.registry.record_progress("CLI1", {"step": 1}, task_id="OPP-OLD-TASK")

        # 3. Worker completes mission -> Transitions to COMPLETED then AVAILABLE and auto-signals NEXT_SAFE_WORK_AVAILABLE
        self.registry.record_worker_completed(
            worker_id="CLI1",
            result_id="RES-M200-SUCCESS",
            completion_evidence={"verified": True},
        )

        w_available = self.registry.get_worker("CLI1")
        self.assertEqual(w_available.state, WorkerState.AVAILABLE.value)
        self.assertEqual(w_available.last_result_id, "RES-M200-SUCCESS")

        # Verify NEXT_SAFE_WORK_AVAILABLE event was emitted
        events = [json.loads(f.read_text(encoding="utf-8")) for f in self.events_dir.glob("*.json")]
        evt_types = [e.get("event_type") for e in events]
        self.assertIn(EventType.WORKER_COMPLETED.value, evt_types)
        self.assertIn(EventType.WORKER_AVAILABLE.value, evt_types)
        self.assertIn(EventType.NEXT_SAFE_WORK_AVAILABLE.value, evt_types)

    def test_08_aggregate_status_view_generation(self):
        self.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY", mission_id="M199")
        self.registry.record_progress("GOOGLE", {"step": "active"})

        self.registry.register_worker("CODEX", "CHIEF_STRATEGIST", "OPENAI_CODEX", mission_id="ORACLE")
        w_codex = self.registry.get_worker("CODEX")
        w_codex.state = WorkerState.SAFE_IDLE.value
        self.registry._save_worker_record(w_codex)

        self.registry.register_worker("CLI1", "OPERATIONS_ENGINEER", "ANTIGRAVITY", mission_id="M200")
        self.registry.record_progress("CLI1", {"step": "scouting"})

        self.registry.register_worker("CLI2", "SECONDARY_AUTONOMOUS_WORKER", "ANTIGRAVITY_BEATA", mission_id="M201")
        w_cli2 = self.registry.get_worker("CLI2")
        w_cli2.state = WorkerState.SAFE_IDLE.value
        self.registry._save_worker_record(w_cli2)

        status = self.registry.generate_aggregate_status()
        self.assertIn("workers", status)
        self.assertEqual(status["workers"]["GOOGLE"]["state"], "PROGRESSING")
        self.assertEqual(status["workers"]["CODEX"]["state"], "SAFE_IDLE")
        self.assertEqual(status["workers"]["CLI1"]["state"], "PROGRESSING")
        self.assertEqual(status["workers"]["CLI2"]["state"], "SAFE_IDLE")
        self.assertIn("CODEX", status["free_workers"])
        self.assertIn("CLI2", status["free_workers"])
        self.assertEqual(self.registry.telemetry["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
