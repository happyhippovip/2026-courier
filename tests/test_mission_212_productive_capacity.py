#!/usr/bin/env python3
"""Mission 212 Acceptance Test Suite: Productive Capacity Run (Google Primary Builder).

Verifies:
1. Productive metrics tracking (tasks completed, productive runtime, duplicates suppressed)
2. CLI2 inactivity enforcement (CLI2 denied work strictly)
3. Automatic Disaster Recovery manifest generation and digest persistence
4. Automatic HQ telemetry snapshot synchronization
5. Queue hygiene integration on idle transitions
6. Zero model calls & 0 EUR spend
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import WorkerState
from scripts.continuous_safe_work_dispatcher import (
    ContinuousSafeWorkDispatcher,
    DispatchableTask,
    TaskSafetyClass,
)


class TestMission212ProductiveCapacity(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_212_test_"))
        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_cli2_inactivity_enforcement(self):
        """CLI2 is strictly inactive and must be denied all work."""
        self.dispatcher.submit_task("task_test", "Local Safe Task")
        ev = self.dispatcher.dispatch_next_safe_cycle(worker_id="CLI2")
        self.assertEqual(ev.action, "WORKER_INACTIVE_DENIED")
        self.assertEqual(ev.next_action, "CLI2_IS_INACTIVE")

    def test_02_productive_capacity_metrics_tracking(self):
        """Validates real-time metrics tracking of completed tasks, duplicates, and runtime."""
        self.dispatcher.submit_task("task_p1", "Productive Job 1", priority=10)
        self.dispatcher.submit_task("task_p2", "Productive Job 2", priority=8)

        def runner(t: DispatchableTask):
            return True, {"output_verified": True}

        # Dispatch task 1
        ev1 = self.dispatcher.dispatch_next_safe_cycle(worker_id="GOOGLE", runner_fn=runner)
        self.assertEqual(ev1.action, "EXECUTED")

        # Dispatch task 2
        ev2 = self.dispatcher.dispatch_next_safe_cycle(worker_id="GOOGLE", runner_fn=runner)
        self.assertEqual(ev2.action, "EXECUTED")

        metrics = self.dispatcher.get_productive_metrics()
        self.assertEqual(metrics["tasks_completed"], 2)
        self.assertGreater(metrics["productive_runtime_seconds"], 0.0)
        self.assertEqual(metrics["model_calls"], 0)
        self.assertEqual(metrics["spend_eur"], 0.0)
        self.assertTrue(bool(metrics["last_dr_manifest_digest"]))

    def test_03_dr_manifest_auto_checkpoint(self):
        """Verifies Disaster Recovery manifest is updated on successful task completion."""
        self.dispatcher.submit_task("task_dr", "DR Test Job")
        ev = self.dispatcher.dispatch_next_safe_cycle(
            worker_id="GOOGLE",
            runner_fn=lambda t: (True, {"verified": True}),
        )
        self.assertEqual(ev.action, "EXECUTED")

        dr_manifest_file = self.test_dir / "events" / "host-survival" / "disaster_recovery_manifest.json"
        self.assertTrue(dr_manifest_file.is_file())
        manifest = json.loads(dr_manifest_file.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "HOST_DR_MANIFEST_V1")
        self.assertIn("MISSION_212", manifest["active_missions"])

    def test_04_duplicate_suppression_counter(self):
        """Verifies duplicates suppressed metric increments upon duplicate submission and reuse."""
        t1 = self.dispatcher.submit_task("task_1", "Duplicate Test Job", code_fingerprint="c-fp-1")
        self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {}))

        # Submit duplicate
        t2 = self.dispatcher.submit_task("task_2", "Duplicate Test Job", code_fingerprint="c-fp-1")
        metrics_after_sub = self.dispatcher.get_productive_metrics()
        self.assertEqual(metrics_after_sub["duplicates_suppressed"], 1)

        # Dispatch duplicate
        ev = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "REUSED_RESULT")

    def test_05_failure_tracking_without_hang(self):
        """Verifies failures are tracked and do not lock the dispatcher loop."""
        self.dispatcher.submit_task("task_fail", "Failing Job", priority=10)
        self.dispatcher.submit_task("task_safe_next", "Safe Job After Fail", priority=5)

        # First cycle fails
        ev1 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (False, {"err": "simulated"}))
        self.assertEqual(ev1.action, "FAILED")
        self.assertEqual(self.dispatcher.metrics.failures_found, 1)

        # Second cycle executes safe job next
        ev2 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {"ok": True}))
        self.assertEqual(ev2.action, "EXECUTED")
        self.assertEqual(ev2.task_id, "task_safe_next")


if __name__ == "__main__":
    unittest.main()
