#!/usr/bin/env python3
"""Mission 187G: Long Sleep Autonomy Acceptance Test Suite."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_control_plane import AutonomyControlPlane
from scripts.chief_brain import ChiefBrain
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.real_autonomy_runtime import (
    ProviderJobEnvelope,
    RealAutonomyRuntime,
    SessionStatus,
)


class TestLongSleepAutonomyMission187G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="long_sleep_187g_test_"))
        self.runtime = RealAutonomyRuntime(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pre_flight_safety_and_firewalls(self):
        self.assertEqual(self.runtime.AUTONOMOUS_SPEND_LIMIT_EUR, 0.0)
        self.assertEqual(self.runtime.PUBLICATION_AUTHORIZATION_INFERENCE, "DENY")
        snap = self.runtime.control_plane.reconstruct_canonical_state()
        self.assertEqual(snap["autonomy_state"], "ACTIVE_DETERMINISTIC_FIRST")
        self.assertEqual(snap["money_firewall_spend_limit_eur"], 0.0)

    def test_02_full_long_sleep_unattended_chain_with_restart(self):
        # 1. Start long sleep session
        session = self.runtime.start_night_session(
            session_id="session-187g-test-sleep",
            goal="Test long sleep unattended autonomy loop",
            max_runtime_minutes=600,
            max_iterations=20,
        )
        self.assertEqual(session.status, SessionStatus.RUNNING)

        # 2. Add real canonical opportunities
        opp1 = Opportunity(
            opportunity_id="OPP-187G-T1-CREATOR",
            source="CREATOR_FACTORY",
            objective_id="OBJ-187G",
            project="CREATOR_FACTORY",
            description="Creator package integrity audit",
            priority=10,
            status="READY",
        )
        opp2 = Opportunity(
            opportunity_id="OPP-187G-T2-RESOURCE",
            source="RESOURCE_INTELLIGENCE",
            objective_id="OBJ-187G",
            project="RESOURCE_INTELLIGENCE",
            description="Resource reset segmentation audit",
            priority=9,
            status="READY",
        )
        opp_human = Opportunity(
            opportunity_id="OPP-187G-T-HUMAN",
            source="CREATOR_FACTORY",
            objective_id="OBJ-187G",
            project="HUMAN_BRANCH",
            description="Audience decision required",
            priority=10,
            status="WAITING_FOR_HUMAN",
        )
        opp_money = Opportunity(
            opportunity_id="OPP-187G-T-MONEY",
            source="EXTERNAL_API",
            objective_id="OBJ-187G",
            project="MONEY_BRANCH",
            description="Payment authorization required",
            priority=10,
            status="PAYMENT_APPROVAL_REQUIRED",
        )
        opp_indep = Opportunity(
            opportunity_id="OPP-187G-T-INDEP",
            source="DISASTER_RECOVERY",
            objective_id="OBJ-187G",
            project="DISASTER_RECOVERY",
            description="Disaster recovery sandbox check",
            priority=7,
            status="READY",
        )

        self.runtime.opp_queue.add_opportunity(opp1)
        self.runtime.opp_queue.add_opportunity(opp2)
        self.runtime.opp_queue.add_opportunity(opp_human)
        self.runtime.opp_queue.add_opportunity(opp_money)
        self.runtime.opp_queue.add_opportunity(opp_indep)

        # Register multi-worker barrier
        self.runtime.control_plane.register_barrier("BARRIER-187G-TEST", "OPP-187G-SYNTHESIS", ["CORR-WA", "CORR-WB"])

        resolver = lambda tid: (True, {"verified": True}) if tid.startswith("OPP-187G-T") else (False, {})
        executor = lambda env: {"success": True, "output": f"Executed {env.task_id}"}

        # Step 1: Opp 1 executes
        res1 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res1["status"], "PROGRESS_MADE")
        self.assertEqual(res1["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")

        # Step 2: Opp 2 executes
        res2 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res2["status"], "PROGRESS_MADE")
        self.assertEqual(res2["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")

        # Controlled Runtime Restart
        restarted_runtime = RealAutonomyRuntime(repo_dir=self.test_dir)
        loaded_sess = restarted_runtime._load_session()
        self.assertIsNotNone(loaded_sess)
        self.assertIn("OPP-187G-T1-CREATOR", loaded_sess.jobs_completed)
        self.assertIn("OPP-187G-T2-RESOURCE", loaded_sess.jobs_completed)

        # Ingest barrier results
        ingA = restarted_runtime.ingest_real_event("RESULT", "GOOGLE", "CORR-WA", {"part": "a"}, "OPP-187G-WA")
        self.assertEqual(ingA["status"], "INGESTED")

        # Ingest duplicate result to test deduplication
        ingA_dup = restarted_runtime.ingest_real_event("RESULT", "GOOGLE", "CORR-WA", {"part": "a"}, "OPP-187G-WA")
        self.assertEqual(ingA_dup["status"], "DUPLICATE_IGNORED")

        ingB = restarted_runtime.ingest_real_event("RESULT", "CODEX", "CORR-WB", {"part": "b"}, "OPP-187G-WB")
        self.assertEqual(ingB["status"], "INGESTED")
        self.assertIn("BARRIER-187G-TEST", ingB["satisfied_barriers"])

        # Step 3: Synthesis fires automatically
        res3 = restarted_runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res3["status"], "PROGRESS_MADE")
        self.assertEqual(res3["transition"]["action_type"], "SYNTHESIS")

        # Step 4: Independent task executes while Human & Money gates remain parked
        res4 = restarted_runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res4["status"], "PROGRESS_MADE")
        self.assertEqual(res4["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")
        self.assertEqual(len(restarted_runtime._load_session().human_gates_encountered), 1)
        self.assertEqual(len(restarted_runtime._load_session().money_gates_encountered), 1)

        # Step 5: Clean transition to IDLE_EXPECTED with Morning Report
        res5 = restarted_runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res5["status"], "IDLE_EXPECTED")
        morning_rep = res5.get("morning_report")
        self.assertIsNotNone(morning_rep)
        self.assertEqual(morning_rep["useful_tasks_completed_count"], 4)
        self.assertEqual(morning_rep["autonomous_spend_eur"], 0.0)
        self.assertEqual(morning_rep["human_gates_waiting_count"], 1)
        self.assertEqual(morning_rep["money_gates_waiting_count"], 1)


if __name__ == "__main__":
    unittest.main()
