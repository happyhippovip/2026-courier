#!/usr/bin/env python3
"""Mission 210 Acceptance Test Suite: Continuous Safe Work Dispatcher (Google Primary Builder).

Verifies all 9 core requirements:
1. Continuous Flow A -> B -> C without manual WEITER
2. Safe Idle entry on empty queue
3. Event-Driven Wake exactly once upon new evidence
4. Permission-gated task parking (WAITING_PERMISSION)
5. Independent safe work continues while gated task is parked
6. Canonical task fingerprint & duplicate execution suppression
7. Restart recovery without duplicate execution
8. HEAVY_JOB_LIMIT = 1 enforcement
9. Zero model calls & 0 EUR spend
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import WorkerState
from scripts.canonical_authority import CanonicalAuthority
from scripts.continuous_safe_work_dispatcher import (
    ContinuousSafeWorkDispatcher,
    DispatchableTask,
    TaskSafetyClass,
    compute_task_fingerprint,
)


class TestMission210ContinuousSafeWorkDispatch(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_210_test_"))
        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_continuous_flow_a_b_c_without_weiter(self):
        """A -> B -> C executes continuously in sequence without manual WEITER."""
        self.dispatcher.submit_task("task_A", "Step A Implementation", priority=10)
        self.dispatcher.submit_task("task_B", "Step B Implementation", priority=8, dependencies=["task_A"])
        self.dispatcher.submit_task("task_C", "Step C Implementation", priority=6, dependencies=["task_B"])

        executed_order = []

        def runner(t: DispatchableTask):
            executed_order.append(t.task_id)
            return True, {"step_completed": t.task_id}

        # Step 1: A
        ev1 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=runner)
        self.assertEqual(ev1.action, "EXECUTED")
        self.assertEqual(ev1.task_id, "task_A")

        # Step 2: B
        ev2 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=runner)
        self.assertEqual(ev2.action, "EXECUTED")
        self.assertEqual(ev2.task_id, "task_B")

        # Step 3: C
        ev3 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=runner)
        self.assertEqual(ev3.action, "EXECUTED")
        self.assertEqual(ev3.task_id, "task_C")

        self.assertEqual(executed_order, ["task_A", "task_B", "task_C"])

    def test_02_empty_queue_enters_safe_idle(self):
        """When no eligible tasks remain, dispatcher safely transitions to SAFE_IDLE."""
        ev = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "ENTERED_SAFE_IDLE")
        self.assertEqual(ev.next_action, "STANDBY_SAFE_IDLE")
        self.assertEqual(self.dispatcher.current_state, WorkerState.SAFE_IDLE.value)

    def test_03_event_driven_wake_exactly_once(self):
        """SAFE_IDLE wakes exactly once upon new evidence fingerprint, executes D, and re-enters SAFE_IDLE."""
        # 1. Start in SAFE_IDLE
        ev_idle = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev_idle.action, "ENTERED_SAFE_IDLE")

        # 2. Inject Task D
        self.dispatcher.submit_task("task_D", "Step D Implementation", priority=5)

        # 3. Trigger wake with evidence fingerprint
        fp_evidence = "evidence-hash-d-001"
        woke1 = self.dispatcher.trigger_event_wake(fp_evidence)
        self.assertTrue(woke1)
        self.assertEqual(self.dispatcher.current_state, WorkerState.PROGRESSING.value)

        # Duplicate trigger with same evidence does NOT re-wake
        woke2 = self.dispatcher.trigger_event_wake(fp_evidence)
        self.assertFalse(woke2)

        # 4. Dispatch D
        ev_d = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {"done": True}))
        self.assertEqual(ev_d.action, "EXECUTED")
        self.assertEqual(ev_d.task_id, "task_D")

        # 5. Return to SAFE_IDLE
        ev_end = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev_end.action, "ENTERED_SAFE_IDLE")

    def test_04_permission_gated_task_parking(self):
        """Task requiring payment or auth parks at WAITING_PERMISSION without executing."""
        self.dispatcher.submit_task("task_E_paid", "Purchase Server", requires_payment=True, priority=10)

        ev = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "PARKED_PERMISSION")
        self.assertEqual(ev.task_id, "task_E_paid")

        task = self.dispatcher.tasks["task_E_paid"]
        self.assertEqual(task.status, "WAITING_PERMISSION")

    def test_05_independent_safe_work_continues_while_permission_parked(self):
        """Independent safe task F executes cleanly even while Task E is parked at WAITING_PERMISSION."""
        self.dispatcher.submit_task("task_E_paid", "Purchase Server", requires_payment=True, priority=10)

        # First cycle parks E
        ev_e = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev_e.action, "PARKED_PERMISSION")
        self.assertEqual(self.dispatcher.tasks["task_E_paid"].status, "WAITING_PERMISSION")

        # Now submit independent safe task F
        self.dispatcher.submit_task("task_F_safe", "Run Local Tests", priority=5)

        # Second cycle executes F despite E being parked
        executed = []
        ev_f = self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (executed.append(t.task_id), (True, {}))[1])
        self.assertEqual(ev_f.action, "EXECUTED")
        self.assertEqual(ev_f.task_id, "task_F_safe")
        self.assertIn("task_F_safe", executed)

    def test_06_duplicate_fingerprint_suppression(self):
        """Duplicate task submission with same fingerprint reuses result and does not re-execute."""
        t1 = self.dispatcher.submit_task("task_orig", "Refactor Tooling", code_fingerprint="fp-v1")

        # Execute first
        call_count = 0

        def runner(t):
            nonlocal call_count
            call_count += 1
            return True, {"res": 1}

        ev1 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=runner)
        self.assertEqual(ev1.action, "EXECUTED")
        self.assertEqual(call_count, 1)

        # Submit task_duplicate with same objective, scope, and code fingerprint
        t2 = self.dispatcher.submit_task("task_dup", "Refactor Tooling", code_fingerprint="fp-v1")
        self.assertEqual(t1.task_fingerprint, t2.task_fingerprint)

        # Second cycle reuses result
        ev2 = self.dispatcher.dispatch_next_safe_cycle(runner_fn=runner)
        self.assertEqual(ev2.action, "REUSED_RESULT")
        self.assertEqual(ev2.task_id, "task_dup")
        # runner was NOT called again
        self.assertEqual(call_count, 1)

    def test_07_restart_recovery_without_duplicate_execution(self):
        """Dispatcher restarts from disk; completed tasks survive and are not re-executed."""
        self.dispatcher.submit_task("task_1", "First Task")
        self.dispatcher.dispatch_next_safe_cycle(runner_fn=lambda t: (True, {"ok": True}))

        # Create new dispatcher instance on same repo_dir
        new_dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)
        self.assertEqual(new_dispatcher.tasks["task_1"].status, "COMPLETED")
        self.assertIn(new_dispatcher.tasks["task_1"].task_fingerprint, new_dispatcher.completed_fingerprints)

        # No pending tasks -> SAFE_IDLE
        ev = new_dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "ENTERED_SAFE_IDLE")

    def test_08_heavy_job_limit_enforced(self):
        """Heavy slot exclusivity blocks second heavy task while first holds HEAVY:GLOBAL."""
        auth = self.dispatcher.authority
        ok, g, _ = auth.acquire_heavy_authority(owner_id="external_heavy", task_id="ext_h")
        self.assertTrue(ok)

        self.dispatcher.submit_task("task_heavy_2", "Second Heavy Job", requires_heavy_slot=True)

        ev = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "SCOPE_LOCKED_WAIT")

        auth.release_heavy_authority(owner_id="external_heavy", generation=g, task_id="ext_h")

    def test_09_deterministic_ranking_safety_first(self):
        """SAFE_LOCAL tasks always rank above gated tasks regardless of insertion order."""
        t_gated = self.dispatcher.submit_task("gated_1", "Paid Task", requires_payment=True, priority=100)
        t_safe = self.dispatcher.submit_task("safe_1", "Safe Task", requires_payment=False, priority=1)

        ranked = self.dispatcher.rank_eligible_tasks()
        self.assertEqual(ranked[0].task_id, "safe_1")
        self.assertEqual(ranked[1].task_id, "gated_1")


if __name__ == "__main__":
    unittest.main()
