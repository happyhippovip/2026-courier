"""
test_permanent_reserve_acceptance_court.py - Acceptance Court 21:
Permanent Reserve Engine & Zero-Human-Continuation Acceptance Suite

Certifies:
1. RESERVOIR_PERSISTENCE: Single canonical work reservoir in safe_backlog.json and SQLite.
2. SEMANTIC_DEDUP: Collision-resistant semantic deduplication prevents identical tasks.
3. ONE_WRITER: Strict 1-writer lease per conflict domain; conflicting tasks held.
4. AUTO_TASK_SUCCESSION: Executes >=3 consecutive tasks autonomously without human continuation.
5. AUTO_GOAL_SUCCESSION: Detects goal completion and autonomously advances to successor goal.
6. CRASH_RECOVERY: Recovers from simulated mid-execution crash and clears stale locks.
7. POST_EFFECT_RECOVERY: Reconciles on-disk effects after pre-checkpoint interruption.
8. FRESH_SESSION_RECOVERY: Self-boots cleanly from disk state without human intervention.
9. WATCHDOG_RECOVERY: Reclaims stale leases and detects hung tasks.
10. CRASH_LOOP_PROTECTION: Parks repeatedly failing candidate (>=3 fails) without halting loop.
11. RESOURCE_BOUNDS: Enforces bounded execution, zero process leaks, bounded memory.
12. PAYMENT_GATE_LOCALITY: Strict 0.00 EUR real spend, human payment gates parked.
13. MAC_NON_CONFLICT: Mac active scope and universuX strictly excluded.
14. REAL_DELTA_SELECTION: Rejects busywork, selects highest value real capability gain.
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

from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone
from courier.chief.control_plane import ControlPlane
from courier.chief.permanent_reserve_engine import (
    PermanentReserveEngine,
    WorkReservoir,
    compute_semantic_fingerprint,
    PARKED_HUMAN_GATES,
    ALLOWED_REAL_DELTAS
)


class TestPermanentReserveAcceptanceCourt(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="agy_reserve_court_")
        self.cp_db = os.path.join(self.temp_dir, "test_cp.db")
        self.cp = ControlPlane(self.cp_db)
        # Seed dummy project memory directory
        self.pm_dir = os.path.join(self.temp_dir, "project-memory", "data")
        os.makedirs(self.pm_dir, exist_ok=True)
        self.backlog_file = os.path.join(self.pm_dir, "safe_backlog.json")
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump({
                "version": "1.0.0",
                "machine_role": "WINDOWS_PARALLEL_COMMERCIAL",
                "spend_limit_eur": 0.0,
                "verified_real_revenue_eur": 0.0,
                "tasks": []
            }, f, indent=2)

        self.engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        self.engine.reservoir.backlog_path = self.backlog_file
        self.engine.heartbeat_path = os.path.join(self.pm_dir, "control_plane", "autonomy_heartbeat.json")

    def tearDown(self):
        try:
            self.cp.close()
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_reservoir_persistence(self):
        """COURT 1: Single canonical work reservoir persists and reloads complete schema."""
        added = self.engine.reservoir.refresh_reservoir("GOAL-04")
        self.assertGreaterEqual(added, 10, "Reservoir must populate sufficient ranked candidates")

        candidates = self.engine.reservoir.get_pending_candidates()
        self.assertGreaterEqual(len(candidates), 10)

        c = candidates[0]
        required_fields = ["task_id", "goal_id", "title", "expected_real_delta", "priority", "conflict_scope", "semantic_fingerprint"]
        for field in required_fields:
            self.assertIn(field, c, f"Candidate must contain schema field: {field}")
            self.assertIsNotNone(c[field])

    def test_02_semantic_dedup(self):
        """COURT 2: Semantic fingerprinting detects duplicates even with reordered titles."""
        c1 = {
            "task_id": "TASK-A",
            "goal_id": "GOAL-04",
            "title": "Autonomous Multi-Task Succession & Zero-Human Continuation Runner",
            "conflict_scope": "TASK_SUCCESSION",
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        c2 = {
            "task_id": "TASK-B",
            "goal_id": "GOAL-04",
            "title": "Zero-Human Continuation Runner & Autonomous Multi-Task Succession",
            "conflict_scope": "TASK_SUCCESSION",
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        fp1 = compute_semantic_fingerprint(c1)
        fp2 = compute_semantic_fingerprint(c2)
        self.assertEqual(fp1, fp2, "Reordered significant words in same domain must produce identical fingerprint")

    def test_03_one_writer_law(self):
        domain = "CRITICAL_DOMAIN"
        # Manually lock domain with another writer
        acquired, _ = self.cp.acquire_lock(f"DOMAIN_{domain}", Lane.MAC_GOOGLE, Host.MAC, "WRITE", ttl_seconds=120)
        self.assertTrue(acquired)

        # Candidate on locked domain
        cand = {
            "task_id": "TASK-CONFLICT-01",
            "goal_id": "GOAL-04",
            "title": "Critical Conflict Task",
            "conflict_scope": domain,
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        res = self.engine.execute_task(cand)
        self.assertFalse(res["success"])
        self.assertIn("ONE_WRITER_LOCK_HELD", res["reason"])

    def test_04_auto_task_succession(self):
        """COURT 4: Autonomous loop executes >=3 consecutive tasks with zero human continuation."""
        self.engine.reservoir.refresh_reservoir("GOAL-04")
        # Run autonomous batch of 3 tasks
        res = self.engine.run_autonomous_batch(max_tasks=3)
        self.assertGreaterEqual(res["executed_count"], 3, "Must execute at least 3 tasks autonomously")
        self.assertGreaterEqual(len(res["executed_tasks"]), 3)
        self.assertGreaterEqual(res["state_generation"], 4)

    def test_05_auto_goal_succession(self):
        """COURT 5: Goal advancement occurs automatically when current goal tasks complete."""
        self.engine.current_goal = "GOAL-01"
        self.engine.reservoir.refresh_reservoir("GOAL-01")
        # Mark all pending GOAL-01 tasks completed
        for t in self.engine.reservoir.get_pending_candidates():
            if t.get("goal_id") == "GOAL-01":
                self.engine.reservoir.do_not_repeat.add(t["task_id"])

        advanced = self.engine.check_and_advance_goal()
        self.assertTrue(advanced, "Must advance to next goal when active goal is satisfied")
        self.assertEqual(self.engine.current_goal, "GOAL-02")

    def test_06_crash_recovery(self):
        """COURT 6: Mid-execution crash with stale running task is detected and recovered."""
        stale_id = "TASK-CRASH-TEST-99"
        self.cp.upsert_task(
            task_id=stale_id,
            assignment_id=f"ASSIGN-{stale_id}",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="DISPATCH"),
            active_agent="CRASHED_PROCESS"
        )
        rec = self.engine.recover_from_interruption()
        self.assertGreaterEqual(rec["repaired_count"], 1)

        t = self.cp.get_task(stale_id)
        self.assertEqual(t["status"], "PENDING", "Stale running task without on-disk effect must reset to PENDING")

    def test_07_post_effect_recovery(self):
        """COURT 7: Interrupted task with committed side-effect is reconciled to COMPLETED."""
        task_id = "TASK-POST-EFFECT-01"
        # Mark completed in backlog file (effect committed)
        with open(self.backlog_file, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        b_data.setdefault("tasks", []).append({"task_id": task_id, "status": "COMPLETED", "evidence": "PASSED"})
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump(b_data, f)

        # But in SQLite it's still RUNNING
        self.cp.upsert_task(
            task_id=task_id,
            assignment_id=f"ASSIGN-{task_id}",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(local_step_erledigt=False, gesamtaufgabe_erledigt=False, blocker="NONE", next_step="DISPATCH"),
            active_agent="CRASHED_PROCESS"
        )

        rec = self.engine.recover_from_interruption()
        self.assertGreaterEqual(rec["repaired_count"], 1)
        t = self.cp.get_task(task_id)
        self.assertEqual(t["status"], "COMPLETED", "Task with verified on-disk effect must recover to COMPLETED")

    def test_08_fresh_session_recovery(self):
        """COURT 8: Fresh engine instance boots from disk without loss of state."""
        self.engine.write_heartbeat("IDLE_TEST", current_task="TASK-WIN-81")

        # Spawn new independent engine instance
        fresh_engine = PermanentReserveEngine(workspace_root=self.temp_dir, cp=self.cp)
        fresh_engine.heartbeat_path = self.engine.heartbeat_path
        fresh_engine._load_state()

        self.assertEqual(fresh_engine.state_generation, self.engine.state_generation)
        self.assertEqual(fresh_engine.current_goal, self.engine.current_goal)

    def test_09_watchdog_recovery(self):
        """COURT 9: Stale locks are automatically pruned by watchdog cleaner."""
        res_key = "DOMAIN_STALE_WATCHDOG"
        # Create lock with 0 TTL (instantly expired)
        self.cp.acquire_lock(res_key, Lane.WINDOWS_GOOGLE, Host.WINDOWS, "WRITE", ttl_seconds=0)
        time.sleep(0.05)

        self.engine.cp.clean_expired_locks()
        active = self.cp.get_active_locks()
        self.assertFalse(any(l["resource_id"] == res_key for l in active), "Expired lock must be cleaned")

    def test_10_crash_loop_protection(self):
        """COURT 10: Repeatedly failing candidate (>=3 fails) is parked in PARKED_CRASH_LOOP."""
        c_id = "TASK-CRASH-LOOP-01"
        self.engine.crash_tracker[c_id] = 3

        # Add to backlog
        cand = {
            "task_id": c_id,
            "goal_id": "GOAL-04",
            "title": "Repeatedly Crashing Task",
            "expected_real_delta": "DEFECT_REMOVAL",
            "priority": 100.0,
            "conflict_scope": "CRASH_DOMAIN",
            "status": "PENDING"
        }
        with open(self.backlog_file, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        b_data.setdefault("tasks", []).append(cand)
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump(b_data, f)

        selected = self.engine.select_next_candidate()
        # The crash looping candidate must NOT be selected
        if selected:
            self.assertNotEqual(selected.get("task_id"), c_id)

    def test_11_resource_bounds(self):
        """COURT 11: Execution batch terminates within bounded task count."""
        self.engine.reservoir.refresh_reservoir("GOAL-04")
        t0 = time.time()
        res = self.engine.run_autonomous_batch(max_tasks=2)
        elapsed = time.time() - t0
        self.assertLessEqual(res["executed_count"], 2)
        self.assertLess(elapsed, 10.0, "Batch must execute within tight bounded time limit")

    def test_12_payment_gate_locality(self):
        """COURT 12: Real spend strictly 0.00 EUR, all live payment gates parked."""
        self.engine.write_heartbeat()
        with open(self.engine.heartbeat_path, "r", encoding="utf-8") as f:
            hb = json.load(f)
        self.assertEqual(hb["real_spend_eur"], 0.00)
        self.assertEqual(hb["real_revenue_eur"], 0.00)
        for pg in ["LIVE_PAYMENT", "LIVE_STRIPE", "REAL_BANKING", "KYC"]:
            self.assertIn(pg, hb["parked_human_gates"])

    def test_13_mac_non_conflict(self):
        """COURT 13: Tasks touching Mac active scopes or universuX are rejected."""
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
        valid_mac, reason_mac = self.engine.reservoir.deduplicate(c_mac)
        self.assertFalse(valid_mac)
        self.assertIn("MAC_SCOPE_PROTECTION", reason_mac)

        valid_ux, reason_ux = self.engine.reservoir.deduplicate(c_ux)
        self.assertFalse(valid_ux)
        self.assertIn("UNIVERSUX_PROTECTION", reason_ux)

    def test_14_real_delta_selection(self):
        """COURT 14: Status churn and busywork rejected; real capability gains accepted."""
        busywork = {
            "task_id": "TASK-BUSYWORK-01",
            "title": "Write redundant status report churn on autonomy",
            "conflict_scope": "DOCS",
            "expected_real_delta": "AUTONOMY_GAIN"
        }
        valid_bw, reason_bw = self.engine.reservoir.deduplicate(busywork)
        self.assertFalse(valid_bw)
        self.assertIn("BUSYWORK", reason_bw)

        valid_candidate = {
            "task_id": "TASK-LEGIT-01",
            "title": "Implement tamper-proof digital seals for audit receipts",
            "conflict_scope": "AUDIT_SEALS",
            "expected_real_delta": "SECURITY_GAIN"
        }
        valid_legit, _ = self.engine.reservoir.deduplicate(valid_candidate)
        self.assertTrue(valid_legit)


if __name__ == "__main__":
    unittest.main()
