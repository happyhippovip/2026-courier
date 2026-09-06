#!/usr/bin/env python3
"""Mission 186G Real Unattended Autonomy Acceptance Test Suite."""

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


class TestUnattendedAutonomyAcceptanceMission186G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="unattended_186g_test_"))
        self.runtime = RealAutonomyRuntime(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pre_run_safety_checks(self):
        self.assertEqual(self.runtime.AUTONOMOUS_SPEND_LIMIT_EUR, 0.0)
        self.assertEqual(self.runtime.PUBLICATION_AUTHORIZATION_INFERENCE, "DENY")
        snap = self.runtime.control_plane.reconstruct_canonical_state()
        self.assertEqual(snap["autonomy_state"], "ACTIVE_DETERMINISTIC_FIRST")

    def test_02_end_to_end_unattended_session_with_controlled_restart(self):
        # 1. Start session
        session = self.runtime.start_night_session(
            session_id="sess-186g-unit",
            goal="Mission 186G Unit Acceptance Run",
            max_runtime_minutes=60,
            max_iterations=10,
        )

        # 2. Add real task 1 and task 2
        opp1 = Opportunity(
            opportunity_id="OPP-186G-U1",
            source="TEST",
            objective_id="OBJ-186G",
            project="TEST_PROJ",
            description="Creator package audit",
            priority=9,
            status="READY",
        )
        opp2 = Opportunity(
            opportunity_id="OPP-186G-U2",
            source="TEST",
            objective_id="OBJ-186G",
            project="TEST_PROJ",
            description="Resource intelligence verification",
            priority=9,
            status="READY",
        )
        opp_human = Opportunity(
            opportunity_id="OPP-186G-U-HUMAN",
            source="TEST",
            objective_id="OBJ-186G",
            project="HUMAN_BRANCH",
            description="Human audience decision required",
            priority=10,
            status="WAITING_FOR_HUMAN",
        )
        opp_money = Opportunity(
            opportunity_id="OPP-186G-U-MONEY",
            source="TEST",
            objective_id="OBJ-186G",
            project="MONEY_BRANCH",
            description="Payment authorization required",
            priority=10,
            status="PAYMENT_APPROVAL_REQUIRED",
        )
        opp_indep = Opportunity(
            opportunity_id="OPP-186G-U-INDEP",
            source="TEST",
            objective_id="OBJ-186G",
            project="INDEPENDENT_BRANCH",
            description="Disaster recovery check",
            priority=7,
            status="READY",
        )

        self.runtime.opp_queue.add_opportunity(opp1)
        self.runtime.opp_queue.add_opportunity(opp2)
        self.runtime.opp_queue.add_opportunity(opp_human)
        self.runtime.opp_queue.add_opportunity(opp_money)
        self.runtime.opp_queue.add_opportunity(opp_indep)

        # Setup barrier
        self.runtime.control_plane.register_barrier("BARRIER-186G-U", "OPP-186G-U-SYNTHESIS", ["CORR-U1", "CORR-U2"])

        resolver = lambda tid: (True, {"verified": True}) if tid in ("OPP-186G-U1", "OPP-186G-U2", "OPP-186G-U-INDEP") else (False, {})
        executor = lambda env: {"success": True, "output": f"Executed {env.task_id}"}

        # Step 1: Execute Opp 1
        res1 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res1["status"], "PROGRESS_MADE")
        self.assertEqual(res1["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")

        # Step 2: Execute Opp 2
        res2 = self.runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res2["status"], "PROGRESS_MADE")
        self.assertEqual(res2["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")

        # Controlled Restart
        restarted_runtime = RealAutonomyRuntime(repo_dir=self.test_dir)
        loaded_sess = restarted_runtime._load_session()
        self.assertIsNotNone(loaded_sess)
        self.assertIn("OPP-186G-U1", loaded_sess.jobs_completed)
        self.assertIn("OPP-186G-U2", loaded_sess.jobs_completed)

        # Step 3: Ingest worker result 1 & duplicate defense
        ing1 = restarted_runtime.ingest_real_event("RESULT", "GOOGLE", "CORR-U1", {"done": True}, "OPP-186G-W1")
        self.assertEqual(ing1["status"], "INGESTED")
        ing1_dup = restarted_runtime.ingest_real_event("RESULT", "GOOGLE", "CORR-U1", {"done": True}, "OPP-186G-W1")
        self.assertEqual(ing1_dup["status"], "DUPLICATE_IGNORED")

        # Ingest worker result 2 -> barrier satisfies
        ing2 = restarted_runtime.ingest_real_event("RESULT", "CODEX", "CORR-U2", {"done": True}, "OPP-186G-W2")
        self.assertEqual(ing2["status"], "INGESTED")
        self.assertIn("BARRIER-186G-U", ing2["satisfied_barriers"])

        # Step 4: Barrier synthesis
        res4 = restarted_runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res4["status"], "PROGRESS_MADE")
        self.assertEqual(res4["transition"]["action_type"], "SYNTHESIS")

        # Step 5: Independent task execution while Human & Money gates are parked
        res5 = restarted_runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res5["status"], "PROGRESS_MADE")
        self.assertEqual(res5["transition"]["action_type"], "LOCAL_DETERMINISTIC_EXECUTION")
        self.assertEqual(len(restarted_runtime._load_session().human_gates_encountered), 1)
        self.assertEqual(len(restarted_runtime._load_session().money_gates_encountered), 1)

        # Step 6: Safe transition to IDLE_EXPECTED & Morning Report generation
        res6 = restarted_runtime.execute_session_step(deterministic_resolver=resolver, job_executor=executor)
        self.assertEqual(res6["status"], "IDLE_EXPECTED")
        self.assertIsNotNone(res6.get("morning_report"))
        self.assertEqual(res6["morning_report"]["useful_tasks_completed_count"], 4)
        self.assertEqual(res6["morning_report"]["autonomous_spend_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
