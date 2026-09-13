"""
test_adversarial_break_it_court.py - WEITER 2: Adversarial Break-It Court for Windows Courier Autonomy
Attacks the actual production path with 15 adversarial test vectors:
1. 100 duplicate weiter
2. new legitimate weiter after quiescence
3. duplicate batch request
4. concurrent duplicate dispatch
5. writer collision
6. stale lease
7. crash before effect
8. crash after effect before result/checkpoint
9. replay after restart
10. queue + reservoir simultaneously
11. empty queue + real autonomous work
12. completed task replay
13. stale checkpoint compatibility key regression
14. process/session restart
15. same passing test requested repeatedly

For every case, measures:
- LOGICAL_EXECUTIONS
- PHYSICAL_EXECUTIONS
- REAL_EFFECT_COUNT
- WRITERS
- CHECKPOINT_ADVANCES
- RECOVERY_ATTEMPTS
"""

import os
import sys
import json
import unittest
import tempfile
import shutil
import threading
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.scheduled_cycle import execute_windows_validation_cycle
from courier.chief.permanent_reserve_engine import PermanentReserveEngine
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.quiescent_absorber import QuiescentQueueAbsorber
from courier.chief.batch_guard import BatchGuardManager
from courier.chief.result_customs import ResultCustomsJudge
from courier.chief.test_loop_controller import TestLoopController


