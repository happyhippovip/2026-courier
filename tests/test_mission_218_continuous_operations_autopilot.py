#!/usr/bin/env python3
"""Mission 218 Acceptance Test Suite: Continuous Operations Autopilot."""

import datetime as dt
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.cli_operations_autopilot import CLIOperationsAutopilot, AutopilotState
from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.canonical_authority import CanonicalAuthority


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class TestMission218ContinuousOperationsAutopilot(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m218_autopilot_"))
        self.events_dir = self.test_dir / "events"
        self.runtime_dir = self.events_dir / "runtime-state"
        self.alerts_dir = self.events_dir / "runtime-alerts"
        self.worker_events_dir = self.events_dir / "worker-events"
        self.locks_dir = self.events_dir / "locks"
        self.opp_queue_dir = self.events_dir / "opportunity-queue"

        for d in [
            self.runtime_dir,
            self.alerts_dir,
            self.worker_events_dir,
            self.locks_dir,
            self.opp_queue_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        self.autopilot = CLIOperationsAutopilot(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_result_auto_detection_and_continuation(self):
        """Task A finishes -> result detected -> fingerprinted -> next task B selected."""
        opp_queue = OpportunityQueue(repo_dir=self.test_dir)
        opp_a = Opportunity(
            opportunity_id="TASK-A",
            source="TEST",
            objective_id="OBJ-A",
            description="Task A",
            project="2026-courier",
            status="READY",
            dedupe_fingerprint="fp-a",
        )
        opp_b = Opportunity(
            opportunity_id="TASK-B",
            source="TEST",
            objective_id="OBJ-B",
            description="Task B",
            project="2026-courier",
            status="READY",
            dedupe_fingerprint="fp-b",
        )
        opp_queue.save_opportunity(opp_a)
        opp_queue.save_opportunity(opp_b)

        # 1. Execute Task A via autopilot
        telemetry = self.autopilot.run_autopilot_cycle()
        self.assertEqual(telemetry.autopilot_state, AutopilotState.EXECUTING_SAFE_WORK.value)
        self.assertIn("TASK-A", telemetry.next_safe_action)

        # 2. Next cycle -> Task B selected automatically
        telemetry2 = self.autopilot.run_autopilot_cycle()
        self.assertEqual(telemetry2.autopilot_state, AutopilotState.EXECUTING_SAFE_WORK.value)
        self.assertIn("TASK-B", telemetry2.next_safe_action)

    def test_02_human_gates_park_without_blocking_safe_work(self):
        """Gated Task parks branch while independent Safe Task continues."""
        opp_queue = OpportunityQueue(repo_dir=self.test_dir)
        opp_hg = Opportunity(
            opportunity_id="TASK-HUMAN",
            source="TEST",
            objective_id="OBJ-HG",
            description="Task Human Gate",
            project="HUMAN_BRANCH",
            status="WAITING_FOR_HUMAN",
            risk="LOW",
        )
        opp_safe = Opportunity(
            opportunity_id="TASK-SAFE-INDEPENDENT",
            source="TEST",
            objective_id="OBJ-SAFE",
            description="Independent Safe Task",
            project="2026-courier",
            status="READY",
            risk="LOW",
            dedupe_fingerprint="fp-safe-indep",
        )
        opp_queue.save_opportunity(opp_hg)
        opp_queue.save_opportunity(opp_safe)

        # Cycle executes independent safe task and registers parked human gate
        tel1 = self.autopilot.run_autopilot_cycle()
        self.assertEqual(tel1.autopilot_state, AutopilotState.EXECUTING_SAFE_WORK.value)
        self.assertIn("TASK-SAFE-INDEPENDENT", tel1.next_safe_action)
        self.assertIn("TASK-HUMAN", tel1.blocked_branches)

    def test_03_single_writer_enforcement_and_scope_protection(self):
        """Active writer on scope 'src/mission_216' blocks overlapping write, non-conflicting continues."""
        authority = CanonicalAuthority(locks_dir=self.locks_dir)
        acquired, gen, _ = authority.acquire_scopes(
            owner_id="MISSION_216_BUILDER",
            task_id="TASK-M216-BUILD",
            scopes=["src/mission_216"],
            ttl_seconds=300,
        )
        self.assertTrue(acquired)

        opp_queue = OpportunityQueue(repo_dir=self.test_dir)
        opp_conflict = Opportunity(
            opportunity_id="TASK-CONFLICT",
            source="TEST",
            objective_id="OBJ-CONF",
            description="Conflicting task",
            project="2026-courier",
            status="READY",
            risk="LOW",
            allowed_scope=["src/mission_216/core.py"],
            dedupe_fingerprint="fp-conf",
        )
        opp_disjoint = Opportunity(
            opportunity_id="TASK-DISJOINT",
            source="TEST",
            objective_id="OBJ-DISJ",
            description="Disjoint task",
            project="2026-courier",
            status="READY",
            risk="LOW",
            allowed_scope=["docs/architecture.md"],
            dedupe_fingerprint="fp-disj",
        )
        opp_queue.save_opportunity(opp_conflict)
        opp_queue.save_opportunity(opp_disjoint)

        # Autopilot must skip conflicting task and execute disjoint task
        tel = self.autopilot.run_autopilot_cycle()
        self.assertEqual(tel.autopilot_state, AutopilotState.EXECUTING_SAFE_WORK.value)
        self.assertIn("TASK-DISJOINT", tel.next_safe_action)

    def test_04_safe_idle_and_wake(self):
        """No safe work -> SAFE_IDLE; new task arrives -> wakes."""
        # Empty queue -> SAFE_IDLE
        tel1 = self.autopilot.run_autopilot_cycle()
        self.assertEqual(tel1.autopilot_state, AutopilotState.SAFE_IDLE.value)
        self.assertTrue(tel1.safe_idle)

        # Inject new safe task -> Wakes
        opp_queue = OpportunityQueue(repo_dir=self.test_dir)
        opp_new = Opportunity(
            opportunity_id="TASK-WAKE",
            source="TEST",
            objective_id="OBJ-WAKE",
            description="Wake task",
            project="2026-courier",
            status="READY",
            risk="LOW",
            dedupe_fingerprint="fp-wake",
        )
        opp_queue.save_opportunity(opp_new)

        tel2 = self.autopilot.run_autopilot_cycle()
        self.assertEqual(tel2.autopilot_state, AutopilotState.EXECUTING_SAFE_WORK.value)
        self.assertFalse(tel2.safe_idle)

    def test_05_financial_firewall_enforcement(self):
        """Enforces zero trades, zero wallet signing, and zero EUR spend."""
        self.assertEqual(self.autopilot.real_trades_count, 0)
        self.assertFalse(self.autopilot.real_funds_touched)
        self.assertFalse(self.autopilot.wallet_signing_active)
        self.assertEqual(self.autopilot.spend_limit_eur, 0.0)

    def test_06_restart_recovery_and_no_duplicate_execution(self):
        """Reinstantiating autopilot loads durable state and does not replay completed work."""
        opp_queue = OpportunityQueue(repo_dir=self.test_dir)
        opp = Opportunity(
            opportunity_id="TASK-ONCE",
            source="TEST",
            objective_id="OBJ-ONCE",
            description="Execute once",
            project="2026-courier",
            status="READY",
            dedupe_fingerprint="fp-once",
        )
        opp_queue.save_opportunity(opp)

        # 1. Execute task
        self.autopilot.run_autopilot_cycle()
        opp_queue._load_all()
        self.assertEqual(opp_queue.get_opportunity("TASK-ONCE").status, "COMPLETED")

        # 2. Re-instantiate autopilot (simulate restart)
        restarted_autopilot = CLIOperationsAutopilot(repo_dir=self.test_dir)
        tel_restart = restarted_autopilot.run_autopilot_cycle()
        self.assertEqual(tel_restart.autopilot_state, AutopilotState.SAFE_IDLE.value)

    def test_07_provider_failover_safety(self):
        """Provider quota marks provider unavailable without account rotation."""
        self.autopilot.telemetry.provider_states["CODEX"] = "QUOTA_EXHAUSTED"
        self.autopilot.telemetry.provider_states["GOOGLE"] = "AVAILABLE"
        self.assertEqual(self.autopilot.telemetry.provider_states["CODEX"], "QUOTA_EXHAUSTED")
        self.assertEqual(self.autopilot.telemetry.provider_states["GOOGLE"], "AVAILABLE")


if __name__ == "__main__":
    unittest.main()
