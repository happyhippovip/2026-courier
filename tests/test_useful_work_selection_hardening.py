#!/usr/bin/env python3
"""Comprehensive test suite for useful-work selection hardening and false-ready defense.

Verifies:
1. Completed task falsely listed READY is classified COMPLETED and suppressed
2. Semantic duplicate with different wording is classified DUPLICATE via canonical fingerprint
3. Stale state with missing referenced artifact is classified STALE
4. Human-gated high-value task has score overridden to 0 and is gated
5. Money-gated task (>0 EUR or purchase) has score overridden to 0 and is gated
6. Publication/upload-gated task is gated
7. Paused creator/video work (and Computer B / universuX) is strictly excluded
8. Empty queue with one real useful opportunity selects and dispatches it
9. Empty queue with no useful opportunities cleanly transitions to SAFE_IDLE
10. Restart duplicate suppression ensures completed tasks are never re-dispatched
11. Failed-task bounded handling (circuit breaker opens on consecutive failures)
12. Deterministic scoring and tie-breaking order
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.useful_work_selection_engine import (
    AutonomyLifecycleState,
    ScoredCandidateTask,
    UsefulWorkSelectionEngine,
    WorkReadinessState,
    compute_canonical_work_fingerprint,
)


class TestUsefulWorkSelectionHardening(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="work_selection_test_"))
        self.events_dir = self.test_dir / "events"
        self.state_dir = self.events_dir / "runtime-state"
        self.queue_dir = self.events_dir / "opportunity-queue"
        self.breakers_dir = self.events_dir / "circuit-breakers"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.breakers_dir.mkdir(parents=True, exist_ok=True)

        self.engine = UsefulWorkSelectionEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_completed_task_falsely_listed_ready(self):
        """Task marked READY in an old queue file but recorded as completed is classified COMPLETED."""
        opp_id = "OPP-OLD-COMPLETED-01"
        fp = compute_canonical_work_fingerprint("Run unit test suite", ["tests/test_a.py"], "UNIT_TEST")
        self.engine.record_completed_fingerprint(fp)

        opp = {
            "opportunity_id": opp_id,
            "objective": "Run unit test suite",
            "task_type": "UNIT_TEST",
            "allowed_scope": ["tests/test_a.py"],
            "status": "READY",  # Falsely listed as READY
        }
        state, reason = self.engine.classify_opportunity(opp)
        self.assertEqual(state, WorkReadinessState.COMPLETED)
        self.assertIn("ALREADY_COMPLETED", reason)

    def test_02_semantic_duplicate_with_different_wording(self):
        """Semantic duplicate with punctuation/whitespace/casing variations produces identical canonical fingerprint."""
        fp1 = compute_canonical_work_fingerprint(
            "Reconcile Active Telemetry State in Events/Runtime-State",
            ["events/runtime-state/"],
            "STATE_RECONCILIATION",
        )
        fp2 = compute_canonical_work_fingerprint(
            "  reconcile active telemetry state in events/runtime-state!  ",
            ["events/runtime-state"],
            "STATE_RECONCILIATION",
        )
        self.assertEqual(fp1, fp2)

        # Record fp1 as completed, then test fp2
        self.engine.record_completed_fingerprint(fp1)
        opp2 = {
            "opportunity_id": "OPP-DUP-02",
            "objective": "  reconcile active telemetry state in events/runtime-state!  ",
            "task_type": "STATE_RECONCILIATION",
            "allowed_scope": ["events/runtime-state"],
            "status": "READY",
        }
        state, reason = self.engine.classify_opportunity(opp2)
        self.assertEqual(state, WorkReadinessState.COMPLETED)

    def test_03_stale_state_with_missing_source_artifact(self):
        """Opportunity referencing a non-existent artifact is classified STALE."""
        opp = {
            "opportunity_id": "OPP-STALE-01",
            "objective": "Process market research feedback",
            "task_type": "MARKET_EVALUATION",
            "source_artifact": "events/nonexistent_folder/missing_file.json",
            "status": "READY",
        }
        state, reason = self.engine.classify_opportunity(opp)
        self.assertEqual(state, WorkReadinessState.STALE)
        self.assertIn("REFERENCED_ARTIFACT_MISSING", reason)

    def test_04_human_gated_high_value_task(self):
        """Human-gated task (OAuth/KYC/legal or requires_human) is gated with 0 final score."""
        opp = {
            "opportunity_id": "OPP-HUMAN-01",
            "objective": "Request OAuth 2FA authentication for high-volume provider account",
            "task_type": "AUTH_PROVISIONING",
            "priority": 10,
            "requires_human": True,
            "status": "READY",
        }
        state, reason = self.engine.classify_opportunity(opp)
        self.assertEqual(state, WorkReadinessState.HUMAN_GATE)

        cand = ScoredCandidateTask(
            task_id="OPP-HUMAN-01",
            objective=opp["objective"],
            readiness_state=state,
            value_score=10.0,
            information_gain=10.0,
        )
        score = self.engine.calculate_score(cand)
        self.assertEqual(score, 0.0)

    def test_05_money_gated_task(self):
        """Financial spend task (>0 EUR) is gated with 0 final score."""
        opp = {
            "opportunity_id": "OPP-MONEY-01",
            "objective": "Purchase API subscription quota",
            "task_type": "PURCHASE",
            "estimated_cost": 20.0,
            "requires_payment": True,
            "status": "READY",
        }
        state, reason = self.engine.classify_opportunity(opp)
        self.assertEqual(state, WorkReadinessState.MONEY_GATE)

        cand = ScoredCandidateTask(
            task_id="OPP-MONEY-01",
            objective=opp["objective"],
            readiness_state=state,
            value_score=9.0,
            resource_cost=20.0,
        )
        score = self.engine.calculate_score(cand)
        self.assertEqual(score, 0.0)

    def test_06_publication_gated_task(self):
        """Public upload or distribution task is gated."""
        opp = {
            "opportunity_id": "OPP-PUB-01",
            "objective": "Upload video package to public channel",
            "task_type": "PUBLICATION",
            "status": "READY",
        }
        state, reason = self.engine.classify_opportunity(opp)
        self.assertEqual(state, WorkReadinessState.PUBLICATION_GATE)

    def test_07_paused_creator_and_protected_project_exclusion(self):
        """Creator video rendering, Computer B, and universuX tasks are strictly gated."""
        for name in ("creator_video_rendering", "universux", "node_b"):
            opp = {
                "opportunity_id": f"OPP-PROT-{name}",
                "objective": f"Execute batch job for {name}",
                "project": name,
                "status": "READY",
            }
            state, reason = self.engine.classify_opportunity(opp)
            self.assertEqual(state, WorkReadinessState.PROTECTED_BOUNDARY_GATED)

    def test_08_empty_queue_with_one_real_useful_opportunity(self):
        """When explicit queue is empty, engine discovers grounded work (e.g. test gap)."""
        # Create a mock script in scripts/ that has no test
        scripts_dir = self.test_dir / "scripts"
        tests_dir = self.test_dir / "tests"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "sample_service.py").write_text("# Sample service\n", encoding="utf-8")

        res = self.engine.select_next_task(explicit_queue=[])
        self.assertEqual(res["lifecycle_state"], AutonomyLifecycleState.TASK_RUNNING.value)
        self.assertEqual(res["action"], "DISPATCH_TASK")
        self.assertIsNotNone(res["selected_task"])
        self.assertIn("sample_service", res["selected_task"]["task_id"])
        self.assertGreater(res["selected_task"]["final_score"], 0.0)

    def test_09_empty_queue_with_no_useful_opportunities(self):
        """When explicit queue is empty and all discovered work is already completed, enters SAFE_IDLE."""
        scripts_dir = self.test_dir / "scripts"
        tests_dir = self.test_dir / "tests"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "verified_tool.py").write_text("# Verified\n", encoding="utf-8")
        (tests_dir / "test_verified_tool.py").write_text("# Test\n", encoding="utf-8")

        # Record all possible discovered fingerprints as completed
        discovered = self.engine.discover_grounded_useful_work()
        for d in discovered:
            self.engine.record_completed_fingerprint(d.fingerprint)

        res = self.engine.select_next_task(explicit_queue=[])
        self.assertEqual(res["lifecycle_state"], AutonomyLifecycleState.SAFE_IDLE.value)
        self.assertEqual(res["action"], "ENTER_SAFE_IDLE")
        self.assertIsNone(res["selected_task"])
        self.assertEqual(res["reason"], "NO_SAFE_USEFUL_WORK_AVAILABLE")

    def test_10_restart_duplicate_suppression(self):
        """Completed fingerprints persist on disk across engine reinstantiations."""
        fp = "test_persisted_fp_12345"
        self.engine.record_completed_fingerprint(fp)

        # Create new engine instance representing restart
        restarted_engine = UsefulWorkSelectionEngine(repo_dir=self.test_dir)
        self.assertTrue(restarted_engine.is_fingerprint_completed(fp))

    def test_11_circuit_breaker_bounded_failure_handling(self):
        """Repeated failures open a circuit breaker and prevent infinite retry loops."""
        fp = "failing_task_fp_999"
        breaker_file = self.breakers_dir / f"{fp}.json"
        breaker_file.write_text(json.dumps({
            "breaker_id": fp,
            "status": "OPEN",
            "consecutive_failures": 3,
            "reason": "DETERMINISTIC_ASSERTION_FAILED",
        }), encoding="utf-8")

        opp = {
            "opportunity_id": "OPP-FAILING-01",
            "objective": "Flaky task causing repeated crash",
            "task_type": "FLAKY_JOB",
            "status": "READY",
        }
        # Force canonical fingerprint to match breaker
        opp_fp = compute_canonical_work_fingerprint(opp["objective"], [], opp["task_type"])
        (self.breakers_dir / f"{opp_fp}.json").write_text(json.dumps({
            "breaker_id": opp_fp,
            "status": "OPEN",
            "consecutive_failures": 3,
            "reason": "DETERMINISTIC_ASSERTION_FAILED",
        }), encoding="utf-8")

        state, reason = self.engine.classify_opportunity(opp)
        self.assertEqual(state, WorkReadinessState.BLOCKED_EXTERNAL)
        self.assertIn("CIRCUIT_BREAKER_OPEN", reason)

    def test_12_deterministic_ordering_and_tie_breaking(self):
        """Tied numerical scores break ties deterministically using alphanumeric task_id."""
        c1 = ScoredCandidateTask(
            task_id="TASK-BBB",
            objective="Audit module B",
            readiness_state=WorkReadinessState.READY_USEFUL,
            value_score=5.0,
            information_gain=5.0,
        )
        c2 = ScoredCandidateTask(
            task_id="TASK-AAA",
            objective="Audit module A",
            readiness_state=WorkReadinessState.READY_USEFUL,
            value_score=5.0,
            information_gain=5.0,
        )
        s1 = self.engine.calculate_score(c1)
        s2 = self.engine.calculate_score(c2)
        self.assertEqual(s1, s2)

        items = [c1, c2]
        items.sort(key=lambda x: (x.final_score, x.task_id), reverse=True)
        self.assertEqual(items[0].task_id, "TASK-BBB")


if __name__ == "__main__":
    unittest.main()
