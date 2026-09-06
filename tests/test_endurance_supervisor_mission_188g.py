#!/usr/bin/env python3
"""Mission 188G: Real Endurance Supervisor Test Suite."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_control_plane import AutonomyControlPlane
from scripts.chief_brain import ChiefBrain
from scripts.opportunity_queue import OpportunityQueue
from scripts.real_autonomy_runtime import RealAutonomyRuntime
from scripts.run_local_endurance_supervisor import LocalEnduranceSupervisor


class TestEnduranceSupervisorMission188G(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="endurance_188g_test_"))
        self.supervisor = LocalEnduranceSupervisor(
            repo_dir=self.test_dir,
            duration_hours=0.005,  # ~18 seconds
            session_id="session-188g-unit-test",
            heartbeat_interval_seconds=2.0,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pre_flight_safety_and_firewalls(self):
        self.assertEqual(self.supervisor.AUTONOMOUS_SPEND_LIMIT_EUR, 0.0)
        self.assertEqual(self.supervisor.PUBLICATION_AUTHORIZATION_INFERENCE, "DENY")
        snap = self.supervisor.runtime.control_plane.reconstruct_canonical_state()
        self.assertEqual(snap["autonomy_state"], "ACTIVE_DETERMINISTIC_FIRST")

    def test_02_heartbeat_and_zero_model_burn_while_idle(self):
        self.supervisor.start_mono = 100.0
        self.supervisor.deadline_mono = 200.0
        self.supervisor._write_heartbeat(status="IDLE_EXPECTED", action="IDLE")

        hb_file = self.test_dir / "events" / "autonomy-runtime" / "heartbeat.json"
        self.assertTrue(hb_file.is_file())
        hb = json.loads(hb_file.read_text(encoding="utf-8"))
        self.assertEqual(hb["status"], "IDLE_EXPECTED")
        self.assertEqual(hb["model_calls_during_idle"], 0)
        self.assertEqual(hb["autonomous_spend_eur"], 0.0)
        self.assertEqual(hb["publication_authorization"], "DENY")
        self.assertTrue(hb["human_gate_parked"])
        self.assertTrue(hb["money_gate_parked"])

    def test_03_deterministic_resolver_handles_tasks(self):
        can_res, out = self.supervisor._deterministic_resolver("OPP-CREATOR-AUDIT")
        self.assertTrue(can_res)
        self.assertEqual(out["status"], "PASS")

        can_res2, out2 = self.supervisor._deterministic_resolver("OPP-RESOURCE-AUDIT")
        self.assertTrue(can_res2)
        self.assertEqual(out2["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
