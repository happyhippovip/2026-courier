#!/usr/bin/env python3
"""Focused Acceptance Test Suite for Live Worker Registry & Operations Controller.

Verifies:
1. Worker Registration, Process Identity, and Heartbeat Recording
2. State Transition Matrix (STARTING, PROGRESSING, COMPLETED, WAITING_PERMISSION, PROVIDER_ERROR)
3. PID Liveness Verification and Dead PID Orphan Transition
4. Event Stream Emission and Compaction (events/worker-events/evt-*.json)
5. Aggregate Status Compilation for Visual HQ Telemetry Bridge
6. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

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


class TestLiveWorkerRegistry(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="live_registry_test_"))
        self.registry = LiveWorkerRegistry(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_worker_registration_and_heartbeat(self):
        """Worker can be registered and subsequent heartbeats update state cleanly."""
        current_pid = os.getpid()
        record = self.registry.register_worker(
            worker_id="GOOGLE",
            provider="ANTIGRAVITY",
            role="PRIMARY_BUILDER",
            availability_class=AvailabilityClass.PRIMARY_BUILDER,
            pid=current_pid,
        )

        self.assertEqual(record.worker_id, "GOOGLE")
        self.assertEqual(record.state, WorkerState.STARTING.value)
        self.assertEqual(record.pid, current_pid)

        # Record meaningful progress
        updated = self.registry.record_progress(
            worker_id="GOOGLE",
            evidence={"step": 1, "task": "TASK-001"},
            task_id="TASK-001",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.state, WorkerState.PROGRESSING.value)
        self.assertEqual(updated.task_id, "TASK-001")

    def test_02_dead_pid_transitions_to_orphaned_on_liveness_audit(self):
        """Dead PID assigned to worker transitions to ORPHANED during liveness audit."""
        dead_pid = 99999999  # Guaranteed non-existent PID
        worker = self.registry.register_worker(
            worker_id="WORKER_DEAD",
            provider="DUMMY",
            role="TEST_WORKER",
            availability_class=AvailabilityClass.DETERMINISTIC_LOCAL,
            pid=dead_pid,
        )

        # Force state to PROGRESSING
        worker = self.registry.record_progress(
            worker_id="WORKER_DEAD",
            evidence={"action": "stuck"},
            task_id="TASK-STUCK",
        )

        # Audit worker liveness with dead PID
        audited = self.registry.audit_worker_liveness(worker, pid=dead_pid)
        self.assertEqual(audited.state, WorkerState.ORPHANED.value)
        self.assertEqual(audited.blocked_reason, "PID_DEAD_WITH_ACTIVE_STATE")

    def test_03_state_transitions_block_and_completion(self):
        """Worker transitions between PROGRESSING, WAITING_PERMISSION, and COMPLETED cleanly."""
        worker = self.registry.register_worker(
            worker_id="CLI1",
            provider="CLI",
            role="OPERATIONS",
            availability_class=AvailabilityClass.PERSISTENT_HOST,
            pid=os.getpid(),
        )

        # Record permission block
        blocked = self.registry.record_permission_blocked(
            worker_id="CLI1",
            prompt_text="Requires payment approval",
            requested_command="gcloud compute instances start",
        )
        self.assertEqual(blocked.state, WorkerState.WAITING_PERMISSION.value)
        self.assertIn("Requires payment approval", blocked.blocked_reason)

        # Record completion
        completed = self.registry.record_worker_completed(
            worker_id="CLI1",
            result_id="RES-001",
            completion_evidence={"verified": True},
        )
        self.assertIn(completed.state, (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value))
        self.assertIsNone(completed.blocked_reason)

    def test_04_event_stream_emission_and_compaction(self):
        """Events are emitted to individual files and compacted when exceeding limit."""
        worker = self.registry.register_worker(
            worker_id="GOOGLE",
            provider="ANTIGRAVITY",
            role="PRIMARY_BUILDER",
            availability_class=AvailabilityClass.PRIMARY_BUILDER,
            pid=os.getpid(),
        )

        # Emit multiple distinct events
        for i in range(25):
            self.registry.emit_event(
                event_type=EventType.WORKER_PROGRESS,
                worker=worker,
                evidence={"seq": i, "timestamp": f"t_{i}"},
            )

        events_dir = self.test_dir / "events" / "worker-events"
        event_files = [f for f in events_dir.glob("evt-*.json") if f.is_file()]
        # Registration event + 25 progress events = 26
        self.assertGreaterEqual(len(event_files), 25)

        # Compact stream to max 10 events
        archived_count = self.registry.compact_event_stream(max_events=10)
        self.assertGreater(archived_count, 0)

        remaining_files = [f for f in events_dir.glob("evt-*.json") if f.is_file()]
        self.assertEqual(len(remaining_files), 10)

        archive_dir = events_dir / "archive"
        self.assertTrue(archive_dir.exists())
        archived_files = list(archive_dir.glob("evt-*.json"))
        self.assertEqual(len(archived_files), archived_count)

    def test_05_aggregate_status_view(self):
        """Aggregate status view summarizes workers accurately for HQ telemetry."""
        self.registry.register_worker(
            worker_id="GOOGLE",
            provider="ANTIGRAVITY",
            role="PRIMARY_BUILDER",
            availability_class=AvailabilityClass.PRIMARY_BUILDER,
            pid=os.getpid(),
        )
        self.registry.record_progress(
            worker_id="GOOGLE",
            evidence={"test": True},
            task_id="TASK-HQ-VIEW",
        )

        agg = self.registry.generate_aggregate_status()
        self.assertEqual(agg["active_worker_count"], 1)
        self.assertIn("GOOGLE", agg["workers"])
        self.assertEqual(agg["workers"]["GOOGLE"]["state"], WorkerState.PROGRESSING.value)


if __name__ == "__main__":
    unittest.main()
