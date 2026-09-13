"""
test_emergency_autonomy_court.py - Comprehensive Emergency Autonomy Court for WINDOWS COURIER
Explicitly validates:
- 100x weiter adversarial court: 100 raw weiter signals -> at most 1 logical continuation, 99 suppressed.
- Court A: Duplicate continuation storm -> <= 1 logical continuation.
- Court B: Duplicate batch request -> exactly one logical batch.
- Court C: Concurrent duplicate batch requests -> atomic winner.
- Court D: Verified task replay -> task not executed again.
- Court E: Writer collision -> single writer owns conflicting scope.
- Court F: Crash before effect -> clean safe recovery.
- Court G: Crash after effect, before checkpoint -> effect discovered, no duplicate effect.
- Court H: Stale lease -> clean recovery.
- Court I: Fresh session -> loads durable state from disk without chat history.
- Court J: No weiter -> automatic succession A -> B -> C without human continuation.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
import threading

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.batch_guard import BatchGuardManager
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone

class TestEmergencyAutonomyCourt(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="emergency_court_")
        self.db_path = os.path.join(self.test_dir, "test_control_plane.db")
        self.state_file = os.path.join(self.test_dir, "durable_state.json")
        self.cp = ControlPlane(db_path=self.db_path)
        self.batch_guard = BatchGuardManager(db_path=self.db_path)
        self.mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        self.engine = FinishFirstContinuationEngine(
            workspace_root=self.test_dir,
            cp=self.cp,
            batch_guard=self.batch_guard
        )

        self.pm_dir = os.path.join(self.test_dir, "project-memory", "data")
        os.makedirs(self.pm_dir, exist_ok=True)
        self.backlog_path = os.path.join(self.pm_dir, "safe_backlog.json")
        self.sample_tasks = [
            {
                "task_id": f"TASK-TEST-EMERG-{i}",
                "title": f"Emergency verified capability task {i}",
                "goal_id": "GOAL-03",
                "priority": 1.0 - (i * 0.05),
                "status": "READY",
                "conflict_scope": f"SCOPE_TEST_{i}",
                "expected_real_delta": "CAPABILITY_GAIN",
                "source_evidence": "courier/chief/control_plane.py",
                "script_path": "courier/tests/test_recovery_court.py",
                "source_gap": "GAP_AUTONOMY_RESILIENCE"
            }
            for i in range(1, 10)
        ]
        with open(self.backlog_path, "w", encoding="utf-8") as f:
            json.dump({"tasks": self.sample_tasks}, f, indent=2)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_100x_weiter_adversarial_court(self):
        is_dup, reason = self.engine.check_duplicate_continuation(
            continuation_generation=1,
            state_generation=1,
            last_verified_task="GENESIS",
            last_verified_fingerprint="FP_GENESIS"
        )
        self.assertFalse(is_dup)
        self.assertEqual(reason, "CONTINUATION_ACCEPTED")

        suppressed_count = 0
        for i in range(2, 101):
            is_dup, reason = self.engine.check_duplicate_continuation(
                continuation_generation=1,
                state_generation=1,
                last_verified_task="GENESIS",
                last_verified_fingerprint="FP_GENESIS"
            )
            if is_dup:
                suppressed_count += 1

        self.assertEqual(suppressed_count, 99)

    def test_02_court_a_duplicate_continuation_storm(self):
        results = []
        for i in range(10):
            res = self.engine.process_continuation(
                signal="weiter",
                continuation_generation=1,
                current_goal="GOAL-03"
            )
            results.append(res)

        first = results[0]
        self.assertIn(first["status"], ("CURRENT_WORK_VERIFIED_NEXT_REAL_TASK_RUNNING", "CLOSED_AND_VERIFIED"))
        
        for r in results[1:]:
            self.assertEqual(r["status"], "CONTINUATION_ALREADY_CONSUMED")
            self.assertTrue(r.get("duplicate_suppressed"))

    def test_03_court_b_duplicate_batch_request(self):
        key = "BATCH-KEY-IDEMPOTENT-001"
        claimed1, reason1, rec1 = self.batch_guard.claim_batch(
            idempotency_key=key,
            mission_id="MISSION-WIN",
            current_goal="GOAL-03",
            state_generation=1,
            source_continuation_generation=1
        )
        self.assertTrue(claimed1)
        self.assertIn(reason1, ("CLAIMED", "BATCH_CLAIMED"))

        claimed2, reason2, rec2 = self.batch_guard.claim_batch(
            idempotency_key=key,
            mission_id="MISSION-WIN",
            current_goal="GOAL-03",
            state_generation=1,
            source_continuation_generation=1
        )
        self.assertFalse(claimed2)
        self.assertIn(reason2, ("DUPLICATE_BATCH_IN_FLIGHT", "BATCH_ALREADY_EXISTS"))
        self.assertEqual(rec1["batch_id"], rec2["batch_id"])

    def test_04_court_c_concurrent_duplicate_batch_requests(self):
        key = "BATCH-KEY-CONCURRENT-001"
        winners = []

        def worker():
            bg = BatchGuardManager(db_path=self.db_path)
            claimed, _, _ = bg.claim_batch(
                idempotency_key=key,
                mission_id="MISSION-WIN",
                current_goal="GOAL-03",
                state_generation=1,
                source_continuation_generation=1
            )
            if claimed:
                winners.append(True)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(winners), 1)

    def test_05_court_d_verified_task_replay(self):
        task_id = "TASK-TEST-EMERG-1"
        self.cp.upsert_task(
            task_id=task_id,
            assignment_id=f"ASSIGN-{task_id}",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.COMPLETED,
            two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=True, blocker="NONE", next_step="DONE"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", {
            "task_id": task_id,
            "task_version": 1,
            "state_generation": 2,
            "result_fingerprint": "FP_TEST_1",
            "verified_at": "2026-09-13T00:00:00Z",
            "status": "VERIFIED"
        })

        do_not_repeat = {task_id}
        next_cand = self.engine.discover_next_real_gap(do_not_repeat, current_goal="GOAL-03")
        self.assertIsNotNone(next_cand)
        self.assertNotEqual(next_cand["task_id"], task_id)
        self.assertEqual(next_cand["task_id"], "TASK-TEST-EMERG-2")

    def test_06_court_e_writer_collision(self):
        scope = "DOMAIN_TEST_EXCLUSIVE"
        acquired1, msg1 = self.cp.acquire_lock(
            resource_id=scope,
            lane=Lane.WINDOWS_GOOGLE,
            host=Host.WINDOWS,
            lock_type="WRITE",
            ttl_seconds=60
        )
        self.assertTrue(acquired1)

        acquired2, msg2 = self.cp.acquire_lock(
            resource_id=scope,
            lane=Lane.MAC_GOOGLE,
            host=Host.MAC,
            lock_type="WRITE",
            ttl_seconds=60
        )
        self.assertFalse(acquired2)
        self.assertIn("SINGLE_WRITER_CONFLICT", msg2)

    def test_07_court_f_crash_before_effect(self):
        task_id = "TASK-TEST-PRE-EFFECT"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria F"], writer_pid=9999999)

        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = fresh_mem.reconcile_on_startup()
        self.assertEqual(report["reconciliation_case"], "CASE_2_PROCESS_DEAD_RESUME")
        self.assertEqual(report["action_required"], "RETRY_INTERRUPTED_TASK_ONCE")

    def test_08_court_g_crash_after_effect_pre_checkpoint(self):
        task_id = "TASK-TEST-POST-EFFECT"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria G"], writer_pid=9999999)
        self.mem.write_ahead_result(task_id, {"status": "SUCCESS"}, "FP_EFFECT_G")

        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = fresh_mem.reconcile_on_startup()
        self.assertEqual(report["reconciliation_case"], "CASE_3_RESULT_PENDING_VERIFICATION")
        self.assertEqual(report["action_required"], "VERIFY_EXISTING_RESULT")

    def test_09_court_h_stale_lease(self):
        self.cp.acquire_lock(
            resource_id="STALE_RESOURCE",
            lane=Lane.WINDOWS_GOOGLE,
            host=Host.WINDOWS,
            lock_type="WRITE",
            ttl_seconds=1
        )
        time.sleep(1.1)
        cleaned = self.cp.clean_expired_locks()
        self.assertEqual(cleaned, 1)
        self.assertEqual(len(self.cp.get_active_locks()), 0)

    def test_10_court_i_fresh_session_bootstrap(self):
        task_id = "TASK-TEST-BOOTSTRAP"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria I"])
        self.mem.commit_verified(task_id, {"verified": True}, successor_id="TASK-TEST-BOOTSTRAP-2")

        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        summary = fresh_mem.get_bootstrap_summary()
        self.assertIn("MISSION: MISSION-AUTONOMY", summary)
        self.assertIn(f"LAST VERIFIED TASK: {task_id}", summary)
        self.assertIn("NEXT SAFE CANDIDATE: TASK-TEST-BOOTSTRAP-2", summary)

    def test_11_court_j_automatic_succession_without_weiter(self):
        executed_tasks = []
        gen = 1
        for i in range(3):
            res = self.engine.process_continuation(
                signal="internal_auto_succession",
                continuation_generation=gen,
                current_goal="GOAL-03"
            )
            gen += 1
            self.assertEqual(res["status"], "CURRENT_WORK_VERIFIED_NEXT_REAL_TASK_RUNNING")
            executed_tasks.append(res["executed_task"])

        self.assertEqual(len(executed_tasks), 3)
        self.assertEqual(executed_tasks, ["TASK-TEST-EMERG-1", "TASK-TEST-EMERG-2", "TASK-TEST-EMERG-3"])

if __name__ == "__main__":
    unittest.main()
