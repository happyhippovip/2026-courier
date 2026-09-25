"""Deterministic test suite for Eight Bodyguards reserve worker pool."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = TESTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.run_bodyguards import (
    BodyguardPoolManager,
    generate_bodyguard_speech,
)


class EightBodyguardsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.manager = BodyguardPoolManager(self.repo)
        self.manager.initialize_pool(force_reset=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_01_all_eight_default_standby(self):
        """1. All 8 bodyguards initialize in STANDBY state with exact names."""
        bgs = self.manager.get_all_bodyguards()
        self.assertEqual(len(bgs), 8)
        expected_callsigns = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"]
        actual_callsigns = [b["callsign"] for b in bgs]
        self.assertEqual(actual_callsigns, expected_callsigns)
        for bg in bgs:
            self.assertEqual(bg["state"], "STANDBY")
            self.assertIsNone(bg["temporary_role"])
            self.assertEqual(bg["speech"], "Ready for reserve duty.")

    def test_02_standby_causes_zero_model_calls(self):
        """2. Standby bodyguards incur exactly 0 model calls and 0 cost."""
        bgs = self.manager.get_all_bodyguards()
        for bg in bgs:
            self.assertEqual(bg.get("model_calls_incurred"), 0)
            self.assertEqual(bg.get("progress"), 0.0)

    def test_03_assign_alpha_only_alpha_activated(self):
        """3. Assign Alpha -> only Alpha transitions to ASSIGNED / WORKING."""
        assigned = self.manager.assign_bodyguard(
            callsign="ALPHA",
            task_id="TASK-QA-001",
            workflow_id="WF-TEST-001",
            correlation_id="corr-test-001",
            temporary_role="QA_WORKER",
            required_capabilities=["test_runner", "deterministic_execution"],
        )
        self.assertEqual(assigned["callsign"], "ALPHA")
        self.assertEqual(assigned["state"], "ASSIGNED")
        self.assertEqual(assigned["temporary_role"], "QA_WORKER")
        self.assertIn("QA_WORKER", assigned["speech"])

    def test_04_bravo_remains_in_standby_when_alpha_assigned(self):
        """4. When Alpha is assigned, Bravo (and others) remain in STANDBY."""
        self.manager.assign_bodyguard(
            callsign="ALPHA",
            task_id="TASK-QA-001",
            workflow_id="WF-TEST-001",
            correlation_id="corr-test-001",
            temporary_role="QA_WORKER",
        )
        bgs = {b["callsign"]: b for b in self.manager.get_all_bodyguards()}
        self.assertEqual(bgs["ALPHA"]["state"], "ASSIGNED")
        self.assertEqual(bgs["BRAVO"]["state"], "STANDBY")
        self.assertEqual(bgs["CHARLIE"]["state"], "STANDBY")
        self.assertEqual(bgs["HOTEL"]["state"], "STANDBY")

    def test_05_completed_task_transitions_returning_to_standby(self):
        """5. Task completion transitions Bodyguard through RETURNING back to STANDBY."""
        self.manager.assign_bodyguard(
            callsign="ALPHA",
            task_id="TASK-DIAG-001",
            workflow_id="WF-TEST-001",
            correlation_id="corr-test-001",
            temporary_role="DIAGNOSTIC_WORKER",
        )
        self.manager.update_progress(
            callsign="ALPHA",
            progress=0.75,
            action="Diagnosing simulated memory anomaly",
        )
        working_state = {b["callsign"]: b for b in self.manager.get_all_bodyguards()}["ALPHA"]
        self.assertEqual(working_state["state"], "WORKING")
        self.assertEqual(working_state["progress"], 0.75)

        completed = self.manager.complete_task(
            callsign="ALPHA",
            result_file="TASK-DIAG-001-result.json",
        )
        self.assertEqual(completed["state"], "STANDBY")
        self.assertIsNone(completed["temporary_role"])
        self.assertEqual(completed["speech"], "Ready for reserve duty.")

    def test_06_missing_required_capability_triggers_capability_mismatch(self):
        """6. Missing required capability -> CAPABILITY_MISMATCH (no false capability claims!)."""
        mismatch = self.manager.assign_bodyguard(
            callsign="BRAVO",
            task_id="TASK-HARDWARE-001",
            workflow_id="WF-TEST-002",
            correlation_id="corr-test-002",
            temporary_role="TECHNICAL_WORKER",
            required_capabilities=["unsupported_hardware_quantum_accelerator", "local_filesystem"],
        )
        self.assertEqual(mismatch["state"], "CAPABILITY_MISMATCH")
        self.assertTrue(mismatch["blocked"])
        self.assertIn("unsupported", mismatch["last_action"])
        self.assertEqual(mismatch["speech"], "Required capability is unavailable. Flagging capability mismatch.")

    def test_07_no_specialist_replacement_claim_without_evidence(self):
        """7. Bodyguard roles are strictly temporary without replacing core specialist identity."""
        assigned = self.manager.assign_bodyguard(
            callsign="CHARLIE",
            task_id="TASK-VISUAL-001",
            workflow_id="WF-TEST-003",
            correlation_id="corr-test-003",
            temporary_role="VISUAL_IMPLEMENTATION",
            required_capabilities=["local_filesystem"],
        )
        self.assertEqual(assigned["name"], "BODYGUARD CHARLIE")
        self.assertEqual(assigned["role"], "RESERVE WORKER SLOT")
        self.assertEqual(assigned["temporary_role"], "VISUAL_IMPLEMENTATION")

    def test_08_no_duplicate_assignment_error_when_exhausted(self):
        """8. Trying to assign a specific busy bodyguard raises ValueError."""
        self.manager.assign_bodyguard(
            callsign="DELTA",
            task_id="TASK-1",
            workflow_id="WF-1",
            correlation_id="corr-1",
            temporary_role="TECHNICAL_WORKER",
        )
        with self.assertRaises(ValueError):
            self.manager.assign_bodyguard(
                callsign="DELTA",
                task_id="TASK-2",
                workflow_id="WF-2",
                correlation_id="corr-2",
                temporary_role="TECHNICAL_WORKER",
            )

    def test_09_workload_routing_selects_first_free_available_standby(self):
        """9. Workload routing assigns next available standby bodyguard when none specified."""
        first = self.manager.assign_bodyguard(
            callsign=None,
            task_id="TASK-AUTO-1",
            workflow_id="WF-AUTO",
            correlation_id="corr-auto",
            temporary_role="TECHNICAL_WORKER",
        )
        second = self.manager.assign_bodyguard(
            callsign=None,
            task_id="TASK-AUTO-2",
            workflow_id="WF-AUTO",
            correlation_id="corr-auto",
            temporary_role="TECHNICAL_WORKER",
        )
        self.assertEqual(first["callsign"], "ALPHA")
        self.assertEqual(second["callsign"], "BRAVO")
        available = self.manager.get_available_bodyguards()
        self.assertEqual(len(available), 6)

    def test_10_speech_bubbles_match_state_invariants(self):
        """10. Bodyguard speech generation produces exact deterministic text for all states."""
        self.assertEqual(generate_bodyguard_speech("STANDBY", "ALPHA"), "Ready for reserve duty.")
        self.assertEqual(generate_bodyguard_speech("ASSIGNED", "BRAVO", "QA_WORKER"), "Temporary role QA_WORKER received. Preparing task.")
        self.assertEqual(generate_bodyguard_speech("WORKING", "CHARLIE"), "I'm covering this task while the specialist is busy.")
        self.assertEqual(generate_bodyguard_speech("RETURNING", "DELTA"), "Result delivered to Courier. Returning to standby.")
        self.assertEqual(generate_bodyguard_speech("CAPABILITY_MISMATCH", "ECHO"), "Required capability is unavailable. Flagging capability mismatch.")


if __name__ == "__main__":
    unittest.main()
