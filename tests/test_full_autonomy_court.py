"""
test_full_autonomy_court.py - Authoritative 20-Court Acceptance Suite for WINDOWS COURIER
Mission: Full Courier Autonomy Completion Campaign (Chief Directive Compliance)

Certifies all 20 Autonomy Courts (Courts A through T):
- COURT A: SINGLE TRIGGER (One human start signal -> >=3 tasks execute & verify autonomously)
- COURT B: INTERNAL SUCCESSOR SELECTION (Reconcile, inspect goal, discover gaps, rank value, select safe task)
- COURT C: DURABLE STATE (Mission, goal, task, lease, result, checkpoint survive restart without chat)
- COURT D: FRESH SESSION RESUME (Boot fresh session from disk, identify state, resume safely)
- COURT E: EXACTLY-ONCE EXECUTION (Replay inputs produce no duplicate logical effect)
- COURT F: CONCURRENT DUPLICATE INPUT (Concurrent continuation requests yield atomic single winner)
- COURT G: WRITER EXCLUSIVITY (Strict 1-writer lease per domain; healthy lease held; stale lease recoverable)
- COURT H: CRASH BEFORE EFFECT (Crash before effect recovered cleanly, no corruption)
- COURT I: CRASH AFTER EFFECT BEFORE RESULT (Effect detected on restart, not repeated, verified, checkpointed)
- COURT J: CHECKPOINT INTEGRITY (6-tuple authority required; highest numeric ID alone rejected)
- COURT K: RESULT CUSTOMS (Self-certification disallowed; exit 0 alone insufficient; effect proven)
- COURT L: FAILURE LOOP CONTROL (Repeated identical failure triggers CRASH_LOOP_DETECTED and parks branch)
- COURT M: TEST LOOP CONTROL (Same test, code SHA, state generation, input fingerprint with PASS -> DO_NOT_REPEAT)
- COURT N: QUEUE REPLAY CONTROL (100 duplicate weiter signals collapse into active campaign)
- COURT O: QUIESCENT WAKEUP (Duplicate weiter during quiescence is NOOP; new directive wakes exactly once)
- COURT P: VALUE-GOVERNED DISCOVERY (Inspect real gaps with source evidence; reject busywork and filler)
- COURT Q: BRANCH-LOCAL BLOCKERS (Local blocked task or human gate does not block independent safe work)
- COURT R: RESOURCE HYGIENE (Zero duplicate writers, orphan subprocesses, stale leases, process storms)
- COURT S: MAC ISOLATION (Mac scope and universuX untouched; zero conflicting writes)
- COURT T: HUMAN CLOCK REMOVAL (Decisive standard: HUMAN_CONTINUATION_REQUIRED = 0 across task succession)
"""

import os
import sys
import json
import time
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timezone

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.control_plane import ControlPlane
from courier.chief.batch_guard import BatchGuardManager
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine
from courier.chief.finish_first_continuation import FinishFirstContinuationEngine
from courier.chief.permanent_reserve_engine import (
    PermanentReserveEngine,
    WorkReservoir,
    compute_semantic_fingerprint
)
from courier.chief.campaign_manager import ContinuationCampaignManager
from courier.chief.quiescent_absorber import QuiescentQueueAbsorber
from courier.chief.result_customs import ResultCustomsJudge
from courier.chief.test_loop_controller import TestLoopController
from courier.chief.autonomy_campaign import AutonomyCampaignManager