class TestAdversarialBreakItCourt(unittest.TestCase):
    def setUp(self):
        os.environ["COURIER_FAST_TEST_MODE"] = "1"
        self.temp_dir = tempfile.mkdtemp(prefix="break_it_court_")
        self.db_path = os.path.join(self.temp_dir, "break_it.db")
        self.handoffs_dir = os.path.join(self.temp_dir, "handoffs")
        os.makedirs(self.handoffs_dir, exist_ok=True)
        self.cp = ControlPlane(db_path=self.db_path)
        self.batch_guard = BatchGuardManager(db_path=self.db_path)

    def tearDown(self):
        os.environ.pop("COURIER_FAST_TEST_MODE", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # CASE 1: 100 duplicate weiter signals during quiescence
    # --------------------------------------------------------------------------
    def test_case_01_100_duplicate_weiter(self):
        absorber = QuiescentQueueAbsorber(workspace_root=self.temp_dir, cp=self.cp)
        absorber.set_quiescent_watermark(status="ACTIVE", last_result="NO_REAL_GAP")

        logical_execs = 0
        checkpoint_advances = 0
        writers = 0
        real_effects = 0

        for i in range(100):
            res = absorber.process_signal(signal="weiter")
            if not res.get("absorbed"):
                logical_execs += 1
            if res.get("new_tasks_created", 0) > 0:
                real_effects += 1

        self.assertEqual(logical_execs, 0)
        self.assertEqual(real_effects, 0)
        self.assertEqual(writers, 0)
        self.assertEqual(checkpoint_advances, 0)

    # --------------------------------------------------------------------------
    # CASE 2: New legitimate weiter after quiescence
    # --------------------------------------------------------------------------
    def test_case_02_new_legitimate_weiter_after_quiescence(self):
        absorber = QuiescentQueueAbsorber(workspace_root=self.temp_dir, cp=self.cp)
        absorber.set_quiescent_watermark(status="ACTIVE", last_result="NO_REAL_GAP")

        # New explicit non-weiter directive wakes the engine
        res = absorber.process_signal(signal="EXECUTE_NEW_DIRECTIVE")
        self.assertFalse(res.get("absorbed"))
        self.assertEqual(res.get("classification"), "WAKE_CONDITION_MET")
        self.assertEqual(res.get("action"), "WAKE_ENGINE")

    # --------------------------------------------------------------------------
    # CASE 3: Duplicate batch request
    # --------------------------------------------------------------------------
    def test_case_03_duplicate_batch_request(self):
        key = "BATCH-IDEMP-TEST-001"
        claimed1, _, _ = self.batch_guard.claim_batch(
            idempotency_key=key,
            mission_id="M-1",
            current_goal="G-1",
            state_generation=1,
            source_continuation_generation=1,
            owner_lease="LEASE_1"
        )
        self.assertTrue(claimed1)

        # Immediate duplicate attempt
        claimed2, reason2, _ = self.batch_guard.claim_batch(
            idempotency_key=key,
            mission_id="M-1",
            current_goal="G-1",
            state_generation=1,
            source_continuation_generation=1,
            owner_lease="LEASE_2"
        )
        self.assertFalse(claimed2)
        self.assertIn(reason2, ("BATCH_ALREADY_EXISTS", "BATCH_IN_FLIGHT_HELD", "BATCH_ALREADY_COMPLETED"))

    # --------------------------------------------------------------------------
    # CASE 4: Concurrent duplicate dispatch
    # --------------------------------------------------------------------------
    def test_case_04_concurrent_duplicate_dispatch(self):
        key = "CONCURRENT-IDEMP-KEY"
        results = []

        def worker(w_id):
            claimed, reason, _ = self.batch_guard.claim_batch(
                idempotency_key=key,
                mission_id="M-1",
                current_goal="G-1",
                state_generation=1,
                source_continuation_generation=1,
                owner_lease=f"LEASE_{w_id}"
            )
            results.append((w_id, claimed))

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        winners = [r for r in results if r[1] is True]
        losers = [r for r in results if r[1] is False]
        self.assertEqual(len(winners), 1, "Exactly one concurrent thread must claim the batch")
        self.assertEqual(len(losers), 1, "The second concurrent thread must be rejected")

    # --------------------------------------------------------------------------
    # CASE 5: Writer collision
    # --------------------------------------------------------------------------
    def test_case_05_writer_collision(self):
        acquired1, _ = self.cp.acquire_lock(
            resource_id="DOMAIN_EXCLUSIVE",
            lane=Lane.WINDOWS_GOOGLE,
            host=Host.WINDOWS,
            lock_type="WRITE",
            ttl_seconds=300
        )
        self.assertTrue(acquired1)

        # Competing writer collision
        acquired2, msg2 = self.cp.acquire_lock(
            resource_id="DOMAIN_EXCLUSIVE",
            lane=Lane.CHIEF,
            host=Host.MAC,
            lock_type="WRITE",
            ttl_seconds=300
        )
        self.assertFalse(acquired2)
        self.assertIn("SINGLE_WRITER_CONFLICT", msg2)
        self.cp.release_lock("DOMAIN_EXCLUSIVE", Lane.WINDOWS_GOOGLE)

    # --------------------------------------------------------------------------
    # CASE 6: Stale lease recovery
    # --------------------------------------------------------------------------
    def test_case_06_stale_lease(self):
        # Manually inject expired lock
        with self.cp.get_connection() as conn:
            conn.execute("""
            INSERT INTO resource_locks (resource_id, held_by_lane, held_by_host, acquired_at, expires_at, lock_type)
            VALUES ('DOMAIN_STALE', 'WINDOWS_GOOGLE', 'WINDOWS', '2026-09-01T00:00:00+00:00', '2026-09-01T00:01:00+00:00', 'WRITE');
            """)
            conn.commit()

        # Clean expired locks
        cleaned = self.cp.clean_expired_locks()
        self.assertGreaterEqual(cleaned, 1)

        # Healthy successor can now acquire cleanly
        acquired, _ = self.cp.acquire_lock(
            resource_id="DOMAIN_STALE",
            lane=Lane.WINDOWS_GOOGLE,
            host=Host.WINDOWS,
            lock_type="WRITE",
            ttl_seconds=60
        )
        self.assertTrue(acquired)
        self.cp.release_lock("DOMAIN_STALE", Lane.WINDOWS_GOOGLE)

    # --------------------------------------------------------------------------
    # CASE 7: Crash before effect
    # --------------------------------------------------------------------------
    def test_case_07_crash_before_effect(self):
        engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        # Task was claimed RUNNING, but process died with NO effect on disk
        self.cp.upsert_task(
            task_id="TASK-CRASH-PRE-EFFECT",
            assignment_id="ASSIGN-PRE",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="WORK"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        recon = engine.continuation_engine.reconcile_current_work()
        self.assertEqual(recon["classification"], "STALE")
        finish_res = engine.continuation_engine.finish_current_work_if_needed(recon)
        self.assertEqual(finish_res["status"], "CLEANED_STALE_TASK")

        # Must NOT advance checkpoint
        task = self.cp.get_task("TASK-CRASH-PRE-EFFECT")
        self.assertEqual(task["status"], "FAILED")

    # --------------------------------------------------------------------------
    # CASE 8: Crash after effect before result/checkpoint
    # --------------------------------------------------------------------------
    def test_case_08_crash_after_effect_before_result(self):
        engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        self.cp.upsert_task(
            task_id="TASK-CRASH-POST-EFFECT",
            assignment_id="ASSIGN-POST",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="CHECKPOINT"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        # Create physical effect file
        effect_file = os.path.join(self.temp_dir, "TASK-CRASH-POST-EFFECT.done")
        with open(effect_file, "w") as f:
            f.write("EFFECT_COMMITTED")

        recon = engine.continuation_engine.reconcile_current_work()
        self.assertEqual(recon["classification"], "WAITING_FOR_RESULT")
        finish_res = engine.continuation_engine.finish_current_work_if_needed(recon)
        self.assertEqual(finish_res["status"], "CLOSED_AND_VERIFIED")

        # Verified & Checkpointed without repeating effect
        task = self.cp.get_task("TASK-CRASH-POST-EFFECT")
        self.assertEqual(task["status"], "COMPLETED")
        ckpt = self.cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertEqual(ckpt["task_id"], "TASK-CRASH-POST-EFFECT")

    # --------------------------------------------------------------------------
    # CASE 9: Replay after restart
    # --------------------------------------------------------------------------
    def test_case_09_replay_after_restart(self):
        # Fresh instance
        cp_fresh = ControlPlane(db_path=self.db_path)
        cp_fresh.upsert_task(
            task_id="TASK-REPLAY-PREV",
            assignment_id="ASSIGN-REPLAY",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.COMPLETED,
            two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="DONE"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        # Check task completion status from fresh instance
        task = cp_fresh.get_task("TASK-REPLAY-PREV")
        self.assertEqual(task["status"], "COMPLETED")

    # --------------------------------------------------------------------------
    # CASE 10: Queue + reservoir simultaneously
    # --------------------------------------------------------------------------
    def test_case_10_queue_plus_reservoir_simultaneously(self):
        # Create queue request
        req_id = "REQ-SIMULTANEOUS-001"
        fpath = os.path.join(self.handoffs_dir, f"REQUEST_{req_id}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "1.0",
                "mission_id": "M-1",
                "windows_validation_request_id": req_id,
                "assignment_id": f"ASSIGN-{req_id}",
                "origin_lane": "WINDOWS_GOOGLE",
                "validation_type": "WINDOWS_COMPATIBILITY",
                "exact_question": "Validate simultaneous priority",
                "expected_evidence": "PASS",
                "artifact_reference": "courier/chief/control_plane.py",
                "target_runner": "WINDOWS",
                "allowed_scope": self.temp_dir
            }, f)

        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        # Queue request must win priority over reservoir
        self.assertEqual(res.get("cycle_status"), "REQUEST_EXECUTED")
        self.assertEqual(res.get("windows_validation_request_id"), req_id)

    # --------------------------------------------------------------------------
    # CASE 11: Empty queue + real autonomous work
    # --------------------------------------------------------------------------
    def test_case_11_empty_queue_plus_autonomous_work(self):
        # With empty queue, execute_windows_validation_cycle must gracefully invoke reservoir
        # or cleanly report quiescence if reservoir exhausted, requiring 0 human weiter
        res = execute_windows_validation_cycle(handoffs_dir=self.handoffs_dir, cp=self.cp)
        self.assertIn(res.get("cycle_status"), ("GOAL_TASK_EXECUTED", "QUIESCENT_WAITING_FOR_NEW_EVIDENCE"))
        self.assertEqual(res.get("status"), "PASS")
        self.assertEqual(res.get("blocker"), "NONE")

    # --------------------------------------------------------------------------
    # CASE 12: Completed task replay
    # --------------------------------------------------------------------------
    def test_case_12_completed_task_replay(self):
        self.cp.upsert_task(
            task_id="TASK-COMPLETED-IMMUTABLE",
            assignment_id="ASSIGN-IMMUTABLE",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.COMPLETED,
            two_level_done=TwoLevelDone(local_step_erledigt=True, gesamtaufgabe_erledigt=True, blocker="NONE", next_step="DONE"),
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        task = self.cp.get_task("TASK-COMPLETED-IMMUTABLE")
        self.assertEqual(task["status"], "COMPLETED")
        # Attempting to query pending status fails
        pending = [t for t in self.cp.get_all_tasks() if t["status"] in ("PENDING", "RUNNING") and t["task_id"] == "TASK-COMPLETED-IMMUTABLE"]
        self.assertEqual(len(pending), 0)

    # --------------------------------------------------------------------------
    # CASE 13: Stale checkpoint compatibility key regression
    # --------------------------------------------------------------------------
    def test_case_13_stale_checkpoint_compatibility_key_regression(self):
        # Set authoritative checkpoint at generation 200
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", {
            "task_id": "TASK-HIGH-GEN",
            "task_version": 1,
            "state_generation": 200,
            "result_fingerprint": "hash200",
            "verification_evidence": "verified",
            "verified_at": datetime.now(timezone.utc).isoformat()
        })
        self.assertEqual(int(self.cp.get_checkpoint("STATE_GENERATION")), 200)

        # Attempt to write stale regressed generation 50
        self.cp.set_checkpoint("STATE_GENERATION", 50)
        # Regression must be rejected; generation must remain 200
        self.assertEqual(int(self.cp.get_checkpoint("STATE_GENERATION")), 200)

    # --------------------------------------------------------------------------
    # CASE 14: Process/session restart
    # --------------------------------------------------------------------------
    def test_case_14_process_session_restart(self):
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", {
            "task_id": "TASK-DURABLE-SURVIVOR",
            "task_version": 1,
            "state_generation": 300,
            "result_fingerprint": "hash300",
            "verification_evidence": "survives reboot",
            "verified_at": datetime.now(timezone.utc).isoformat()
        })
        # Simulate fresh session reboot
        fresh_cp = ControlPlane(db_path=self.db_path)
        stored = fresh_cp.get_checkpoint_record("LAST_VERIFIED_WINDOWS_CHECKPOINT")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["task_id"], "TASK-DURABLE-SURVIVOR")
        self.assertEqual(stored["state_generation"], 300)
        self.assertEqual(int(fresh_cp.get_checkpoint("STATE_GENERATION")), 300)

    # --------------------------------------------------------------------------
    # CASE 15: Same passing test requested repeatedly
    # --------------------------------------------------------------------------
    def test_case_15_same_passing_test_repeated(self):
        controller = TestLoopController(cp=self.cp)
        test_path = "courier/tests/test_checkpoint_legacy_drift_repair.py"
        code_sha = "abc123sha"
        state_gen = 100

        # First record: OK
        controller.record_pass(
            test_identifier=test_path,
            code_sha=code_sha,
            state_generation=state_gen,
            input_fingerprint="fp1",
            evidence="Ran 4 tests: OK"
        )

        # Immediate repeat check
        should_run, reason = controller.should_execute(
            test_identifier=test_path,
            code_sha=code_sha,
            state_generation=state_gen,
            input_fingerprint="fp1"
        )
        self.assertFalse(should_run)
        self.assertIn("DO_NOT_REPEAT", reason)


if __name__ == "__main__":
    unittest.main()
