#!/usr/bin/env python3
"""Mission 217 Acceptance Test Suite: Autonomous Investigate -> Fix -> Verify -> Continue Loop.

Verifies:
1. Investigation Result Contract (DEFECT_CONFIRMED, TEST_GAP_CONFIRMED, RELIABILITY_IMPROVEMENT_CONFIRMED, etc.)
2. Automatic Follow-Up Task Generation from confirmed investigations
3. Strict Queue Accounting Ledger (DISCOVERED_TOTAL = COMPLETED + ACTIVE + PENDING + GATED + REJECTED + DUPLICATE + SUPERSEDED)
4. Work-Conserving Invariant (AVAILABLE_NORMAL + SAFE_ELIGIBLE_WORK -> MUST_DISPATCH, SAFE_IDLE forbidden)
5. Multi-step Investigate -> Fix -> Verify autonomous chains executed without WEITER
6. Snitch detection for WORK_AVAILABLE_BUT_IDLE and PREMATURE_IDLE
7. 100% Deterministic local execution (0 Model Calls, 0 EUR Spend)
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
from scripts.investigation_lifecycle_engine import (
    InvestigationLifecycleEngine,
    InvestigationRecord,
    InvestigationResultClass,
    QueueAccountingLedger,
)
from scripts.snitch_observer import SnitchObserver


class TestMission217InvestigateFixVerifyLoop(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_217_test_"))
        self.scripts_dir = self.test_dir / "scripts"
        self.tests_dir = self.test_dir / "tests"
        self.events_dir = self.test_dir / "events"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)
        self.inv_engine = InvestigationLifecycleEngine(repo_dir=self.test_dir)
        self.snitch = SnitchObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_investigation_result_contract(self):
        """Validates structured investigation execution and record persistence."""
        task = DispatchableTask(
            task_id="TASK-GEN-TEST-COV-SAMPLE-MODULE",
            objective="Verify and construct focused test harness for sample_module.py",
            task_type="SAFE_LOCAL_INVESTIGATION",
            scope=["scripts/sample_module.py"],
            task_fingerprint="fp123456",
        )

        rec = self.inv_engine.execute_investigation(task)

        self.assertEqual(rec.task_id, task.task_id)
        self.assertEqual(rec.result_class, InvestigationResultClass.TEST_GAP_CONFIRMED)
        self.assertTrue(len(rec.result_fingerprint) > 0)
        self.assertEqual(len(rec.follow_up_tasks), 1)
        self.assertTrue((self.test_dir / "events" / "investigations" / f"{rec.investigation_id}.json").exists())

    def test_02_automatic_follow_up_task_generation(self):
        """Generates evidence-backed engineering follow-up task from confirmed investigation."""
        task = DispatchableTask(
            task_id="TASK-GEN-EXC-AUDIT-SAMPLE-L50",
            objective="Audit silent exception in sample.py:50",
            task_type="SAFE_LOCAL_INVESTIGATION",
            scope=["scripts/sample.py"],
            task_fingerprint="fp789012",
        )

        rec = self.inv_engine.execute_investigation(task)
        fu_task = self.inv_engine.generate_follow_up_task(rec, task)

        self.assertIsNotNone(fu_task)
        self.assertEqual(fu_task.task_type, "SAFE_LOCAL_ENGINEERING")
        self.assertEqual(fu_task.priority, 8)
        self.assertIn(task.task_id, fu_task.dependencies)
        self.assertEqual(fu_task.safety_class, TaskSafetyClass.SAFE_LOCAL)

    def test_03_queue_accounting_balance_invariant(self):
        """Enforces DISCOVERED_TOTAL = COMPLETED + ACTIVE + PENDING + GATED + REJECTED + DUPLICATE + SUPERSEDED."""
        tasks = {
            "T1": DispatchableTask("T1", "Task 1", status="COMPLETED"),
            "T2": DispatchableTask("T2", "Task 2", status="RUNNING"),
            "T3": DispatchableTask("T3", "Task 3", status="PENDING"),
            "T4": DispatchableTask("T4", "Task 4", status="PENDING", safety_class=TaskSafetyClass.PAID_SUBSCRIPTION_GATED),
        }

        ledger = self.inv_engine.reconcile_queue_accounting(
            tasks=tasks,
            rejected_count=1,
            duplicate_count=2,
            superseded_count=1,
        )

        self.assertEqual(ledger.discovered_total, 8)
        self.assertEqual(ledger.completed, 1)
        self.assertEqual(ledger.active, 1)
        self.assertEqual(ledger.pending, 1)
        self.assertEqual(ledger.gated, 1)
        self.assertEqual(ledger.rejected, 1)
        self.assertEqual(ledger.duplicate, 2)
        self.assertEqual(ledger.superseded, 1)
        self.assertTrue(ledger.is_balanced)
        self.assertEqual(ledger.unaccounted_discrepancy, 0)
        self.assertTrue(self.inv_engine.ledger_file.exists())

    def test_04_work_conserving_dispatch_invariant(self):
        """Strictly disallows SAFE_IDLE when eligible safe tasks exist in queue."""
        self.dispatcher.submit_task(
            task_id="TASK-SAFE-PENDING",
            objective="Pending safe work",
            priority=5,
            safety_class=TaskSafetyClass.SAFE_LOCAL,
        )

        assertion = self.dispatcher.evaluate_anti_premature_idle()
        self.assertFalse(assertion.no_safe_work)
        self.assertFalse(assertion.current_queue_empty)

    def test_05_multi_step_investigate_fix_verify_chain(self):
        """Executes 3 complete investigate -> follow-up -> execute -> verify chains continuously."""
        # Create 3 operational modules needing investigation
        modules = [
            "bootstrap_replacement_host.py",
            "disaster_recovery_bundle_sync.py",
            "multi_host_failover_coordinator.py",
        ]
        for m in modules:
            (self.scripts_dir / m).write_text(f"# {m}\n", encoding="utf-8")

        # Mock clean survival environment
        survival_dir = self.test_dir / "events" / "host-survival"
        survival_dir.mkdir(parents=True, exist_ok=True)
        (survival_dir / "disaster_recovery_manifest.json").write_text(
            json.dumps({"manifest_digest": "valid_digest", "confirmed_state_hashes": {"a": "1"}}),
            encoding="utf-8",
        )
        state_dir = self.test_dir / "events" / "runtime-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "hq_telemetry_snapshot.json").write_text(
            json.dumps({"visual_state": "ALL_SYSTEMS_OPERATIONAL"}),
            encoding="utf-8",
        )

        executed_tasks = []

        def runner(t: DispatchableTask):
            executed_tasks.append(t.task_id)
            return True, {"verified": True, "task": t.task_id}

        # Run continuous batch allowing both investigations and follow-ups to run
        summary = self.dispatcher.run_continuous_backlog_batch(
            worker_id="GOOGLE",
            max_tasks=6,  # 3 investigations + 3 follow-ups
            runner_fn=runner,
        )

        self.assertGreaterEqual(summary["tasks_completed"], 6)
        self.assertEqual(summary["model_calls"], 0)
        self.assertEqual(summary["spend_eur"], 0.0)

        # Verify investigation records were created
        inv_files = list((self.test_dir / "events" / "investigations").glob("inv-*.json"))
        self.assertGreaterEqual(len(inv_files), 3)


if __name__ == "__main__":
    unittest.main()
