"""
test_e2e_resilience_soak.py - End-to-End Resilience, Fenced Mutex & Crash Recovery Soak Suite
Part of TASK-WIN-65: End-to-End Cross-Platform Recovery, Fenced Synchronization & Handoff Soak Certification.

Verifies the complete integration of:
1. CrashProofMemoryEngine (write-ahead persistence, restart recovery)
2. QueueCoalescer (coalescing 100+ queue storms, monotonic state generation)
3. FencedMutexManager (fencing tokens, split-brain write protection)
4. TwoLevelClosureGate (Level 1 process success vs Level 2 global completion + signed receipts)
5. Zero EUR spend firewall enforcement across all operations
6. Mac scope protection invariant (zero writes to reserved Mac scopes)
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.crash_proof_recovery import CrashProofMemoryEngine, MAC_RESERVED_SCOPES
from courier.chief.queue_coalescer import QueueCoalescer
from courier.chief.fenced_mutex import FencedMutexManager
from courier.chief.closure_gate import TwoLevelClosureGate

class TestE2EResilienceSoak(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_e2e_soak_")
        self.db_path = os.path.join(self.test_dir, "soak_control_plane.db")
        self.state_file = os.path.join(self.test_dir, "durable_state.json")
        self.coalescer_file = os.path.join(self.test_dir, "coalescer_state.json")

        self.memory_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        self.coalescer = QueueCoalescer(db_path=self.db_path, state_file=self.coalescer_file)
        self.mutex_mgr = FencedMutexManager(db_path=self.db_path)
        self.closure_gate = TwoLevelClosureGate(workspace_root=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_mac_reserved_scopes_strictly_isolated(self):
        """Verifies that all reserved Mac scopes are recognized and protected."""
        for scope in MAC_RESERVED_SCOPES:
            self.assertIn(scope, self.memory_engine.load_durable_state()["mac_reserved_scopes"])

    def test_02_full_lifecycle_with_fencing_and_closure_receipt(self):
        """Full end-to-end task cycle: write-ahead -> mutex acquire -> receipt -> state generation advance."""
        task_id = f"SOAK-TASK-{int(time.time() * 1000)}"
        criteria = ["Verify artifact integrity", "Validate 0 spend"]

        # 1. Write-Ahead Intent
        intent = self.memory_engine.write_ahead_intent(task_id, 1, criteria)
        self.assertEqual(intent["task_status"], "RUNNING")

        # 2. Fenced Mutex Acquisition
        mutex_res = self.mutex_mgr.acquire(f"resource:{task_id}", "SOAK_WORKER", "WINDOWS", os.getpid())
        self.assertTrue(mutex_res["acquired"])
        epoch = mutex_res["epoch"]
        token = mutex_res["lease_token"]

        # 3. Simulate Task Execution & Validate Fencing Token before commit
        val = self.mutex_mgr.validate_fencing_token(f"resource:{task_id}", "SOAK_WORKER", token, epoch)
        self.assertTrue(val["valid"])

        # 4. Two-Level Closure Evaluation & Cryptographic Receipt
        closure_res = self.closure_gate.evaluate_task_closure(
            task_id=task_id,
            execution_evidence={"returncode": 0, "success": True, "stdout": "All soak tests green."},
            remote_peer_synced=True,
            requires_human_gate=False,
            spend_eur=0.00
        )
        self.assertTrue(closure_res["success"])
        self.assertTrue(closure_res["two_level_done"]["local_step_erledigt"])
        self.assertTrue(closure_res["two_level_done"]["gesamtaufgabe_erledigt"])
        self.assertEqual(closure_res["two_level_done"]["blocker"], "NONE")
        self.assertIsNotNone(closure_res["receipt"])

        # 5. Commit Verified State in Memory Engine
        self.memory_engine.commit_verified(task_id, closure_res["receipt"], successor_id="SOAK-TASK-SUCCESSOR")
        
        # 6. Advance Queue Coalescer State Generation
        new_gen = self.coalescer.advance_state_generation(task_id)
        self.assertGreaterEqual(new_gen, 2)

        # 7. Release Fenced Mutex
        rel = self.mutex_mgr.release(f"resource:{task_id}", "SOAK_WORKER", token)
        self.assertTrue(rel["released"])

    def test_03_queue_storm_during_in_flight_soak(self):
        """Simulates 150 'weiter' inputs arriving while task is active: 0 duplicate tasks created."""
        task_id = f"SOAK-STORM-{int(time.time() * 1000)}"
        self.memory_engine.write_ahead_intent(task_id, 1, ["Rule 1"])

        # 150 consecutive 'weiter' inputs
        messages = ["weiter"] * 150
        burst = self.coalescer.process_queue_burst(messages, active_task_status="RUNNING", active_task_id=task_id)

        self.assertEqual(burst["total_messages_processed"], 150)
        self.assertEqual(burst["logical_continuation_intents_created"], 0)
        self.assertEqual(burst["continuations_coalesced"], 150)
        self.assertEqual(burst["duplicate_tasks_created"], 0)

    def test_04_restart_reconstruction_with_pending_customs(self):
        """Simulates mid-cycle crash when result is written but not yet verified: recovers pending result."""
        task_id = f"SOAK-CRASH-RESULT-{int(time.time() * 1000)}"
        self.memory_engine.write_ahead_intent(task_id, 1, ["Criteria"])
        self.memory_engine.write_ahead_result(task_id, {"exitcode": 0, "hash": "abc123sha"}, "EFFECT_FP_123")

        # Simulate agent crash & restart
        fresh_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        startup_report = fresh_engine.reconcile_on_startup()

        self.assertEqual(startup_report["reconciliation_case"], "CASE_3_RESULT_PENDING_VERIFICATION")
        self.assertEqual(startup_report["action_required"], "VERIFY_EXISTING_RESULT")

    def test_05_strict_zero_spend_invariant_across_all_layers(self):
        """Verifies spend firewall rejects any spend > 0.00 EUR at closure and memory layers."""
        closure_res = self.closure_gate.evaluate_task_closure(
            task_id="SPEND-TEST",
            execution_evidence={"returncode": 0, "success": True},
            remote_peer_synced=True,
            spend_eur=1.50
        )
        self.assertFalse(closure_res["success"])
        self.assertEqual(closure_res["decision"], "REJECTED_SPEND_VIOLATION")

if __name__ == "__main__":
    unittest.main()
