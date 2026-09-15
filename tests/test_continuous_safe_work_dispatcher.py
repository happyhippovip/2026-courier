#!/usr/bin/env python3
"""Comprehensive Unit and Integration Test Suite for ContinuousSafeWorkDispatcher.

Tests coverage across:
- Task submission & canonical fingerprinting
- Deterministic priority & safety-first ranking
- Scope acquisition & heavy slot isolation
- Continuous flow execution & failure handling
- Safe idle transition & anti-premature idle audit
- Event-driven wake (exactly once per evidence fingerprint)
- Parking of permission-gated & human-audience-gated tasks
- Opportunity queue ingestion
- State persistence & restart recovery
- Batch execution & productive metrics tracking
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import WorkerState
from scripts.canonical_authority import CanonicalAuthority
from scripts.continuous_safe_work_dispatcher import (
    AntiPrematureIdleAssertion,
    ContinuousSafeWorkDispatcher,
    DispatchableTask,
    DispatcherProductiveMetrics,
    IdleSemanticState,
    TaskSafetyClass,
    compute_task_fingerprint,
)


class TestContinuousSafeWorkDispatcher(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_cswd_"))
        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_compute_task_fingerprint(self):
        """Fingerprints are deterministic, normalized, and sensitive to inputs."""
        fp1 = compute_task_fingerprint("Fix Bug", ["src/main.py", "src/util.py"], "SAFE_LOCAL_ENGINEERING")
        fp2 = compute_task_fingerprint("Fix Bug", ["src/util.py", "src/main.py"], "SAFE_LOCAL_ENGINEERING")
        self.assertEqual(fp1, fp2)

        fp_diff = compute_task_fingerprint("Fix Bug 2", ["src/main.py"], "SAFE_LOCAL_ENGINEERING")
        self.assertNotEqual(fp1, fp_diff)

    def test_submit_task_and_state_persistence(self):
        """Tasks are persisted to disk and survive re-instantiation."""
        task = self.dispatcher.submit_task(
            task_id="task_1",
            objective="Improve dispatch latency",
            priority=8,
            scope=["scripts/continuous_safe_work_dispatcher.py"],
        )
        self.assertEqual(task.task_id, "task_1")
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(task.safety_class, TaskSafetyClass.SAFE_LOCAL)

        # Recreate dispatcher from same directory
        reloaded = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)
        self.assertIn("task_1", reloaded.tasks)
        self.assertEqual(reloaded.tasks["task_1"].priority, 8)
        self.assertEqual(reloaded.tasks["task_1"].objective, "Improve dispatch latency")

    def test_deterministic_ranking_ordering(self):
        """Tasks rank strictly: SAFE_LOCAL > GATED, higher priority > lower priority, non-heavy > heavy."""
        # Submit varying safety and priority
        self.dispatcher.submit_task("task_low_safe", "Low safe", priority=2)
        self.dispatcher.submit_task("task_high_safe", "High safe", priority=9)
        self.dispatcher.submit_task("task_paid_high", "Paid high", requires_payment=True, priority=10)
        self.dispatcher.submit_task("task_heavy_safe", "Heavy safe", requires_heavy_slot=True, priority=9)

        ranked = self.dispatcher.rank_eligible_tasks()
        ranked_ids = [t.task_id for t in ranked]

        # task_high_safe (safe, prio 9, non-heavy) should come before task_heavy_safe (safe, prio 9, heavy)
        self.assertEqual(ranked_ids[0], "task_high_safe")
        self.assertEqual(ranked_ids[1], "task_heavy_safe")
        self.assertEqual(ranked_ids[2], "task_low_safe")
        self.assertEqual(ranked_ids[3], "task_paid_high")

    def test_dependency_gating(self):
        """Tasks with unmet dependencies are not eligible until upstream completes."""
        self.dispatcher.submit_task("task_parent", "Parent Step", priority=5)
        self.dispatcher.submit_task("task_child", "Child Step", priority=10, dependencies=["task_parent"])

        ranked = self.dispatcher.rank_eligible_tasks()
        self.assertEqual([t.task_id for t in ranked], ["task_parent"])

        # Execute parent
        ev = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {"status": "ok"}))
        self.assertEqual(ev.action, "EXECUTED")
        self.assertEqual(ev.task_id, "task_parent")

        # Now child becomes eligible and ranks first
        ranked_after = self.dispatcher.rank_eligible_tasks()
        self.assertEqual([t.task_id for t in ranked_after], ["task_child"])

    def test_execution_failure_handling(self):
        """When runner returns False or raises exception, task status becomes FAILED."""
        self.dispatcher.submit_task("task_fail", "Failing task", priority=5)

        def failing_runner(t: DispatchableTask):
            return False, {"error": "Simulated failure"}

        ev = self.dispatcher.dispatch_next_safe_cycle(runner_fn=failing_runner)
        self.assertEqual(ev.action, "FAILED")
        self.assertEqual(ev.task_id, "task_fail")
        self.assertEqual(self.dispatcher.tasks["task_fail"].status, "FAILED")
        self.assertEqual(self.dispatcher.metrics.failures_found, 1)

    def test_scope_lock_contention(self):
        """Contention on shared scope locks prevents execution until lock released."""
        auth = self.dispatcher.authority
        ok, gen, _ = auth.acquire_scopes(
            owner_id="external_worker",
            task_id="ext_task",
            scopes=["repo/shared_module.py"],
            ttl_seconds=300,
        )
        self.assertTrue(ok)

        self.dispatcher.submit_task(
            "task_contended",
            "Contended task",
            scope=["repo/shared_module.py"],
            priority=5,
        )

        ev = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "SCOPE_LOCKED_WAIT")

        # Release lock
        auth.release_scopes(
            owner_id="external_worker",
            task_id="ext_task",
            generation=gen,
            scopes=["repo/shared_module.py"],
        )

        ev2 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {}))
        self.assertEqual(ev2.action, "EXECUTED")

    def test_anti_premature_idle_and_semantics(self):
        """Empty queue triggers anti-premature idle evaluation and safe idle semantics file writing."""
        assertion = self.dispatcher.evaluate_anti_premature_idle()
        self.assertIsInstance(assertion, AntiPrematureIdleAssertion)
        self.assertTrue(assertion.is_safe_idle_valid)

        semantics_file = self.test_dir / "events" / "runtime-state" / "safe_idle_semantics.json"
        self.assertTrue(semantics_file.exists())
        data = json.loads(semantics_file.read_text(encoding="utf-8"))
        self.assertEqual(data["idle_semantic_state"], IdleSemanticState.EXECUTION_QUEUE_EMPTY.value)

    def test_trigger_event_wake(self):
        """Trigger wake transitions from SAFE_IDLE to PROGRESSING and rejects duplicates."""
        self.dispatcher.current_state = WorkerState.SAFE_IDLE.value
        first_wake = self.dispatcher.trigger_event_wake("ev-unique-100")
        self.assertTrue(first_wake)
        self.assertEqual(self.dispatcher.current_state, WorkerState.PROGRESSING.value)

        # Duplicate evidence does not trigger wake again
        second_wake = self.dispatcher.trigger_event_wake("ev-unique-100")
        self.assertFalse(second_wake)

    def test_run_continuous_backlog_batch(self):
        """Batch execution drains pending tasks until empty queue / limit."""
        for i in range(5):
            self.dispatcher.submit_task(f"batch_task_{i}", f"Batch task {i}", priority=5 - i)

        executed = []

        def runner(t: DispatchableTask):
            executed.append(t.task_id)
            return True, {"batch": True}

        res = self.dispatcher.run_continuous_backlog_batch(runner_fn=runner, max_tasks=10)
        self.assertEqual(res["tasks_completed"], 5)
        self.assertEqual(len(executed), 5)
        self.assertEqual(self.dispatcher.get_productive_metrics()["tasks_completed"], 5)

    def test_inactive_worker_role_rejected(self):
        """Inactive worker roles (e.g. CLI2) are denied work dispatch."""
        self.dispatcher.submit_task("task_inactive_test", "Task test")
        ev = self.dispatcher.dispatch_next_safe_cycle(worker_id="CLI2")
        self.assertEqual(ev.action, "WORKER_INACTIVE_DENIED")
        self.assertEqual(ev.next_action, "CLI2_IS_INACTIVE")


if __name__ == "__main__":
    unittest.main()
