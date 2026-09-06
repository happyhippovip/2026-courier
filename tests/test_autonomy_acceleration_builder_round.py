#!/usr/bin/env python3
"""Acceptance Tests for Computer-A Autonomy Acceleration (Builder Round).

Verifies:
1. Automatic opportunity discovery when queue is empty.
2. Multi-task automatic continuation without manual WEITER prompts.
3. Opportunity value ranking (HIGH_VALUE > USEFUL > NEUTRAL > SUPPRESSED).
4. Cryptographic duplicate suppression and closed-strand protection.
5. Durable restart recovery from persistent state.
6. Clean STOP / RESUME semantics.
7. Human/Money gate isolation and 0 EUR spend invariance.
8. Max iteration bounded protection.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_opportunity_discovery import (
    AutonomousOpportunityDiscoveryEngine,
    CanonicalOpportunity,
)
from scripts.autonomous_single_pc_executor import (
    SinglePCAutonomousExecutor,
    COURIER_DIR,
)


class TestAutonomyAccelerationBuilderRound(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_autonomy_accel_"))
        (self.tmp_dir / "runtime/content").mkdir(parents=True)
        (self.tmp_dir / "events/autonomy-runtime").mkdir(parents=True)
        (self.tmp_dir / "events/opportunity-queue").mkdir(parents=True)
        (self.tmp_dir / "events/chief-brain").mkdir(parents=True)

        for f in ["runtime/content/catalog_manifest.json", "runtime/content/qc_batch_report.json"]:
            src = COURIER_DIR / f
            if src.is_file():
                shutil.copy(src, self.tmp_dir / f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_empty_queue_triggers_discovery(self):
        """When queue is empty, engine discovers actionable unblocked opportunities."""
        engine = AutonomousOpportunityDiscoveryEngine(repo_dir=self.tmp_dir)
        opps = engine.discover_opportunities(active_goals=["goal-creator-factory-autonomy"])
        self.assertTrue(len(opps) > 0)
        self.assertFalse(any("busywork" in o.description.lower() for o in opps))

    def test_02_multi_task_continuation_zero_prompt(self):
        """Executes at least 2 sequential tasks automatically without intermediate prompts."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-multi-001")
        rep = executor.execute_shift(max_steps=5)

        self.assertEqual(rep["autonomous_spend_eur"], 0.0)
        self.assertEqual(rep["publications"], 0)
        self.assertTrue(len(rep["completed_tasks"]) >= 2)
        self.assertIn("work-fruitki-inventory-summary", rep["completed_tasks"])
        self.assertIn("work-fruitki-pricing-manifest", rep["completed_tasks"])

    def test_03_high_value_vs_useful_ranking(self):
        """HIGH_VALUE critical-path items rank ahead of USEFUL and NEUTRAL."""
        engine = AutonomousOpportunityDiscoveryEngine(repo_dir=self.tmp_dir)

        opp_high = CanonicalOpportunity(
            opportunity_id="opp-high",
            description="Critical Path Revenue Item",
            priority=9,
            critical_path=True,
            status="READY",
        )
        opp_useful = CanonicalOpportunity(
            opportunity_id="opp-useful",
            description="Useful Summary Verification",
            priority=5,
            critical_path=False,
            status="READY",
        )
        opp_neutral = CanonicalOpportunity(
            opportunity_id="opp-neutral",
            description="Non-essential log check",
            priority=2,
            critical_path=False,
            status="READY",
        )

        ranked = engine.rank_opportunities([opp_neutral, opp_useful, opp_high])
        self.assertEqual(ranked[0].opportunity_id, "opp-high")
        self.assertEqual(ranked[1].opportunity_id, "opp-useful")
        self.assertEqual(ranked[2].opportunity_id, "opp-neutral")

    def test_04_duplicate_suppression_and_closed_strand(self):
        """Already completed tasks are categorized as SUPPRESSED and not re-executed."""
        engine = AutonomousOpportunityDiscoveryEngine(repo_dir=self.tmp_dir)
        engine.completed_signatures.add("work-done-01")

        opp = CanonicalOpportunity(
            opportunity_id="work-done-01",
            description="Already finished item",
            status="READY",
        )
        tier = engine.classify_opportunity_value_tier(opp)
        self.assertEqual(tier, "SUPPRESSED")

        ranked = engine.rank_opportunities([opp])
        self.assertEqual(len(ranked), 0)

    def test_05_restart_recovery_preserves_completed(self):
        """Restarting session preserves completed state and avoids redundant executions."""
        exec1 = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-restart-001")
        rep1 = exec1.execute_shift(max_steps=5)
        self.assertTrue(len(rep1["executed_tasks"]) >= 2)

        # Resume with fresh instance
        exec2 = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-restart-001")
        rep2 = exec2.execute_shift(max_steps=5)
        self.assertEqual(len(rep2["executed_tasks"]), 0)
        self.assertEqual(set(rep1["completed_tasks"]), set(rep2["completed_tasks"]))

    def test_06_stop_and_resume_semantics(self):
        """Session can be stopped cleanly and resumed from persisted state."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-stop-001")
        stop_res = executor.stop_session(reason="SAFETY_PAUSE")
        self.assertEqual(stop_res["status"], "STOPPED")
        self.assertEqual(executor.controller.session.status, "STOPPED")

        resume_res = executor.resume_session()
        self.assertIn(resume_res["final_status"], ["RUNNING", "SAFE_IDLE", "WAITING_HUMAN"])

    def test_07_human_money_gate_isolation(self):
        """Human/Money gates are parked safely with zero spend and zero publication."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-gates-001")
        rep = executor.execute_shift(max_steps=5)

        self.assertEqual(rep["autonomous_spend_eur"], 0.0)
        self.assertEqual(rep["publications"], 0)
        self.assertTrue(any(g["task_id"] == "work-fruitki-release-proposal" for g in rep["human_gates"]))

    def test_08_max_iteration_bounded_protection(self):
        """Executor respects max_steps bound without runaway iteration."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-bound-001")
        rep = executor.execute_shift(max_steps=2)
        self.assertLessEqual(rep["steps_run"], 2)


if __name__ == "__main__":
    unittest.main()
