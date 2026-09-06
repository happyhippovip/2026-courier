#!/usr/bin/env python3
"""Targeted unit and integration tests for Mission 185G: Real Local Autonomy Runtime."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_control_plane import AutonomyControlPlane
from scripts.evidence_provenance import check_for_secrets
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.real_autonomy_runtime import (
    JobStatus,
    NightSessionState,
    ProviderJobEnvelope,
    RealAutonomyRuntime,
    SessionStatus,
)


class TestRealAutonomyRuntimeMission185G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="autonomy_runtime_185g_"))
        self.runtime = RealAutonomyRuntime(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # Phase B: Real Event Ingestion & Correlation
    # --------------------------------------------------------------------------

    def test_01_real_event_ingestion_updates_brain_and_barriers(self):
        # Register a barrier first
        self.runtime.control_plane.register_barrier("bar-ing-1", "task-syn-1", ["corr-w1", "corr-w2"])

        # Ingest first real event
        res1 = self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="GOOGLE",
            correlation_id="corr-w1",
            payload={"outcome": "SUCCESS", "tests_passed": 5, "tests_failed": 0},
            task_id="task-sub-1",
        )
        self.assertEqual(res1["status"], "INGESTED")
        self.assertEqual(res1["satisfied_barriers"], [])

        # Ingest second real event
        res2 = self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="CODEX",
            correlation_id="corr-w2",
            payload={"outcome": "SUCCESS", "evidence": {"verified": True}},
            task_id="task-sub-2",
        )
        self.assertEqual(res2["status"], "INGESTED")
        self.assertEqual(res2["satisfied_barriers"], ["bar-ing-1"])

    def test_02_duplicate_event_ingestion_defense(self):
        res1 = self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="LOCAL",
            correlation_id="corr-dup-1",
            payload={"data": "unique_output"},
            task_id="task-dup-1",
        )
        self.assertEqual(res1["status"], "INGESTED")

        # Second identical event is detected and bypassed
        res2 = self.runtime.ingest_real_event(
            event_type="RESULT",
            source_worker="LOCAL",
            correlation_id="corr-dup-1",
            payload={"data": "unique_output"},
            task_id="task-dup-1",
        )
        self.assertEqual(res2["status"], "DUPLICATE_IGNORED")

    # --------------------------------------------------------------------------
    # Phase C & D: Automatic Next-Action Selection & Efficiency
    # --------------------------------------------------------------------------

    def test_03_automatic_next_action_selection_priority(self):
        # Add ready opportunity to queue
        opp = Opportunity(
            opportunity_id="OPP-TEST-AUTO-1",
            source="TEST",
            objective_id="OBJ-1",
            project="TEST_PROJECT",
            description="Run unit test audit",
            priority=9,
            risk="LOW",
            cost_class="ZERO_COST_LOCAL",
            status="READY",
        )
        self.runtime.opp_queue.add_opportunity(opp)

        session = self.runtime.start_night_session("sess-test-1", "Automated test audit")
        next_act = self.runtime.select_next_action(session)
        self.assertEqual(next_act["action_type"], "DISPATCH_JOB")
        self.assertTrue(next_act["admitted"])
        self.assertEqual(next_act["job_envelope"]["task_id"], "OPP-TEST-AUTO-1")

    def test_04_provider_job_envelope_structure_and_persistence(self):
        env = ProviderJobEnvelope(
            job_id="job-1234",
            task_id="task-render-qc",
            correlation_id="corr-1234",
            owner="GOOGLE",
            provider="GOOGLE_PRO",
            scope="runtime/content/watermelon",
            mutation_scope=["runtime/content/watermelon/render.mp4"],
            dependency_ids=[],
            context_reference="ctx-ref-watermelon",
            expected_unlock="QC PASS",
            resource_class="GOOGLE_PRO_POOL_1",
            risk_class="LOW",
            admission_reason="Admitted for render check",
        )
        self.runtime._save_job_envelope(env)
        loaded = self.runtime.get_job_envelope("job-1234")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.job_id, "job-1234")
        self.assertEqual(loaded.owner, "GOOGLE")
        self.assertEqual(loaded.status, JobStatus.PREPARED)

    # --------------------------------------------------------------------------
    # Phase G: Human & Money Branch Isolation
    # --------------------------------------------------------------------------

    def test_05_human_and_money_gates_isolated_without_stopping_independent_work(self):
        # Add a Human-gated opportunity
        opp_human = Opportunity(
            opportunity_id="OPP-HUMAN-GATE-1",
            source="TEST",
            objective_id="OBJ-HG",
            project="HUMAN_BRANCH",
            description="Human signoff required",
            priority=10,
            status="WAITING_FOR_HUMAN",
        )
        # Add an independent safe opportunity
        opp_safe = Opportunity(
            opportunity_id="OPP-SAFE-INDEP-1",
            source="TEST",
            objective_id="OBJ-SAFE",
            project="INDEPENDENT_BRANCH",
            description="Local checksum verification",
            priority=7,
            status="READY",
        )
        self.runtime.opp_queue.add_opportunity(opp_human)
        self.runtime.opp_queue.add_opportunity(opp_safe)

        session = self.runtime.start_night_session("sess-iso", "Test branch isolation")
        next_act = self.runtime.select_next_action(session)

        # Human gate parked, independent safe task selected
        self.assertEqual(next_act["action_type"], "DISPATCH_JOB")
        self.assertEqual(next_act["job_envelope"]["task_id"], "OPP-SAFE-INDEP-1")
        self.assertEqual(len(session.human_gates_encountered), 1)

    # --------------------------------------------------------------------------
    # Phase H & I: Restart Recovery & Night Session Controller
    # --------------------------------------------------------------------------

    def test_06_restart_recovery_restores_session_and_ledger(self):
        session = self.runtime.start_night_session("sess-recover", "Recovery test session")
        session.jobs_completed.append("task-step-1")
        self.runtime._save_session(session)

        # Simulate process crash and restart
        restarted_runtime = RealAutonomyRuntime(repo_dir=self.test_dir)
        loaded_session = restarted_runtime._load_session()
        self.assertIsNotNone(loaded_session)
        self.assertEqual(loaded_session.session_id, "sess-recover")
        self.assertIn("task-step-1", loaded_session.jobs_completed)

    # --------------------------------------------------------------------------
    # Phase J: Morning Report Determinism
    # --------------------------------------------------------------------------

    def test_07_morning_report_generation(self):
        session = self.runtime.start_night_session("sess-rep", "Morning report test")
        session.jobs_completed.extend(["task-1", "task-2"])
        session.status = SessionStatus.COMPLETED

        report = self.runtime.generate_morning_report(session)
        self.assertEqual(report["session_id"], "sess-rep")
        self.assertEqual(report["useful_tasks_completed_count"], 2)
        self.assertEqual(report["autonomous_spend_eur"], 0.0)
        self.assertTrue(Path(session.morning_report_path).is_file())

    # --------------------------------------------------------------------------
    # Phase K: Multi-Step Zero-Copy-Paste Execution Proof
    # --------------------------------------------------------------------------

    def test_08_multi_step_zero_copy_paste_execution_chain(self):
        """Proves complete unattended end-to-end execution without manual copy/paste."""
        # 1. Setup session
        session = self.runtime.start_night_session(
            session_id="sess-zero-cp",
            goal="Execute multi-step pipeline without human copy-paste",
            max_iterations=10,
        )

        # 2. Add Task 1: Deterministic check
        opp1 = Opportunity(
            opportunity_id="OPP-STEP-1-DET",
            source="TEST",
            objective_id="OBJ-CHAIN",
            project="CHAIN_PROJ",
            description="Validate hash signatures",
            priority=9,
            status="READY",
        )
        self.runtime.opp_queue.add_opportunity(opp1)

        # Mock deterministic resolver
        resolver = lambda tid: (True, {"hash_valid": True}) if tid == "OPP-STEP-1-DET" else (False, None)
        # Mock job executor for dispatched jobs
        executor = lambda env: {"success": True, "output": f"Executed {env.task_id}"}

        # Step 1: Executes deterministic task without copy/paste
        res1 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res1["status"], "PROGRESS_MADE")
        self.assertEqual(res1["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")
        opp1.status = "COMPLETED"
        self.runtime.opp_queue.save_opportunity(opp1)

        # Step 2: Register dependency barrier for Task 3 requiring Task 2A and 2B
        self.runtime.control_plane.register_barrier("bar-chain", "OPP-STEP-3-SYNTHESIS", ["corr-2a", "corr-2b"])

        # Add Task 2A to queue
        opp2a = Opportunity(
            opportunity_id="OPP-STEP-2A",
            source="TEST",
            objective_id="OBJ-CHAIN",
            project="CHAIN_PROJ",
            description="Worker 2A processing",
            priority=8,
            status="READY",
        )
        self.runtime.opp_queue.add_opportunity(opp2a)

        # Step 2: Dispatches Task 2A and auto-ingests its result
        res2 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res2["status"], "PROGRESS_MADE")
        self.assertEqual(res2["transition"]["action_type"], "DISPATCH_JOB")
        opp2a.status = "COMPLETED"
        self.runtime.opp_queue.save_opportunity(opp2a)

        # Ingest 2A result into barrier correlation
        self.runtime.ingest_real_event("RESULT", "GOOGLE", "corr-2a", {"done": True}, "OPP-STEP-2A")

        # Add Task 2B to queue
        opp2b = Opportunity(
            opportunity_id="OPP-STEP-2B",
            source="TEST",
            objective_id="OBJ-CHAIN",
            project="CHAIN_PROJ",
            description="Worker 2B processing",
            priority=8,
            status="READY",
        )
        self.runtime.opp_queue.add_opportunity(opp2b)

        # Step 3: Dispatches Task 2B
        res3 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res3["status"], "PROGRESS_MADE")
        opp2b.status = "COMPLETED"
        self.runtime.opp_queue.save_opportunity(opp2b)

        # Ingest 2B result -> barrier satisfies
        self.runtime.ingest_real_event("RESULT", "CODEX", "corr-2b", {"done": True}, "OPP-STEP-2B")

        # Step 4: Next step automatically detects satisfied barrier and synthesizes
        res4 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res4["status"], "PROGRESS_MADE")
        self.assertEqual(res4["transition"]["action_type"], "SYNTHESIS")

        # Step 5: With no remaining backlog, loop transitions to IDLE_EXPECTED and generates morning report
        res5 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res5["status"], "IDLE_EXPECTED")
        self.assertTrue(res5.get("morning_report"))
        self.assertGreaterEqual(res5["morning_report"]["useful_tasks_completed_count"], 3)


if __name__ == "__main__":
    unittest.main()
