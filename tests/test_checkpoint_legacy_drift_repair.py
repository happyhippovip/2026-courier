"""
test_checkpoint_legacy_drift_repair.py - Stage 1 Targeted Tests for Authoritative State Drift Repair
Verifies:
A) Verified checkpoint generation advances -> legacy compatibility generation mirrors it.
B) Task advances -> legacy LAST_VERIFIED_TASK mirrors verified task.
C) Unverified/failed task -> legacy state MUST NOT advance.
D) Restart/readback -> authoritative tuple and compatibility keys agree.
"""
import os
import sys
import unittest
import tempfile
import shutil
import json

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane


class TestCheckpointLegacyDriftRepair(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="stage1_ckpt_")
        self.db_path = os.path.join(self.temp_dir, "test_control_plane.db")
        self.cp = ControlPlane(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_a_verified_checkpoint_generation_advances_mirrors_legacy_generation(self):
        """A) Verified checkpoint generation advances -> legacy compatibility generation mirrors it."""
        ckpt_payload = {
            "task_id": "TASK-WIN-101",
            "task_version": 1,
            "state_generation": 122,
            "result_fingerprint": "FP_TEST_A",
            "verification_evidence": "All checks passed cleanly",
            "verified_at": "2026-09-13T10:00:00+00:00"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_payload)

        # Query legacy compatibility key
        legacy_gen = self.cp.get_checkpoint("STATE_GENERATION")
        self.assertEqual(legacy_gen, "122")

        # Advance to generation 125
        ckpt_payload2 = {
            "task_id": "TASK-WIN-102",
            "task_version": 1,
            "state_generation": 125,
            "result_fingerprint": "FP_TEST_A2",
            "verification_evidence": "All checks passed cleanly v2",
            "verified_at": "2026-09-13T10:01:00+00:00"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_payload2)
        self.assertEqual(self.cp.get_checkpoint("STATE_GENERATION"), "125")

    def test_b_task_advances_mirrors_legacy_task(self):
        """B) Task advances -> legacy LAST_VERIFIED_TASK mirrors verified task."""
        ckpt_payload = {
            "task_id": "TASK-WIN-200",
            "task_version": 1,
            "state_generation": 130,
            "result_fingerprint": "FP_TEST_B",
            "verification_evidence": "Passed verification",
            "verified_at": "2026-09-13T10:05:00+00:00"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_payload)

        legacy_task = self.cp.get_checkpoint("LAST_VERIFIED_TASK")
        self.assertEqual(legacy_task, "TASK-WIN-200")

    def test_c_unverified_or_failed_task_does_not_advance_legacy_state(self):
        """C) Unverified/failed task -> legacy state MUST NOT advance."""
        # Baseline valid checkpoint
        valid_ckpt = {
            "task_id": "TASK-WIN-300",
            "task_version": 1,
            "state_generation": 140,
            "result_fingerprint": "FP_TEST_C_VALID",
            "verification_evidence": "Initial valid evidence",
            "verified_at": "2026-09-13T10:10:00+00:00"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", valid_ckpt)
        self.assertEqual(self.cp.get_checkpoint("STATE_GENERATION"), "140")
        self.assertEqual(self.cp.get_checkpoint("LAST_VERIFIED_TASK"), "TASK-WIN-300")

        # Candidate missing required fields (e.g. unverified candidate or failed exit code only)
        invalid_candidate = {
            "task_id": "TASK-WIN-9999",
            "state_generation": 999  # Attempting to spoof generation without 6-tuple evidence
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", invalid_candidate)

        # Verify neither authoritative nor legacy keys advanced
        auth_rec = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(auth_rec["task_id"], "TASK-WIN-300")
        self.assertEqual(auth_rec["state_generation"], 140)
        self.assertEqual(self.cp.get_checkpoint("STATE_GENERATION"), "140")
        self.assertEqual(self.cp.get_checkpoint("LAST_VERIFIED_TASK"), "TASK-WIN-300")

    def test_d_restart_and_readback_agreement(self):
        """D) Restart/readback -> authoritative tuple and compatibility keys agree."""
        ckpt_payload = {
            "task_id": "TASK-WIN-400",
            "task_version": 1,
            "state_generation": 150,
            "result_fingerprint": "FP_TEST_D",
            "verification_evidence": "Restart proof evidence",
            "verified_at": "2026-09-13T10:15:00+00:00"
        }
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", ckpt_payload)

        # Reopen brand new ControlPlane instance simulating fresh process restart
        fresh_cp = ControlPlane(db_path=self.db_path)
        auth_rec = fresh_cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(auth_rec["task_id"], "TASK-WIN-400")
        self.assertEqual(auth_rec["state_generation"], 150)

        # Both legacy keys must exactly agree with authoritative tuple
        self.assertEqual(fresh_cp.get_checkpoint("STATE_GENERATION"), "150")
        self.assertEqual(fresh_cp.get_checkpoint("LAST_VERIFIED_TASK"), "TASK-WIN-400")


if __name__ == "__main__":
    unittest.main()
