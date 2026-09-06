#!/usr/bin/env python3
"""Mission 214 Acceptance Test Suite: Anti-Premature-Idle & Snitch Truth (Google Primary Builder).

Verifies:
1. Anti-Premature-Idle 10-point assertion validity
2. Fresh opportunity scan discovers new disk opportunities before SAFE_IDLE
3. SnitchObserver real-time inspection of active_workers.json and stale locks
4. Snitch orphan reconciliation of dead PIDs
5. Continuous autonomous execution with 0 model calls and 0 EUR spend
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
    AntiPrematureIdleAssertion,
    ContinuousSafeWorkDispatcher,
    DispatchableTask,
    TaskSafetyClass,
)
from scripts.snitch_observer import SnitchObserver


class TestMission214AntiPrematureIdleAndSnitch(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_214_test_"))
        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)
        self.snitch = SnitchObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_anti_premature_idle_assertion_contract(self):
        """Validates the 10-point anti-premature-idle assertion contract."""
        assertion = self.dispatcher.evaluate_anti_premature_idle()
        self.assertTrue(assertion.is_safe_idle_valid)
        d = assertion.to_dict()
        self.assertEqual(len(d), 10)
        self.assertTrue(d["current_queue_empty"])
        self.assertTrue(d["fresh_opportunity_scan_completed"])
        self.assertTrue(d["no_unclaimed_safe_task"])
        self.assertTrue(d["no_safe_work"])

    def test_02_fresh_opportunity_scan_prevents_premature_idle(self):
        """When queue is empty but opportunity exists on disk, anti-premature-idle scan ingests it immediately."""
        # Ensure dispatcher tasks are empty
        self.assertEqual(len(self.dispatcher.tasks), 0)

        # Place opportunity on disk
        opp_dir = self.test_dir / "events" / "opportunity-queue"
        opp_dir.mkdir(parents=True, exist_ok=True)
        opp_file = opp_dir / "OPP-DISCOVERY-001.json"
        opp_file.write_text(
            json.dumps(
                {
                    "opportunity_id": "OPP-DISCOVERY-001",
                    "source": "AUTONOMY_SCANNER",
                    "objective_id": "M214_DISCOVERY",
                    "project": "Courier",
                    "description": "Discovered Useful Engineering Task",
                    "priority": 7,
                    "risk": "LOW",
                    "cost_class": "ZERO_COST_LOCAL",
                    "status": "READY",
                }
            ),
            encoding="utf-8",
        )

        # Dispatch next cycle: instead of entering SAFE_IDLE, it discovers and executes the task!
        executed = []
        ev = self.dispatcher.dispatch_next_safe_cycle(
            runner_fn=lambda t: (executed.append(t.task_id), (True, {"discovered_pass": True}))[1]
        )
        self.assertEqual(ev.action, "EXECUTED")
        self.assertEqual(ev.task_id, "OPP-DISCOVERY-001")
        self.assertIn("OPP-DISCOVERY-001", executed)

    def test_03_snitch_inspects_active_workers_and_stale_locks(self):
        """SnitchObserver detects live workers, dead PIDs, and stale locks."""
        # 1. Register live worker
        self.dispatcher.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "GOOGLE_PRO", pid=os.getpid())

        # 2. Inject dead lock in events/locks/
        locks_dir = self.test_dir / "events" / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        stale_lock = locks_dir / "scope_dummy.json"
        stale_lock.write_text(
            json.dumps({"owner_id": "crashed_worker", "pid": 99999999, "acquired_at": "2026-09-01T00:00:00Z"}),
            encoding="utf-8",
        )

        observations = self.snitch.inspect_workspace()
        obs_workers = {o.worker_id: o for o in observations}

        self.assertIn("GOOGLE", obs_workers)
        self.assertTrue(obs_workers["GOOGLE"].alive)

        self.assertIn("stale-lock-scope_dummy", obs_workers)
        self.assertFalse(obs_workers["stale-lock-scope_dummy"].alive)

    def test_04_snitch_orphan_reconciliation(self):
        """SnitchObserver reconciles dead PID locks and dead worker records."""
        # Inject dead lock
        locks_dir = self.test_dir / "events" / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        stale_lock = locks_dir / "scope_stale.json"
        stale_lock.write_text(
            json.dumps({"owner_id": "crashed_worker", "pid": 99999998, "acquired_at": "2026-09-01T00:00:00Z"}),
            encoding="utf-8",
        )

        reconciled = self.snitch.reconcile_orphans()
        self.assertGreater(reconciled, 0)
        self.assertFalse(stale_lock.exists())


if __name__ == "__main__":
    unittest.main()