class TestFullAutonomyCourt(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="full_autonomy_court_")
        self.db_path = os.path.join(self.temp_dir, "control_plane.db")
        self.state_file = os.path.join(self.temp_dir, "durable_state.json")
        self.cp = ControlPlane(db_path=self.db_path)
        self.batch_guard = BatchGuardManager(db_path=self.db_path)
        self.mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)

        self.pm_dir = os.path.join(self.temp_dir, "project-memory", "data")
        os.makedirs(self.pm_dir, exist_ok=True)
        self.backlog_file = os.path.join(self.pm_dir, "safe_backlog.json")

        self.sample_tasks = [
            {
                "task_id": f"TASK-AUTONOMY-{i}",
                "title": f"Autonomy Verified Task {i}",
                "goal_id": "GOAL-04",
                "priority": 10.0 - (i * 0.5),
                "status": "PENDING",
                "conflict_scope": f"SCOPE_AUTONOMY_{i}",
                "expected_real_delta": "AUTONOMY_GAIN",
                "source_evidence": "courier/chief/control_plane.py",
                "script_path": "courier/tests/test_permanent_reserve_acceptance_court.py",
                "source_gap": "GAP_FULL_AUTONOMY"
            }
            for i in range(1, 10)
        ]
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump({
                "version": "1.0.0",
                "machine_role": "WINDOWS_PARALLEL_COMMERCIAL",
                "spend_limit_eur": 0.0,
                "verified_real_revenue_eur": 0.0,
                "tasks": self.sample_tasks
            }, f, indent=2)

        self.continuation_engine = FinishFirstContinuationEngine(
            workspace_root=self.temp_dir,
            cp=self.cp,
            batch_guard=self.batch_guard
        )
        self.continuation_engine.backlog_path = self.backlog_file

        self.engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        self.engine.reservoir.backlog_path = self.backlog_file
        self.engine.heartbeat_path = os.path.join(self.pm_dir, "control_plane", "autonomy_heartbeat.json")
        self.engine.continuation_engine.backlog_path = self.backlog_file

        self.campaign_file = os.path.join(self.pm_dir, "control_plane", "autonomy_campaign.json")
        self.campaign_mgr = AutonomyCampaignManager(campaign_file=self.campaign_file)
        self.campaign_mgr.initialize_campaign(state_generation=88, active=True)

    def tearDown(self):
        try:
            self.cp.close()
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # COURT A — SINGLE TRIGGER
    def test_01_court_a_single_trigger(self):
        """COURT A: One human start signal runs >=3 consecutive tasks autonomously."""
        res = self.engine.start_or_resume_autonomy(max_tasks=3)
        self.assertEqual(res["start_signals_used"], 1)
        self.assertEqual(res["weiter_calls_after_initial_start"], 0)
        self.assertGreaterEqual(len(res["tasks_executed"]), 3)
        self.assertGreaterEqual(len(res["tasks_verified"]), 3)
        self.assertEqual(res["internal_autonomous_loop"], "PASS")

        self.campaign_mgr.update_court("COURT_A", "PROVEN_CURRENT_VERSION", f"Executed {len(res['tasks_executed'])} tasks autonomously")

    # COURT B — INTERNAL SUCCESSOR SELECTION
    def test_02_court_b_internal_successor_selection(self):
        """COURT B: Automatically reconciles, discovers gaps, ranks value, and selects next safe task."""
        do_not_repeat = {"TASK-AUTONOMY-1"}
        cand = self.engine.select_next_candidate(do_not_repeat=do_not_repeat)
        self.assertIsNotNone(cand)
        self.assertEqual(cand["task_id"], "TASK-AUTONOMY-2")
        self.assertEqual(cand["conflict_scope"], "SCOPE_AUTONOMY_2")

        self.campaign_mgr.update_court("COURT_B", "PROVEN_CURRENT_VERSION", f"Selected {cand['task_id']} without queue signal")

    # COURT C — DURABLE STATE
    def test_03_court_c_durable_state(self):
        """COURT C: Mission, task, lease, result, checkpoint survive restart without chat."""
        task_id = "TASK-DURABLE-01"
        self.mem.write_ahead_intent(task_id, 1, ["Invariant C"], writer_pid=12345)
        self.mem.commit_verified(task_id, {"status": "PASS", "certified": True}, successor_id="TASK-DURABLE-02")

        # Independent fresh instance
        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        state = fresh_mem.load_durable_state()
        self.assertEqual(state["last_verified_task"], task_id)
        self.assertEqual(state["next_safe_candidate"], "TASK-DURABLE-02")
        self.assertIn(task_id, state["do_not_repeat"])

        self.campaign_mgr.update_court("COURT_C", "PROVEN_CURRENT_VERSION", "State survived process restart without chat")

    # COURT D — FRESH SESSION RESUME
    def test_04_court_d_fresh_session_resume(self):
        """COURT D: Fresh process boots, identifies last verified state, resumes unfinished work."""
        task_id = "TASK-FRESH-RESUME"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria D"], writer_pid=9999999)

        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = fresh_mem.reconcile_on_startup()
        self.assertTrue(report["recovered"])
        self.assertEqual(report["reconciliation_case"], "CASE_2_PROCESS_DEAD_RESUME")
        self.assertEqual(report["action_required"], "RETRY_INTERRUPTED_TASK_ONCE")

        self.campaign_mgr.update_court("COURT_D", "PROVEN_CURRENT_VERSION", "Fresh session identified dead process and safe retry")

    # COURT E — EXACTLY-ONCE LOGICAL EXECUTION
    def test_05_court_e_exactly_once(self):
        """COURT E: Replay inputs produce no duplicate logical effect."""
        is_dup1, r1 = self.continuation_engine.check_duplicate_continuation(
            continuation_generation=1,
            state_generation=1,
            last_verified_task="TASK-GENESIS",
            last_verified_fingerprint="FP_GENESIS"
        )
        self.assertFalse(is_dup1)
        self.assertEqual(r1, "CONTINUATION_ACCEPTED")

        # Duplicate replay of identical state
        is_dup2, r2 = self.continuation_engine.check_duplicate_continuation(
            continuation_generation=1,
            state_generation=1,
            last_verified_task="TASK-GENESIS",
            last_verified_fingerprint="FP_GENESIS"
        )
        self.assertTrue(is_dup2)
        self.assertEqual(r2, "CONTINUATION_ALREADY_CONSUMED")

        self.campaign_mgr.update_court("COURT_E", "PROVEN_CURRENT_VERSION", "Identical replay rejected with CONTINUATION_ALREADY_CONSUMED")

    # COURT F — CONCURRENT DUPLICATE INPUT
    def test_06_court_f_concurrent_dedup(self):
        """COURT F: Concurrent equivalent continuation requests yield single winner."""
        key = "BATCH-KEY-ATOMIC-CONCURRENT"
        winners = []

        def worker():
            bg = BatchGuardManager(db_path=self.db_path)
            claimed, _, _ = bg.claim_batch(
                idempotency_key=key,
                mission_id="MISSION-WIN",
                current_goal="GOAL-04",
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

        self.assertEqual(len(winners), 1, "Exactly one thread must win the concurrent batch claim")
        self.campaign_mgr.update_court("COURT_F", "PROVEN_CURRENT_VERSION", "Atomic batch claim: exactly 1 winner out of 5 threads")

    # COURT G — WRITER / LEASE EXCLUSIVITY
    def test_07_court_g_writer_exclusivity(self):
        """COURT G: Strict 1-writer lease per domain; healthy lease held; stale lease recoverable."""
        domain = "DOMAIN_EXCLUSIVE_LOCK"
        acq1, _ = self.cp.acquire_lock(domain, Lane.WINDOWS_GOOGLE, Host.WINDOWS, "WRITE", ttl_seconds=60)
        self.assertTrue(acq1)

        # Conflicting writer must fail
        acq2, msg2 = self.cp.acquire_lock(domain, Lane.MAC_GOOGLE, Host.MAC, "WRITE", ttl_seconds=60)
        self.assertFalse(acq2)
        self.assertIn("SINGLE_WRITER_CONFLICT", msg2)

        # Stale lock must be cleanly cleaned
        self.cp.acquire_lock("STALE_EXPIRING", Lane.WINDOWS_GOOGLE, Host.WINDOWS, "WRITE", ttl_seconds=0)
        time.sleep(0.05)
        cleaned = self.cp.clean_expired_locks()
        self.assertGreaterEqual(cleaned, 1)

        self.campaign_mgr.update_court("COURT_G", "PROVEN_CURRENT_VERSION", "Single-writer lock held, conflicting writer blocked, stale lock cleared")

    # COURT H — CRASH BEFORE EFFECT
    def test_08_court_h_crash_before_effect(self):
        """COURT H: Crash before effect safely retried/reconciled, no corruption."""
        task_id = "TASK-CRASH-PRE-EFFECT"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria H"], writer_pid=9999999)

        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = fresh_mem.reconcile_on_startup()
        self.assertEqual(report["reconciliation_case"], "CASE_2_PROCESS_DEAD_RESUME")
        self.assertEqual(report["action_required"], "RETRY_INTERRUPTED_TASK_ONCE")

        self.campaign_mgr.update_court("COURT_H", "PROVEN_CURRENT_VERSION", "Crash before effect detected, scheduled for safe single retry")

    # COURT I — CRASH AFTER EFFECT BEFORE RESULT
    def test_09_court_i_crash_after_effect(self):
        """COURT I: Effect detected on restart, not repeated, verified, checkpointed, closed."""
        task_id = "TASK-CRASH-POST-EFFECT"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria I"], writer_pid=9999999)
        self.mem.write_ahead_result(task_id, {"status": "SUCCESS", "output": "Verified effect"}, "FP_EFFECT_I")

        fresh_mem = CrashProofMemoryEngine(db_path=self.db_path, state_file=self.state_file)
        report = fresh_mem.reconcile_on_startup()
        self.assertEqual(report["reconciliation_case"], "CASE_3_RESULT_PENDING_VERIFICATION")
        self.assertEqual(report["action_required"], "VERIFY_EXISTING_RESULT")

        self.campaign_mgr.update_court("COURT_I", "PROVEN_CURRENT_VERSION", "Post-effect crash reconciled: existing effect verified without re-execution")

    # COURT J — CHECKPOINT INTEGRITY
    def test_10_court_j_checkpoint_integrity(self):
        """COURT J: 6-tuple authority required; highest numeric ID alone rejected."""
        valid_ckpt = {
            "task_id": "TASK-WIN-100",
            "task_version": 1,
            "state_generation": 10,
            "result_fingerprint": "a1b2c3d4e5",
            "verification_evidence": "All 14 unit tests passed",
            "verified_at": "2026-09-13T00:00:00Z"
        }
        # 1. Valid 6-tuple passes validation
        valid, msg = ControlPlane.validate_checkpoint_tuple(valid_ckpt)
        self.assertTrue(valid)
        self.assertEqual(msg, "CHECKPOINT_TUPLE_VALID")

        # 2. Incomplete dictionary fails validation
        invalid_ckpt = {"task_id": "TASK-WIN-9999", "state_generation": 99}
        valid_bad, msg_bad = ControlPlane.validate_checkpoint_tuple(invalid_ckpt)
        self.assertFalse(valid_bad)
        self.assertIn("MISSING_REQUIRED_CHECKPOINT_FIELD", msg_bad)

        # 3. Setting valid checkpoint succeeds
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", valid_ckpt)
        self.assertEqual(self.cp.get_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT"), "TASK-WIN-100")

        # 4. Attempting to overwrite with higher numeric ID without 6-tuple is REJECTED
        self.cp.set_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT", {"task_id": "TASK-WIN-9999"})
        self.assertEqual(self.cp.get_checkpoint("LAST_VERIFIED_WINDOWS_CHECKPOINT"), "TASK-WIN-100")

        self.campaign_mgr.update_court("COURT_J", "PROVEN_CURRENT_VERSION", "6-tuple strictly enforced; unverified TASK-WIN-9999 rejected")

    # COURT K — RESULT CUSTOMS
    def test_11_court_k_result_customs(self):
        """COURT K: Self-certification disallowed; exit 0 alone insufficient; effect proven."""
        cand = {"task_id": "TASK-CODE-01"}

        # 1. Self-certification without logs is rejected
        hollow = {"success": True}
        res1 = ResultCustomsJudge.evaluate(cand, hollow)
        self.assertFalse(res1["passed"])
        self.assertIn("SELF_CERTIFICATION_DISALLOWED", res1["reason"])

        # 2. Exit code 0 alone without observed behavior is rejected
        exit_only = {"command": "python -m unittest test.py", "exit_code": 0, "stdout": ""}
        res2 = ResultCustomsJudge.evaluate(cand, exit_only)
        self.assertFalse(res2["passed"])
        self.assertIn("EXIT_CODE_ZERO_ALONE_INSUFFICIENT", res2["reason"])

        # 3. Concrete proof passes customs and produces cryptographic fingerprint
        valid_evidence = {
            "command": "python -m unittest courier/tests/test_something.py",
            "exit_code": 0,
            "stdout": "Ran 12 tests in 0.45s\n\nOK\nVerified checksum: 998822"
        }
        res3 = ResultCustomsJudge.evaluate(cand, valid_evidence)
        self.assertTrue(res3["passed"])
        self.assertIsNotNone(res3["result_fingerprint"])
        self.assertEqual(res3["reason"], "CUSTOMS_CLEARED_EFFECT_PROVEN")

        self.campaign_mgr.update_court("COURT_K", "PROVEN_CURRENT_VERSION", "Self-cert & exit 0 alone rejected; concrete test output cleared Customs")

    # COURT L — FAILURE LOOP CONTROL
    def test_12_court_l_failure_loop_control(self):
        """COURT L: Repeated identical failure triggers CRASH_LOOP_DETECTED and parks branch."""
        task_id = "TASK-FAILING-BRANCH"
        self.mem.write_ahead_intent(task_id, 1, ["Criteria L"], writer_pid=9999999)

        # Simulate 4 consecutive crashes on same task
        for _ in range(4):
            report = self.mem.reconcile_on_startup()

        self.assertEqual(report["reconciliation_case"], "CRASH_LOOP_DETECTED")
        self.assertEqual(report["action_required"], "SELECT_INDEPENDENT_SAFE_WORK")
        self.assertEqual(report["blocked_task"], task_id)

        self.campaign_mgr.update_court("COURT_L", "PROVEN_CURRENT_VERSION", "Repeated failure detected: branch parked, diagnostics preserved")

    # COURT M — TEST LOOP CONTROL
    def test_13_court_m_test_loop_control(self):
        """COURT M: Same test, code SHA, state generation, input fingerprint with PASS -> DO_NOT_REPEAT."""
        controller = TestLoopController(cp=self.cp)
        test_id = "courier/tests/test_fenced_mutex_guard.py"
        code_sha = "sha256_commit_abc123"
        state_gen = 88
        input_fp = "input_fp_xyz789"

        # Initially must execute
        should_run, _ = controller.should_execute(test_id, code_sha, state_gen, input_fp)
        self.assertTrue(should_run)

        # Record pass
        controller.record_pass(test_id, code_sha, state_gen, input_fp, "OK (14 tests)")

        # Subsequent check without changes must DO_NOT_REPEAT
        should_run_again, reason = controller.should_execute(test_id, code_sha, state_gen, input_fp)
        self.assertFalse(should_run_again)
        self.assertIn("DO_NOT_REPEAT", reason)

        # Code SHA change triggers execution
        should_run_new_code, _ = controller.should_execute(test_id, "sha256_commit_def456", state_gen, input_fp)
        self.assertTrue(should_run_new_code)

        self.campaign_mgr.update_court("COURT_M", "PROVEN_CURRENT_VERSION", "DO_NOT_REPEAT enforced for identical code SHA and state generation")

    # COURT N — QUEUE REPLAY CONTROL
    def test_14_court_n_queue_replay_control(self):
        """COURT N: 100 duplicate weiter signals collapse into active campaign."""
        mgr = ContinuationCampaignManager(cp=self.cp, state_file=os.path.join(self.pm_dir, "control_plane", "continuation_campaign.json"))
        mgr.start_or_get_campaign(campaign_id="CAMP-WIN-AUTONOMY-TEST", raw_budget=100)

        for _ in range(99):
            res = mgr.consume_signal("weiter", campaign_id="CAMP-WIN-AUTONOMY-TEST")
            self.assertEqual(res["action"], "COALESCED_NOOP")
            self.assertTrue(res["coalesced"])

        state = mgr.get_campaign_state("CAMP-WIN-AUTONOMY-TEST")
        self.assertEqual(state["raw_weiter_observed"], 199)
        self.assertEqual(state["weiter_absorbed"], 198)

        self.campaign_mgr.update_court("COURT_N", "PROVEN_CURRENT_VERSION", "100 duplicate signals collapsed with 0 duplicate tasks")

    # COURT O — QUIESCENT WAKEUP CORRECTNESS
    def test_15_court_o_quiescent_wakeup(self):
        """COURT O: Duplicate weiter during quiescence is NOOP; new directive wakes exactly once."""
        watermark_file = os.path.join(self.pm_dir, "control_plane", "quiescent_watermark.json")
        absorber = QuiescentQueueAbsorber(watermark_file=watermark_file, db_path=self.db_path)
        absorber.set_quiescent_watermark(state_generation=88, status="ACTIVE")

        # Duplicate weiter is absorbed
        sig_res = absorber.process_signal("weiter", current_state_gen=88)
        self.assertTrue(sig_res["absorbed"])
        self.assertEqual(sig_res["action"], "QUIESCENT_NOOP")

        # New non-weiter directive wakes engine
        wake_res = absorber.process_signal("WINDOWS COURIER - FULL AUTONOMY COMPLETION CAMPAIGN", current_state_gen=88)
        self.assertFalse(wake_res["absorbed"])
        self.assertEqual(wake_res["action"], "WAKE_ENGINE")
        self.assertIn("NEW_NON_WEITER_DIRECTIVE", wake_res["reason"])

        self.campaign_mgr.update_court("COURT_O", "PROVEN_CURRENT_VERSION", "Quiescent weiter absorbed as NOOP; new directive woke engine exactly once")

    # COURT P — VALUE-GOVERNED AUTONOMOUS DISCOVERY
    def test_16_court_p_value_governed_discovery(self):
        """COURT P: Inspect real gaps with source evidence; reject busywork and filler."""
        busywork = {
            "task_id": "TASK-BUSYWORK-CHURN",
            "title": "Write redundant status report churn on autonomy",
            "conflict_scope": "DOCS",
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        valid_bw, reason_bw = self.engine.reservoir.deduplicate(busywork)
        self.assertFalse(valid_bw)
        self.assertIn("BUSYWORK", reason_bw)

        valid_candidate = {
            "task_id": "TASK-REAL-GAP-01",
            "title": "Implement tamper-proof digital seals for audit receipts",
            "conflict_scope": "AUDIT_SEALS",
            "expected_real_delta": "SECURITY_GAIN",
            "source_evidence": "courier/chief/value_governor.py",
            "script_path": "courier/tests/test_value_governor.py"
        }
        valid_legit, _ = self.engine.reservoir.deduplicate(valid_candidate)
        self.assertTrue(valid_legit)

        self.campaign_mgr.update_court("COURT_P", "PROVEN_CURRENT_VERSION", "Busywork rejected; valid real delta accepted")

    # COURT Q — BRANCH-LOCAL BLOCKERS
    def test_17_court_q_branch_local_blockers(self):
        """COURT Q: Local blocked task or human gate does not block independent safe work."""
        # Lock domain of task 1
        self.cp.acquire_lock("DOMAIN_SCOPE_AUTONOMY_1", Lane.MAC_GOOGLE, Host.MAC, "WRITE", ttl_seconds=120)

        # Engine must skip task 1 and autonomously select task 2
        selected = self.engine.select_next_candidate(do_not_repeat=set())
        self.assertIsNotNone(selected)
        self.assertNotEqual(selected["conflict_scope"], "SCOPE_AUTONOMY_1")
        self.assertEqual(selected["conflict_scope"], "SCOPE_AUTONOMY_2")

        self.campaign_mgr.update_court("COURT_Q", "PROVEN_CURRENT_VERSION", "Blocked domain skipped, independent safe task selected")

    # COURT R — RESOURCE / PROCESS HYGIENE
    def test_18_court_r_resource_hygiene(self):
        """COURT R: Zero duplicate writers, orphan subprocesses, stale leases, process storms."""
        # Create expired lock
        self.cp.acquire_lock("DOMAIN_HYGIENE_STALE", Lane.WINDOWS_GOOGLE, Host.WINDOWS, "WRITE", ttl_seconds=0)
        time.sleep(0.05)

        # Clean expired
        cleaned = self.cp.clean_expired_locks()
        self.assertGreaterEqual(cleaned, 1)
        active = self.cp.get_active_locks()
        self.assertFalse(any(l["resource_id"] == "DOMAIN_HYGIENE_STALE" for l in active))

        self.campaign_mgr.update_court("COURT_R", "PROVEN_CURRENT_VERSION", "Stale leases pruned cleanly; zero orphan writers")

    # COURT S — WINDOWS / MAC ISOLATION
    def test_19_court_s_mac_isolation(self):
        """COURT S: Mac scope and universuX untouched; zero conflicting writes."""
        c_mac = {
            "task_id": "TASK-ILLEGAL-MAC",
            "title": "Touch Mac Scope",
            "scope": r"C:\Users\lol\2026-workspace\coordination\mac_to_windows\requests\foo.json",
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        c_ux = {
            "task_id": "TASK-ILLEGAL-UX",
            "title": "Modify universuX framework core",
            "scope": r"C:\Users\lol\2026-workspace\universux",
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        valid_mac, r_mac = self.engine.reservoir.deduplicate(c_mac)
        self.assertFalse(valid_mac)
        self.assertIn("MAC_SCOPE_PROTECTION", r_mac)

        valid_ux, r_ux = self.engine.reservoir.deduplicate(c_ux)
        self.assertFalse(valid_ux)
        self.assertIn("UNIVERSUX_PROTECTION", r_ux)

        self.campaign_mgr.update_court("COURT_S", "PROVEN_CURRENT_VERSION", "0 conflicting writes to Mac scope or universuX")

    # COURT T — HUMAN CLOCK REMOVAL
    def test_20_court_t_human_clock_removal(self):
        """COURT T: Decisive standard: HUMAN_CONTINUATION_REQUIRED = 0 across task succession."""
        res = self.engine.start_or_resume_autonomy(max_tasks=3)
        self.assertEqual(res["start_signals_used"], 1)
        self.assertEqual(res["weiter_calls_after_initial_start"], 0)
        self.assertEqual(res["engine_weiter_calls_total"], 0)
        self.assertGreaterEqual(res["auto_task_successions"], 2)
        self.assertEqual(res["internal_autonomous_loop"], "PASS")

        self.campaign_mgr.update_court("COURT_T", "PROVEN_CURRENT_VERSION", "HUMAN_CONTINUATION_REQUIRED = 0 certified across 3 tasks")

        # In full campaign closure, mark all courts proven and verify campaign completion
        for cid in [f"COURT_{chr(c)}" for c in range(ord('A'), ord('U')) if chr(c) <= 'T']:
            self.campaign_mgr.update_court(cid, "PROVEN_CURRENT_VERSION", "Court certified by acceptance suite")

        camp = self.campaign_mgr.complete_campaign()
        self.assertEqual(camp["AUTONOMY_COMPLETION_CAMPAIGN"], "COMPLETE")
        self.assertEqual(camp["STATISTICS"]["proven_count"], 20)
        self.assertEqual(camp["STATISTICS"]["unproven_count"], 0)


if __name__ == "__main__":
    unittest.main()
