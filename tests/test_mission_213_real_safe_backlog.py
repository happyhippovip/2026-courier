#!/usr/bin/env python3
"""Mission 213 Acceptance Test Suite: Real Safe Backlog Capacity Run (Google Primary Builder).

Verifies:
1. Real bounded backlog creation and continuous batch execution (run_continuous_backlog_batch)
2. No WEITER required across multi-task execution
3. Opportunity queue dynamic ingestion
4. Clean SAFE_IDLE transition when backlog completes
5. Event stream compaction & queue hygiene integration
6. 0 Model calls & 0 EUR spend
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
from scripts.live_worker_registry import EventType


class TestMission213RealSafeBacklog(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_213_test_"))
        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_real_backlog_continuous_batch_execution(self):
        """Executes a backlog of 6 real safe engineering tasks continuously in a single batch without WEITER."""
        backlog_tasks = [
            ("TASK-213-01", "Queue Ingestion Bridge Hardening", 10, []),
            ("TASK-213-02", "Orphan Lock Hygiene Reconciliation", 9, ["TASK-213-01"]),
            ("TASK-213-03", "DR Manifest Post-Reboot Verification", 8, ["TASK-213-02"]),
            ("TASK-213-04", "Telemetry Event Stream Compaction", 7, ["TASK-213-03"]),
            ("TASK-213-05", "Continuous Dispatcher Resilience Loop", 6, ["TASK-213-04"]),
            ("TASK-213-06", "Benchmark Productive Capacity Suite", 5, ["TASK-213-05"]),
        ]

        for tid, obj, prio, deps in backlog_tasks:
            self.dispatcher.submit_task(tid, obj, priority=prio, dependencies=deps)

        self.assertEqual(len(self.dispatcher.tasks), 6)

        executed_tasks = []

        def safe_runner(t: DispatchableTask):
            executed_tasks.append(t.task_id)
            return True, {"verified_output": f"artifact-{t.task_id}"}

        # Run continuous batch
        summary = self.dispatcher.run_continuous_backlog_batch(
            worker_id="GOOGLE",
            max_tasks=10,
            runner_fn=safe_runner,
        )

        self.assertEqual(summary["tasks_started"], 6)
        self.assertEqual(summary["tasks_completed"], 6)
        self.assertEqual(summary["current_state"], WorkerState.SAFE_IDLE.value)
        self.assertEqual(summary["model_calls"], 0)
        self.assertEqual(summary["spend_eur"], 0.0)
        self.assertEqual(
            executed_tasks,
            ["TASK-213-01", "TASK-213-02", "TASK-213-03", "TASK-213-04", "TASK-213-05", "TASK-213-06"],
        )

    def test_02_opportunity_queue_ingestion_and_ranking(self):
        """Verifies ingestion of opportunity queue files from disk into dispatchable tasks."""
        # Create a mock opportunity file in events/opportunity-queue/
        opp_dir = self.test_dir / "events" / "opportunity-queue"
        opp_dir.mkdir(parents=True, exist_ok=True)
        opp_file = opp_dir / "OPP-M213-TEST.json"
        opp_file.write_text(
            json.dumps(
                {
                    "opportunity_id": "OPP-M213-TEST",
                    "source": "TEST_RUNNER",
                    "objective_id": "M213_SAFE_OPS",
                    "project": "Courier",
                    "description": "Safe Opportunity Ingestion Test",
                    "priority": 8,
                    "risk": "LOW",
                    "cost_class": "ZERO_COST_LOCAL",
                    "status": "READY",
                }
            ),
            encoding="utf-8",
        )

        ingested = self.dispatcher.ingest_opportunity_queue()
        self.assertEqual(ingested, 1)
        self.assertIn("OPP-M213-TEST", self.dispatcher.tasks)
        task = self.dispatcher.tasks["OPP-M213-TEST"]
        self.assertEqual(task.safety_class, TaskSafetyClass.SAFE_LOCAL)

        # Dispatch ingested task
        ev = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {"ingest_test": "pass"}))
        self.assertEqual(ev.action, "EXECUTED")
        self.assertEqual(ev.task_id, "OPP-M213-TEST")

    def test_03_event_stream_compaction(self):
        """Verifies event stream compaction rolls older events into archive."""
        registry = self.dispatcher.registry
        worker = registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "GOOGLE_PRO", pid=os.getpid())

        # Generate 15 dummy events
        for i in range(15):
            registry.emit_event(
                event_type=EventType.WORKER_PROGRESS,
                worker=worker,
                evidence={"step_index": i, "unique_token": f"tok-{i}"},
            )

        archived_count = registry.compact_event_stream(max_events=5)
        self.assertGreater(archived_count, 0)
        remaining_events = list(registry.events_dir.glob("evt-*.json"))
        self.assertLessEqual(len(remaining_events), 5)


if __name__ == "__main__":
    unittest.main()
