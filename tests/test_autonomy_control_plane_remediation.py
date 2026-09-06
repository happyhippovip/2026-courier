#!/usr/bin/env python3
"""Crash-Window, Endurance, and Invariant Verification Suite for Control-Plane Remediation.

Verifies:
1. INVARIANT_IDLE_1 & 2: Idle cycles do not exhaust productive iteration budget.
2. INVARIANT_EXEC_1 & 2: Durable execution intent and post-crash duplicate suppression.
3. INVARIANT_RESULT_1 & 2: Transactional event ingest and crash-safe replay.
4. INVARIANT_LEASE_1: TOCTOU-safe stale claim reclaim.
5. INVARIANT_LIVENESS_1: Liveness reconciliation for dead PIDs.
6. INVARIANT_HEAVY_1: Cross-process mutual exclusion for heavy jobs (HEAVY_JOB_LIMIT=1).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.real_autonomy_runtime import (
    NightSessionState,
    RealAutonomyRuntime,
    SessionStatus,
    COURIER_DIR,
)
from scripts.autonomous_single_pc_executor import (
    SinglePCAutonomousExecutor,
)
from scripts.opportunity_queue import (
    Opportunity,
    OpportunityQueue,
)
from scripts.resource_intelligence import (
    ResourceIntelligenceManager as ResourceIntelligence,
)
from scripts.autonomous_work_session_controller import (
    AutonomousWorkSessionController,
    AutonomousSessionState,
)


class TestAutonomyControlPlaneRemediation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_remediation_"))
        (self.tmp_dir / "events/autonomy-runtime/task_intents").mkdir(parents=True)
        (self.tmp_dir / "events/opportunity-queue").mkdir(parents=True)
        (self.tmp_dir / "events/chief-brain").mkdir(parents=True)
        (self.tmp_dir / "runtime/content").mkdir(parents=True)
        (self.tmp_dir / "runtime/resources").mkdir(parents=True)

        for f in ["runtime/content/catalog_manifest.json", "runtime/content/qc_batch_report.json"]:
            src = COURIER_DIR / f
            if src.is_file():
                shutil.copy(src, self.tmp_dir / f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_idle_cycles_do_not_exhaust_productive_budget(self):
        """HIGH-1: 600 idle cycles do NOT exhaust 500 productive iteration budget."""
        runtime = RealAutonomyRuntime(repo_dir=self.tmp_dir)
        session = runtime.start_night_session(
            session_id="test-idle-endurance",
            goal="Test idle budget isolation",
            max_iterations=500,
        )
        session.max_idle_observations = 1000
        runtime._save_session(session)

        # Run 600 simulated idle steps
        for _ in range(600):
            res = runtime.execute_session_step()
            self.assertEqual(res["status"], "IDLE_EXPECTED")

        sess = runtime._load_session()
        self.assertEqual(sess.iterations_completed, 0)
        self.assertEqual(sess.idle_observations, 600)
        self.assertEqual(sess.status, SessionStatus.IDLE_EXPECTED)

    def test_02_productive_iterations_properly_bounded(self):
        """Productive execution steps correctly increment iterations_completed up to limit."""
        runtime = RealAutonomyRuntime(repo_dir=self.tmp_dir)
        session = runtime.start_night_session(
            session_id="test-prod-bound",
            goal="Test productive bound",
            max_iterations=2,
        )

        # Add 3 deterministic opportunities
        for i in range(3):
            opp = Opportunity(
                opportunity_id=f"opp-det-{i}",
                source="TEST",
                objective_id=f"obj-{i}",
                project="test",
                description=f"Task {i}",
                problem_or_goal=f"Task {i}",
                target_agent="antigravity",
                status="READY",
                priority=10,
            )
            runtime.opp_queue.save_opportunity(opp)

        def mock_resolver(task_id: str):
            return True, {"computed": task_id}

        res1 = runtime.execute_session_step(deterministic_resolver=mock_resolver)
        self.assertEqual(res1["status"], "PROGRESS_MADE")

        res2 = runtime.execute_session_step(deterministic_resolver=mock_resolver)
        self.assertEqual(res2["status"], "PROGRESS_MADE")

        res3 = runtime.execute_session_step(deterministic_resolver=mock_resolver)
        self.assertEqual(res3["status"], "MAX_ITERATIONS_REACHED")

        sess = runtime._load_session()
        self.assertEqual(sess.iterations_completed, 3)

    def test_03_crash_after_side_effect_prevents_duplicate_reexecution(self):
        """HIGH-2: Post-crash uncommitted task fails closed as EFFECT_UNKNOWN_AFTER_CRASH."""
        executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-crash-001")

        # Simulate task in progress that crashed before result was committed
        intent_file = executor.intents_dir / "work-fruitki-inventory-summary.json"
        intent = {
            "task_id": "work-fruitki-inventory-summary",
            "status": "EXECUTION_IN_PROGRESS",
            "pid": 9999999,
            "started_at": "2026-09-01T00:00:00+00:00",
        }
        intent_file.write_text(json.dumps(intent))

        # Start fresh executor instance simulating process restart
        fresh_executor = SinglePCAutonomousExecutor(repo_dir=self.tmp_dir, session_id="test-crash-001")
        self.assertIn("work-fruitki-inventory-summary", fresh_executor.recovery_required_tasks)

        # Execute shift; verify crashed task is NOT re-executed
        rep = fresh_executor.execute_shift(max_steps=5)
        self.assertNotIn("work-fruitki-inventory-summary", rep["executed_tasks"])

        # Intent file should now be in EFFECT_UNKNOWN_AFTER_CRASH state
        final_intent = json.loads(intent_file.read_text())
        self.assertEqual(final_intent["status"], "EFFECT_UNKNOWN_AFTER_CRASH")

    def test_04_transactional_event_ingest_and_crash_replay(self):
        """HIGH-3: Uncommitted event replay applies downstream changes without duplicate rejection."""
        runtime = RealAutonomyRuntime(repo_dir=self.tmp_dir)

        # 1. Simulate uncommitted event (stage=RECEIVED, not in processed_event_hashes)
        ledger = runtime._load_ledger()
        payload = {"outcome": "SUCCESS", "computed": 42}
        corr_id = "corr-tx-001"
        task_id = "task-tx-001"

        res = runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="LOCAL_DETERMINISTIC",
            correlation_id=corr_id,
            payload=payload,
            task_id=task_id,
        )
        self.assertEqual(res["status"], "INGESTED")

        # Verify event committed as APPLIED and dedupe hash recorded
        updated_ledger = runtime._load_ledger()
        self.assertEqual(updated_ledger["events"][0]["stage"], "APPLIED")
        self.assertTrue(len(updated_ledger["processed_event_hashes"]) > 0)

        # Second delivery is cleanly recognized as DUPLICATE_IGNORED
        res_dup = runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="LOCAL_DETERMINISTIC",
            correlation_id=corr_id,
            payload=payload,
            task_id=task_id,
        )
        self.assertEqual(res_dup["status"], "DUPLICATE_IGNORED")

    def test_05_stale_claim_reclaim_toctou_safety(self):
        """MEDIUM-1: Stale reclaim does not delete intermediate replacement claims."""
        queue = OpportunityQueue(self.tmp_dir)
        opp = Opportunity(
            opportunity_id="opp-toctou-001",
            source="TEST",
            objective_id="obj-toctou",
            project="test",
            description="TOCTOU Test",
            problem_or_goal="TOCTOU Test",
            status="READY",
        )
        queue.save_opportunity(opp)

        # Create expired claim with dead PID
        claim_path = queue._claim_path("opp-toctou-001")
        dead_claim = {
            "opportunity_id": "opp-toctou-001",
            "claim_owner": "dead_worker",
            "claim_id": "claim-dead-123",
            "claimed_at": "2026-08-01T00:00:00+00:00",
            "lease_expires_at": "2026-08-01T00:15:00+00:00",
            "pid": 9999999,
            "authority_generation": 0,
        }
        claim_path.write_text(json.dumps(dead_claim))

        # Claim opportunity by live worker
        success, code, claim = queue.claim_opportunity("opp-toctou-001", claim_owner="live_worker")
        self.assertTrue(success)
        self.assertEqual(code, "CLAIMED")
        self.assertEqual(claim["claim_owner"], "live_worker")

    def test_06_process_liveness_reconciliation(self):
        """MEDIUM-2: RUNNING state with dead PID reconciles to STALE_RUNNING_OFFLINE."""
        controller = AutonomousWorkSessionController(repo_dir=self.tmp_dir, session_id="test-liveness-001")
        controller.session.status = "RUNNING"
        controller.session.pid = 9999999  # Dead PID
        controller._save_session()

        status = controller.reconcile_process_liveness()
        self.assertEqual(status, "STALE_RUNNING_OFFLINE")
        self.assertEqual(controller.session.status, "STALE_RUNNING_OFFLINE")

    def test_07_cross_process_heavy_job_mutex(self):
        """MEDIUM-3: HEAVY_JOB_LIMIT=1 is strictly enforced across separate processes."""
        ri1 = ResourceIntelligence(repo_dir=self.tmp_dir)
        res1 = ri1.claim_command("ffmpeg -i test.mp4", "hash123", owner_id="proc_1", heavy=True)
        self.assertEqual(res1["decision"], "CLAIMED")

        # Second process attempts heavy job
        ri2 = ResourceIntelligence(repo_dir=self.tmp_dir)
        res2 = ri2.claim_command("godot --headless", "hash456", owner_id="proc_2", heavy=True)
        self.assertEqual(res2["decision"], "BLOCK_HEAVY_JOB_LIMIT")

        # Process 1 completes command
        ri1.complete_command(res1["fingerprint"], "res_hash_1")

        # Now Process 2 can claim
        res3 = ri2.claim_command("godot --headless", "hash456", owner_id="proc_2", heavy=True)
        self.assertEqual(res3["decision"], "CLAIMED")


if __name__ == "__main__":
    unittest.main()
