#!/usr/bin/env python3
"""Targeted Test Suite for Deterministic Next-Safe-Work Router."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.live_worker_registry import (
    AvailabilityClass,
    LiveWorkerRegistry,
    WorkerState,
)
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.queue_hygiene_manager import QueueHygieneManager


class TestNextSafeWorkRouter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="next_safe_router_test_"))
        self.router = NextSafeWorkRouter(repo_dir=self.test_dir)
        self.registry = self.router.registry
        self.queue_dir = self.test_dir / "events" / "opportunity-queue"
        self.state_dir = self.test_dir / "events" / "runtime-state"
        self.events_dir = self.test_dir / "events" / "worker-events"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_available_worker_and_safe_task(self):
        # Register available worker
        w = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w.state = WorkerState.SAFE_IDLE.value
        self.registry._save_worker_record(w)

        # Add safe ready task
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-SAFE-01",
            source="TEST",
            objective_id="OBJ1",
            project="TEST_PROJ",
            description="Run unit test suite",
            priority=9,
            status="READY",
        ))

        res = self.router.evaluate_next_safe_work()
        recs = res["recommendations"]
        self.assertTrue(recs["CLI1"]["available"])
        self.assertTrue(recs["CLI1"]["safe_task_available"])
        self.assertEqual(recs["CLI1"]["task_id"], "OPP-SAFE-01")
        self.assertEqual(recs["CLI1"]["recommended_action"], "DISPATCH_TASK_OPP-SAFE-01")

    def test_02_completed_fingerprint_suppression(self):
        w = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w)

        # Add task and archive it to historical ledger
        opp = Opportunity(
            opportunity_id="OPP-COMPLETED-HISTORICAL",
            source="TEST",
            objective_id="OBJ1",
            project="HIST_PROJ",
            description="Already done task",
            status="COMPLETED",
        )
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(opp)
        self.router.queue_manager.prune_and_archive_completed()

        # Re-add opportunity with status READY
        opp_readded = Opportunity(
            opportunity_id="OPP-COMPLETED-HISTORICAL",
            source="TEST",
            objective_id="OBJ1",
            project="HIST_PROJ",
            description="Already done task",
            status="READY",
        )
        q.add_opportunity(opp_readded)

        res = self.router.evaluate_next_safe_work()
        recs = res["recommendations"]
        # Completed historical task must NOT be dispatched again!
        self.assertFalse(recs["CLI1"]["safe_task_available"])
        self.assertEqual(recs["CLI1"]["recommended_action"], "STANDBY_SAFE_IDLE")

    def test_03_scope_conflict_suppression(self):
        # Worker 1 is PROGRESSING on scope 'AUTH_MODULE'
        w1 = self.registry.register_worker("GOOGLE", "BUILDER", "ANTIGRAVITY", mutable_scope=["AUTH_MODULE"])
        w1.state = WorkerState.PROGRESSING.value
        self.registry._save_worker_record(w1)

        # Worker 2 is AVAILABLE
        w2 = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w2.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w2)

        # Task targets conflicting scope 'AUTH_MODULE'
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-AUTH-TASK",
            source="TEST",
            objective_id="OBJ1",
            project="AUTH_MODULE",
            description="Modify auth files",
            allowed_scope=["AUTH_MODULE"],
            status="READY",
        ))

        res = self.router.evaluate_next_safe_work()
        # CLI1 must be suppressed due to scope conflict with GOOGLE
        self.assertFalse(res["recommendations"]["CLI1"]["safe_task_available"])

    def test_04_heavy_job_limit_respect(self):
        # Worker 1 is running a heavy job
        w1 = self.registry.register_worker("GOOGLE", "BUILDER", "ANTIGRAVITY", heavy_job=True)
        w1.state = WorkerState.PROGRESSING.value
        self.registry._save_worker_record(w1)

        # Worker 2 is AVAILABLE
        w2 = self.registry.register_worker("CLI2", "WORKER", "ANTIGRAVITY_BEATA")
        w2.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w2)

        # Task is also heavy
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-HEAVY-RENDER",
            source="TEST",
            objective_id="OBJ1",
            project="RENDER",
            description="Heavy video rendering",
            heavy_job=True,
            status="READY",
        ))

        res = self.router.evaluate_next_safe_work()
        # Cannot assign heavy job while limit (1) is reached
        self.assertFalse(res["recommendations"]["CLI2"]["safe_task_available"])

    def test_05_high_risk_and_spend_firewalls(self):
        w = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w)

        q = OpportunityQueue(repo_dir=self.test_dir)
        # High risk task
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-HIGH-RISK", source="TEST", objective_id="OBJ1",
            project="SECURITY", description="Dangerous root operation", risk="HIGH", status="READY"
        ))
        # Paid task
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-PAID-API", source="TEST", objective_id="OBJ1",
            project="API", description="Paid cloud query", estimated_cost=5.0, status="READY"
        ))

        res = self.router.evaluate_next_safe_work()
        self.assertFalse(res["recommendations"]["CLI1"]["safe_task_available"])

    def test_06_expired_cli_worker_not_dispatched(self):
        w_exp = self.registry.register_worker(
            "CLI2", "WORKER", "ANTIGRAVITY_BEATA",
            availability_class=AvailabilityClass.TEMPORARY_30_DAY,
            available_duration_seconds=-10.0,  # Expired
        )
        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-SAFE-TASK", source="TEST", objective_id="OBJ1",
            project="P1", description="Safe task", status="READY"
        ))

        res = self.router.evaluate_next_safe_work()
        self.assertFalse(res["recommendations"]["CLI2"]["available"])
        self.assertEqual(res["recommendations"]["CLI2"]["block_reason"], "30_DAY_RESOURCE_WINDOW_EXPIRED")

    def test_07_two_available_workers_disjoint_dispatch(self):
        w1 = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w1.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w1)

        w2 = self.registry.register_worker("CLI2", "WORKER", "ANTIGRAVITY_BEATA")
        w2.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w2)

        q = OpportunityQueue(repo_dir=self.test_dir)
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-DISJOINT-1", source="TEST", objective_id="OBJ1",
            project="MODULE_A", description="Task A", priority=10, status="READY"
        ))
        q.add_opportunity(Opportunity(
            opportunity_id="OPP-DISJOINT-2", source="TEST", objective_id="OBJ1",
            project="MODULE_B", description="Task B", priority=8, status="READY"
        ))

        res = self.router.evaluate_next_safe_work()
        recs = res["recommendations"]
        self.assertTrue(recs["CLI1"]["safe_task_available"])
        self.assertTrue(recs["CLI2"]["safe_task_available"])
        self.assertEqual(recs["CLI1"]["task_id"], "OPP-DISJOINT-1")
        self.assertEqual(recs["CLI2"]["task_id"], "OPP-DISJOINT-2")

    def test_08_deduplication_unchanged_state(self):
        w = self.registry.register_worker("CLI1", "OPS", "ANTIGRAVITY")
        w.state = WorkerState.AVAILABLE.value
        self.registry._save_worker_record(w)

        # First evaluation
        self.router.evaluate_next_safe_work()
        self.assertEqual(self.router.telemetry["duplicates_suppressed"], 0)

        # Second evaluation with unchanged state -> Suppressed write!
        self.router.evaluate_next_safe_work()
        self.assertEqual(self.router.telemetry["duplicates_suppressed"], 1)
        self.assertEqual(self.router.telemetry["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
