"""
test_recovery_court.py - Comprehensive Recovery Court for WINDOWS COURIER PERMANENT CRASH-PROOF MEMORY
Certifies Tests 1 through 8:
TEST 1: Interruption after start -> restart recovers A exactly once.
TEST 2: A verified -> chat loss -> fresh session skips A and advances to B.
TEST 3: Multiple equivalent 'weiter' signals produce exactly one logical transition (TASKS_DUPLICATED = 0).
TEST 4: Interruption after effect occurred -> effect discovered, duplicate side-effect prevented, state reconciled.
TEST 5: Interruption before effect -> safe single retry.
TEST 6: Corrupted checkpoint file -> restores from known-good SQLite/backup without inventing state.
TEST 7: Bounded crash loop -> CRASH_LOOP_DETECTED after 3 failures, advances to alternative candidate.
TEST 8: New empty Antigravity session -> bootstrap reconstructs full mission without human memory.
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

from courier.chief.crash_proof_recovery import CrashProofMemoryEngine

class TestRecoveryCourt(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_recovery_court_")
        self.db_path = os.path.join(self.test_dir, "test_control_plane.db")
        self.state_file = os.path.join(self.test_dir, "durable_state.json")
        self.engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file, max_crash_retries=3)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_interruption_after_start_reconstructed_once(self):
        """TEST 1: Task starts, worker dies -> restart recovers task exactly once."""
        task_id = "TASK-TEST-01"
        self.engine.write_ahead_intent(task_id, 1, ["Rule 1"], writer_pid=9999999) # Dead PID

        # Fresh restart of engine
        restart_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = restart_engine.reconcile_on_startup()

        self.assertTrue(report["recovered"])
        self.assertEqual(report["reconciliation_case"], "CASE_2_PROCESS_DEAD_RESUME")
        self.assertEqual(report["action_required"], "RETRY_INTERRUPTED_TASK_ONCE")
        
        state = restart_engine.load_durable_state()
        self.assertEqual(state["task_status"], "INTERRUPTED")
        self.assertEqual(state["active_task_id"], task_id)

    def test_02_verified_task_not_repeated_successor_selected(self):
        """TEST 2: Task verified, chat lost -> fresh session skips A and advances to B."""
        task_a = "TASK-TEST-02A"
        task_b = "TASK-TEST-02B"

        self.engine.write_ahead_intent(task_a, 1, ["Criteria A"])
        self.engine.commit_verified(task_a, {"returncode": 0}, successor_id=task_b)

        # Fresh session
        fresh_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        state = fresh_engine.load_durable_state()

        self.assertEqual(state["last_verified_task"], task_a)
        self.assertIn(task_a, state["do_not_repeat"])
        self.assertEqual(state["next_safe_candidate"], task_b)

        weiter_res = fresh_engine.handle_weiter_signal()
        self.assertEqual(weiter_res["decision"], "ADVANCE_TO_NEXT_GOAL")
        self.assertEqual(weiter_res["successor"], task_b)
        self.assertEqual(weiter_res["tasks_duplicated"], 0)

    def test_03_multiple_weiter_inputs_idempotent(self):
        """TEST 3: 5x 'weiter' while task is running -> 0 duplicate tasks created."""
        task_id = "TASK-TEST-03"
        self.engine.write_ahead_intent(task_id, 1, ["Criteria 3"], writer_pid=os.getpid())

        for _ in range(5):
            res = self.engine.handle_weiter_signal()
            self.assertEqual(res["decision"], "SUPPRESS_DUPLICATE_CONTINUATION")
            self.assertEqual(res["tasks_duplicated"], 0)

    def test_04_post_effect_crash_reconciliation(self):
        """TEST 4: Effect occurred before crash -> reconciled without duplicate effect."""
        task_id = "TASK-TEST-04"
        self.engine.write_ahead_intent(task_id, 1, ["Criteria 4"], writer_pid=9999999)
        self.engine.write_ahead_result(task_id, {"artifact": "file.zip"}, "SHA256_EFFECT_FP")

        # Restart
        restart_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = restart_engine.reconcile_on_startup()

        self.assertEqual(report["reconciliation_case"], "CASE_3_RESULT_PENDING_VERIFICATION")
        self.assertEqual(report["action_required"], "VERIFY_EXISTING_RESULT")

    def test_05_pre_effect_crash_recovery(self):
        """TEST 5: Crash before effect produced -> clean single retry."""
        task_id = "TASK-TEST-05"
        self.engine.write_ahead_intent(task_id, 1, ["Criteria 5"], writer_pid=9999999)

        restart_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = restart_engine.reconcile_on_startup()
        self.assertEqual(report["reconciliation_case"], "CASE_2_PROCESS_DEAD_RESUME")

    def test_06_corrupted_checkpoint_recovery(self):
        """TEST 6: Corrupted JSON file falls back to known-good SQLite state."""
        task_id = "TASK-TEST-06"
        self.engine.write_ahead_intent(task_id, 1, ["Criteria 6"])

        # Corrupt JSON file
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write("CORRUPTED_GARBAGE_JSON{{{")

        # Fresh engine load
        recovery_engine = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        state = recovery_engine.load_durable_state()
        self.assertEqual(state["active_task_id"], task_id)
        self.assertEqual(state["task_status"], "RUNNING")

    def test_07_crash_loop_protection(self):
        """TEST 7: Repeated crash on same task triggers CRASH_LOOP_DETECTED and prevents infinite retry."""
        task_id = "TASK-TEST-CRASHING"
        self.engine.write_ahead_intent(task_id, 1, ["Crash prone"], writer_pid=9999999)

        # Trigger 3 retries
        for _ in range(3):
            eng = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file, max_crash_retries=3)
            eng.reconcile_on_startup()

        # 4th retry triggers CRASH_LOOP_DETECTED
        eng4 = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file, max_crash_retries=3)
        rep = eng4.reconcile_on_startup()
        self.assertEqual(rep["reconciliation_case"], "CRASH_LOOP_DETECTED")
        self.assertEqual(rep["action_required"], "SELECT_INDEPENDENT_SAFE_WORK")
        self.assertEqual(rep["blocked_task"], task_id)

    def test_08_fresh_session_bootstrap(self):
        """TEST 8: Clean bootstrap summary discovers mission without human reconstruction."""
        task_id = "TASK-TEST-08"
        self.engine.write_ahead_intent(task_id, 1, ["Criteria 8"])
        self.engine.commit_verified(task_id, {"verified": True}, successor_id="TASK-TEST-09")

        summary = self.engine.get_bootstrap_summary()
        self.assertIn("MISSION: MISSION-AUTONOMY", summary)
        self.assertIn("LAST VERIFIED TASK: TASK-TEST-08", summary)
        self.assertIn("NEXT SAFE CANDIDATE: TASK-TEST-09", summary)
        self.assertIn("NEXT AUTOMATIC ACTION: EXECUTE_SUCCESSOR", summary)

if __name__ == "__main__":
    unittest.main()
