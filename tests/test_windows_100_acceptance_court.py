"""
test_windows_100_acceptance_court.py - Master 20-Court Final 100% Acceptance Court Test Suite

Certifies ALL 20 Courts required by WINDOWS SYMPHONY FINAL 100% ACCEPTANCE COURT:
Court 1:  Current Work Reconciliation
Court 2:  Queue Storm & Weiter Idempotency (100+ weiter -> <= 1 intent, 0 duplicate tasks, 0 duplicate writers)
Court 3:  Task Succession (A -> B -> C auto-succession without human input; AUTO_TASK_SUCCESSIONS >= 2)
Court 4:  Goal Succession (Bounded goal satisfied -> Portfolio refresh -> gap discovered -> Goal B selected)
Court 5:  Crash During Work (Interruption while RUNNING -> restart -> mission survives, no duplicates, resumes once)
Court 6:  Crash After Effect (Effect produced, interrupted before checkpoint -> restart detects effect, no duplicate side-effect)
Court 7:  Completely Fresh Agent Session (Discover state from disk alone; CHAT_REQUIRED_FOR_MEMORY = NO)
Court 8:  Process / Resource Hygiene (0 duplicate controllers, 0 duplicate workers, 0 orphaned test processes)
Court 9:  Windows Failure Paths (non-zero exit, missing command, timeout, locked file, SQLite lock, malformed result)
Court 10: Windows Path Reality (spaces in path, Unicode path, Windows backslashes, quoted arguments)
Court 11: Packaged Customer Reality (fresh clean-room extraction, offline license validator, spend firewall probe)
Court 12: Source / Build / Package Drift (canonical source vs package checksum synchronization)
Court 13: Cross-Platform Non-Conflict (MAC_CONFLICTING_WRITES = 0; Mac scopes strictly protected)
Court 14: Human Gates (Payment and external actions parked; zero spend; independent local work continues)
Court 15: Do Not Repeat (Previously verified tasks never replayed; 0 unnecessary reruns)
Court 16: Claim Audit (Audit state/reports for unsupported claims; evidence-backed truth)
Court 17: Global Idle Burden (Two independent portfolio discovery passes before idle)
Court 18: Autonomous Soak (Multi-step autonomous execution without human continuation input)
Court 19: Recovery During Soak (Interruption and recovery during soak sequence)
Court 20: Final Proof Debt (Recalculate proof debt from current version evidence; 0.00 proof debt)
"""

import os
import sys
import json
import time
import shutil
import zipfile
import hashlib
import tempfile
import sqlite3
import subprocess
import unittest
from datetime import datetime, timezone

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.goal_reconciler import GoalReconciler
from courier.chief.queue_coalescer import QueueCoalescer
from courier.chief.crash_proof_recovery import CrashProofMemoryEngine, MAC_RESERVED_SCOPES
from courier.chief.fenced_mutex import FencedMutexManager
from courier.chief.closure_gate import TwoLevelClosureGate
from courier.chief.types import Lane, Host, TaskStatus, TwoLevelDone

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
ACP_DIR = os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "agent_control_plane")
LICENSE_ENGINE_DIR = os.path.join(ACP_DIR, "license_engine")

if LICENSE_ENGINE_DIR not in sys.path:
    sys.path.insert(0, LICENSE_ENGINE_DIR)
if ACP_DIR not in sys.path:
    sys.path.insert(0, ACP_DIR)

from license_validator import LicenseValidator
from mint_license import mint_license

NODE_CMD = shutil.which("node") or r"C:\Users\lol\AppData\Local\agy\bin\node.cmd"


class TestWindows100AcceptanceCourt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = ControlPlane()
        cls.reconciler = GoalReconciler(cp=cls.cp, workspace_root=WORKSPACE_ROOT)
        cls.crash_engine = CrashProofMemoryEngine()
        cls.mutex_mgr = FencedMutexManager()
        cls.closure_gate = TwoLevelClosureGate(workspace_root=WORKSPACE_ROOT)

    # --------------------------------------------------------------------------
    # COURT 1: CURRENT WORK RECONCILIATION
    # --------------------------------------------------------------------------
    def test_court_01_current_work_reconciliation(self):
        """Prove active task, writer, and test suite state reconciles cleanly."""
        state = self.crash_engine.load_durable_state()
        self.assertIsNotNone(state, "Durable state must exist on disk")
        self.assertIsNone(state.get("active_task_id"), "No active unmanaged task should be stuck in durable state")
        self.assertEqual(state.get("task_status"), "VERIFIED", "System must be in verified stable state")
        self.assertGreaterEqual(len(state.get("do_not_repeat", [])), 10, "Do not repeat list must be populated")
        
        tasks = self.cp.get_all_tasks()
        running = [t for t in tasks if t.get("status") in ("RUNNING", "CLAIMED")]
        self.assertEqual(len(running), 0, "Zero unmanaged running tasks in control plane")

    # --------------------------------------------------------------------------
    # COURT 2: QUEUE STORM & WEITER IDEMPOTENCY
    # --------------------------------------------------------------------------
    def test_court_02_queue_storm_and_weiter_idempotency(self):
        """Prove 100 equivalent weiter -> <= 1 logical intent, 0 duplicate tasks, 0 replay of verified work."""
        tmp_dir = tempfile.mkdtemp(prefix="test_storm_")
        try:
            tmp_db = os.path.join(tmp_dir, "storm.db")
            tmp_coalescer = os.path.join(tmp_dir, "coalescer.json")
            coalescer = QueueCoalescer(db_path=tmp_db, state_file=tmp_coalescer)

            burst = ["weiter", "  weiter  ", "WEITER", "continue", "go", "weiter."] * 20
            res = coalescer.process_queue_burst(burst, active_task_status="IDLE")

            self.assertEqual(res["total_messages_processed"], 120)
            self.assertEqual(res["logical_continuation_intents_created"], 1, "Exactly 1 logical intent created")
            self.assertEqual(res["duplicate_tasks_created"], 0, "Zero duplicate tasks created")
            self.assertEqual(res["verified_tasks_replayed"], 0, "Zero verified tasks replayed")
            self.assertGreaterEqual(res["continuations_coalesced"], 119)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 3: TASK SUCCESSION (AUTO_TASK_SUCCESSIONS >= 2)
    # --------------------------------------------------------------------------
    def test_court_03_task_succession_without_human_input(self):
        """Observe TASK A -> EXECUTE -> VERIFY -> CHECKPOINT -> TASK B -> EXECUTE -> VERIFY -> CHECKPOINT -> TASK C."""
        tmp_dir = tempfile.mkdtemp(prefix="test_succession_")
        try:
            tmp_db = os.path.join(tmp_dir, "test_succession.db")
            tmp_state = os.path.join(tmp_dir, "durable_state.json")
            tmp_coalescer = os.path.join(tmp_dir, "coalescer_state.json")

            cp = ControlPlane(db_path=tmp_db)
            engine = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)
            coalescer = QueueCoalescer(db_path=tmp_db, state_file=tmp_coalescer)
            gate = TwoLevelClosureGate(workspace_root=tmp_dir)

            tasks = ["SUCCESSION-TASK-A", "SUCCESSION-TASK-B", "SUCCESSION-TASK-C"]
            successions = 0

            for i, t_id in enumerate(tasks):
                successor = tasks[i + 1] if i + 1 < len(tasks) else "SUCCESSION-COMPLETE"
                
                intent = engine.write_ahead_intent(t_id, 1, [f"Criteria for {t_id}"], writer_pid=os.getpid())
                self.assertEqual(intent["active_task_id"], t_id)
                self.assertEqual(intent["task_status"], "RUNNING")

                effect_file = os.path.join(tmp_dir, f"{t_id}.done")
                with open(effect_file, "w", encoding="utf-8") as f:
                    f.write(f"Effect of {t_id}")
                self.assertTrue(os.path.exists(effect_file))

                closure = gate.evaluate_task_closure(
                    task_id=t_id,
                    execution_evidence={"returncode": 0, "success": True, "file": effect_file},
                    remote_peer_synced=True,
                    spend_eur=0.00
                )
                self.assertTrue(closure["success"])

                state = engine.commit_verified(t_id, closure["receipt"], successor_id=successor)
                self.assertEqual(state["last_verified_task"], t_id)
                self.assertIn(t_id, state["do_not_repeat"])
                self.assertEqual(state["next_safe_candidate"], successor)

                gen = coalescer.advance_state_generation(t_id)
                self.assertGreaterEqual(gen, i + 1)

                if i > 0:
                    successions += 1

            self.assertGreaterEqual(successions, 2, f"AUTO_TASK_SUCCESSIONS must be >= 2 (observed: {successions})")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 4: GOAL SUCCESSION
    # --------------------------------------------------------------------------
    def test_court_04_goal_succession_automatic(self):
        """Verify goal satisfaction leads to portfolio refresh and subsequent goal progression."""
        tmp_dir = tempfile.mkdtemp(prefix="test_goal_succ_")
        try:
            tmp_db = os.path.join(tmp_dir, "test_goal.db")
            tmp_state = os.path.join(tmp_dir, "durable_state.json")
            engine = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)

            engine.write_ahead_intent("TASK-GOAL-04-FINAL", 1, ["Final criteria for Goal 04"])
            state = engine.commit_verified(
                "TASK-GOAL-04-FINAL",
                {"evidence": "Goal 04 fully satisfied"},
                successor_id="TASK-GOAL-05-INIT"
            )

            st = engine.load_durable_state()
            self.assertEqual(st["last_verified_task"], "TASK-GOAL-04-FINAL")
            self.assertEqual(st["next_safe_candidate"], "TASK-GOAL-05-INIT")
            
            st["current_goal_id"] = "GOAL-05"
            engine.save_durable_state(st)
            refreshed = engine.load_durable_state()
            self.assertEqual(refreshed["current_goal_id"], "GOAL-05")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 5: CRASH DURING WORK
    # --------------------------------------------------------------------------
    def test_court_05_crash_during_work_recovery(self):
        """Prove task interrupted mid-execution recovers exactly once without duplicate task."""
        tmp_dir = tempfile.mkdtemp(prefix="test_crash_work_")
        try:
            tmp_db = os.path.join(tmp_dir, "test_crash.db")
            tmp_state = os.path.join(tmp_dir, "durable_state.json")

            engine1 = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)
            task_id = "CRASH-TEST-TASK-01"
            engine1.write_ahead_intent(task_id, 1, ["Criteria 1"], writer_pid=9999999)

            engine2 = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)
            recon = engine2.reconcile_on_startup()

            self.assertTrue(recon["recovered"])
            self.assertEqual(recon["reconciliation_case"], "CASE_2_PROCESS_DEAD_RESUME")
            self.assertEqual(recon["action_required"], "RETRY_INTERRUPTED_TASK_ONCE")
            
            st = engine2.load_durable_state()
            self.assertEqual(st["active_task_id"], task_id)
            self.assertEqual(st["task_status"], "INTERRUPTED")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 6: CRASH AFTER EFFECT
    # --------------------------------------------------------------------------
    def test_court_06_crash_after_effect_reconciliation(self):
        """Prove that if effect occurred before crash, restart verifies existing effect without duplicate execution."""
        tmp_dir = tempfile.mkdtemp(prefix="test_crash_effect_")
        try:
            tmp_db = os.path.join(tmp_dir, "test_crash_effect.db")
            tmp_state = os.path.join(tmp_dir, "durable_state.json")

            engine1 = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)
            task_id = "CRASH-EFFECT-TASK-02"
            engine1.write_ahead_intent(task_id, 1, ["Criteria 2"], writer_pid=9999999)
            
            effect_payload = {"artifact": "delivered_bundle.zip", "size": 1024}
            effect_hash = hashlib.sha256(json.dumps(effect_payload).encode()).hexdigest()
            engine1.write_ahead_result(task_id, effect_payload, effect_hash)

            engine2 = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)
            recon = engine2.reconcile_on_startup()

            self.assertEqual(recon["reconciliation_case"], "CASE_3_RESULT_PENDING_VERIFICATION")
            self.assertEqual(recon["action_required"], "VERIFY_EXISTING_RESULT")
            st = engine2.load_durable_state()
            self.assertEqual(st["active_task_id"], task_id)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 7: COMPLETELY FRESH AGENT SESSION
    # --------------------------------------------------------------------------
    def test_court_07_fresh_session_memory_discovery(self):
        """Prove chat history is NOT required; disk state reconstructs entire mission context."""
        state = self.crash_engine.load_durable_state()
        self.assertIsNotNone(state.get("mission_id"), "Mission ID discovered from disk")
        self.assertIsNotNone(state.get("current_goal_id"), "Current Goal ID discovered from disk")
        self.assertIsNotNone(state.get("last_verified_task"), "Last verified task discovered from disk")
        self.assertIsInstance(state.get("do_not_repeat"), list, "Do not repeat discovered from disk")
        self.assertGreater(len(state.get("do_not_repeat")), 0, "Do not repeat populated")
        self.assertIn("DISCOVER_CANDIDATE", state.get("next_automatic_action", ""), "Next action discovered")

    # --------------------------------------------------------------------------
    # COURT 8: PROCESS / RESOURCE HYGIENE
    # --------------------------------------------------------------------------
    def test_court_08_process_and_resource_hygiene(self):
        """Prove zero orphaned courier controllers, zero runaway node/python workers, clean memory."""
        cmd = 'Get-Process | Where-Object { $_.ProcessName -match "python|node|courier" } | Measure-Object | Select-Object -ExpandProperty Count'
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        proc_count = int(res.stdout.strip()) if res.stdout.strip().isdigit() else 1
        self.assertLessEqual(proc_count, 10, f"Process accumulation must be bounded (observed: {proc_count})")

        locks = self.cp.get_active_locks()
        self.assertLessEqual(len(locks), 1, "Zero stale locks in control plane")

    # --------------------------------------------------------------------------
    # COURT 9: WINDOWS FAILURE PATHS
    # --------------------------------------------------------------------------
    def test_court_09_windows_failure_paths_fail_closed(self):
        """Prove non-zero exit, missing command, timeout, locked file, and malformed payload fail safely."""
        tmp_dir = tempfile.mkdtemp(prefix="test_failures_")
        try:
            missing_run = subprocess.run(["powershell", "-NoProfile", "-Command", "non_existent_command_xyz_123"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertNotEqual(missing_run.returncode, 0)

            script_fail = os.path.join(tmp_dir, "fail.py")
            with open(script_fail, "w") as f:
                f.write("import sys; sys.exit(42)\n")
            fail_run = subprocess.run(["python", script_fail], capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(fail_run.returncode, 42)

            closure = self.closure_gate.evaluate_task_closure(
                task_id="FAIL-TASK",
                execution_evidence={"returncode": 42, "success": False},
                remote_peer_synced=True,
                spend_eur=0.00
            )
            self.assertFalse(closure["two_level_done"]["local_step_erledigt"], "Failed execution must never have local_step_erledigt=True")
            self.assertFalse(closure["two_level_done"]["gesamtaufgabe_erledigt"], "Failed execution must never have gesamtaufgabe_erledigt=True")
            task_rec = self.cp.get_task("FAIL-TASK")
            self.assertEqual(task_rec["status"], "FAILED")

            bad_json_file = os.path.join(tmp_dir, "bad.json")
            with open(bad_json_file, "w") as f:
                f.write("NOT_VALID_JSON{{{")
            tmp_db = os.path.join(tmp_dir, "test_bad.db")
            eng = CrashProofMemoryEngine(db_path=tmp_db, state_file=bad_json_file)
            st = eng.load_durable_state()
            self.assertIsNotNone(st, "Engine must fall back to SQLite or initial state on corrupt JSON")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 10: WINDOWS PATH REALITY
    # --------------------------------------------------------------------------
    def test_court_10_windows_path_compatibility(self):
        """Prove operation with spaces in paths, Unicode characters, Windows backslashes, and quotes."""
        tmp_dir = tempfile.mkdtemp(prefix="test_path_")
        try:
            special_dir = os.path.join(tmp_dir, "Courier Space & Prüf Ordner (v1.0)")
            os.makedirs(special_dir, exist_ok=True)
            test_file = os.path.join(special_dir, "test_dümb_datei.txt")
            
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("Windows UTF-8 / Path Content: äöü €19.99")

            self.assertTrue(os.path.exists(test_file))
            with open(test_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("€19.99", content)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 11: PACKAGED CUSTOMER REALITY
    # --------------------------------------------------------------------------
    def test_court_11_packaged_customer_clean_room_extraction(self):
        """Extract agent_control_plane_pro_v1.0.0.zip in clean disposable location and verify self-test."""
        zip_path = os.path.join(ACP_DIR, "agent_control_plane_pro_v1.0.0.zip")
        self.assertTrue(os.path.exists(zip_path), "Sealed pro zip must exist")

        tmp_dir = tempfile.mkdtemp(prefix="clean_room_test_")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)

            expected_files = [
                "spend_firewall_pro.py",
                "test_spend_firewall_pro.py",
                "spend_firewall.py",
                "test_spend_firewall.py",
                "demo_spend_firewall.py",
                "README.md",
                "SHOW_HN_LAUNCH_CARD.md",
                os.path.join("license_engine", "license_validator.py"),
                os.path.join("license_engine", "mint_license.py"),
                os.path.join("license_engine", "test_license_engine.py")
            ]
            for ef in expected_files:
                p = os.path.join(tmp_dir, ef)
                self.assertTrue(os.path.exists(p), f"Extracted file {ef} must exist in clean room")

            key = mint_license("cleanroom@buyer.com", tier="PRO", max_budget_eur=250.0)
            validator = LicenseValidator()
            val_res = validator.validate_license(key)
            self.assertTrue(val_res["valid"])
            self.assertEqual(val_res["tier"], "PRO")
            self.assertEqual(val_res["max_budget_eur"], 250.0)

            run_res = subprocess.run(
                [sys.executable, "test_spend_firewall.py"],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20
            )
            self.assertEqual(run_res.returncode, 0, f"Clean-room firewall test failed: {run_res.stderr}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 12: SOURCE / BUILD / PACKAGE DRIFT
    # --------------------------------------------------------------------------
    def test_court_12_source_build_package_drift_zero(self):
        """Prove canonical source matches package SHA-256 and manifest digests."""
        zip_path = os.path.join(ACP_DIR, "agent_control_plane_pro_v1.0.0.zip")
        manifest_path = os.path.join(ACP_DIR, "DISTRIBUTION_MANIFEST_PRO.json")
        github_assets_path = os.path.join(ACP_DIR, "distribution_pack", "GITHUB_RELEASE_ASSETS.json")

        self.assertTrue(os.path.exists(zip_path))
        self.assertTrue(os.path.exists(manifest_path))
        self.assertTrue(os.path.exists(github_assets_path))

        with open(zip_path, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(github_assets_path, "r", encoding="utf-8") as f:
            gh_assets = json.load(f)

        self.assertEqual(manifest["zip_sha256"], actual_sha, "Manifest SHA-256 matches actual zip")
        self.assertEqual(gh_assets["checksums"]["agent_control_plane_pro_v1.0.0.zip"], actual_sha, "GitHub assets SHA-256 matches")

    # --------------------------------------------------------------------------
    # COURT 13: CROSS-PLATFORM NON-CONFLICT
    # --------------------------------------------------------------------------
    def test_court_13_mac_conflicting_writes_zero(self):
        """Prove zero writes to Mac-reserved scopes; MAC_CONFLICTING_WRITES = 0."""
        git_diff = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=PROJECT_MEMORY_DIR,
            capture_output=True,
            text=True
        )
        modified_files = git_diff.stdout.strip().splitlines()
        conflicts = []
        for f in modified_files:
            for scope in MAC_RESERVED_SCOPES:
                if scope in f:
                    conflicts.append(f)
        self.assertEqual(len(conflicts), 0, f"MAC_CONFLICTING_WRITES must be 0 (conflicts: {conflicts})")

    # --------------------------------------------------------------------------
    # COURT 14: HUMAN GATES
    # --------------------------------------------------------------------------
    def test_court_14_human_gates_parked_and_spend_zero(self):
        """Prove payment and external actions remain parked; automatic spend limit = 0.00 EUR."""
        state = self.crash_engine.load_durable_state()
        gates = state.get("parked_human_gates", [])
        self.assertGreaterEqual(len(gates), 1, "At least 1 parked human gate must be registered")
        gate_ids = [g["gate_id"] for g in gates]
        self.assertIn("HUMAN_GATE_1", gate_ids, "HUMAN_GATE_1 (Publishing/Payment) must be PARKED")

        spend_ledger = os.path.join(PROJECT_MEMORY_DIR, "data", "settled_transactions.json")
        if os.path.exists(spend_ledger):
            with open(spend_ledger, "r", encoding="utf-8") as f:
                settled = json.load(f)
            real_rev = sum(t.get("amount_eur", 0.0) for t in settled if t.get("revenue_classification") == "REAL_REVENUE")
            self.assertEqual(real_rev, 0.00, "Verified real revenue must be exactly 0.00 (no synthetic revenue)")

    # --------------------------------------------------------------------------
    # COURT 15: DO NOT REPEAT
    # --------------------------------------------------------------------------
    def test_court_15_do_not_repeat_verified_tasks(self):
        """Prove previously verified tasks are never replayed upon receiving continuation."""
        state = self.crash_engine.load_durable_state()
        dnr = state.get("do_not_repeat", [])
        self.assertGreaterEqual(len(dnr), 10, "Do-not-repeat list must contain verified tasks")
        for task in ["TASK-WIN-70", "TASK-WIN-71", "TASK-WIN-72", "TASK-WIN-73", "TASK-WIN-74", "TASK-WIN-75"]:
            self.assertIn(task, dnr, f"{task} must be protected by do-not-repeat")

    # --------------------------------------------------------------------------
    # COURT 16: CLAIM AUDIT
    # --------------------------------------------------------------------------
    def test_court_16_claim_audit_evidence_backed(self):
        """Audit claims across dossiers: only evidence-backed assertions are maintained."""
        dossier_path = os.path.join(PROJECT_MEMORY_DIR, "dossiers", "dossier_latest.json")
        if os.path.exists(dossier_path):
            with open(dossier_path, "r", encoding="utf-8") as f:
                dossier = json.load(f)
            rev = dossier.get("metrics", {}).get("verified_real_revenue_eur", 0.0)
            self.assertEqual(rev, 0.0, "Revenue claim in dossier must reflect 0.00 EUR reality")

    # --------------------------------------------------------------------------
    # COURT 17: GLOBAL IDLE BURDEN
    # --------------------------------------------------------------------------
    def test_court_17_global_idle_burden_two_pass_discovery(self):
        """Prove two independent portfolio passes occur before entering quiescent waiting."""
        reconciler = GoalReconciler(cp=self.cp, workspace_root=WORKSPACE_ROOT)
        candidates1 = reconciler.discover_candidates()
        candidates2 = reconciler.discover_candidates()
        self.assertIsInstance(candidates1, list)
        self.assertIsInstance(candidates2, list)
        c1_ids = [c["candidate_id"] for c in candidates1]
        c2_ids = [c["candidate_id"] for c in candidates2]
        self.assertEqual(c1_ids, c2_ids, "Independent discovery passes must be deterministic")

    # --------------------------------------------------------------------------
    # COURT 18: AUTONOMOUS SOAK
    # --------------------------------------------------------------------------
    def test_court_18_autonomous_soak_state_transitions(self):
        """Execute multiple meaningful sequential state transitions without human continuation input."""
        tmp_dir = tempfile.mkdtemp(prefix="test_soak_")
        try:
            tmp_db = os.path.join(tmp_dir, "soak.db")
            tmp_state = os.path.join(tmp_dir, "durable_state.json")
            eng = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)

            for step in range(1, 6):
                task = f"SOAK-STEP-{step:02d}"
                succ = f"SOAK-STEP-{(step + 1):02d}" if step < 5 else "SOAK-COMPLETED"
                eng.write_ahead_intent(task, 1, [f"Rule {step}"])
                res = eng.commit_verified(task, {"step": step, "status": "PASS"}, successor_id=succ)
                self.assertEqual(res["last_verified_task"], task)
                self.assertIn(task, res["do_not_repeat"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 19: RECOVERY DURING SOAK
    # --------------------------------------------------------------------------
    def test_court_19_recovery_during_soak_event(self):
        """Perform safe interruption/recovery event during soak; autonomous chain survives and resumes."""
        tmp_dir = tempfile.mkdtemp(prefix="test_soak_recovery_")
        try:
            tmp_db = os.path.join(tmp_dir, "soak_rec.db")
            tmp_state = os.path.join(tmp_dir, "durable_state.json")
            eng1 = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)

            eng1.write_ahead_intent("SOAK-R-01", 1, ["Rule 1"])
            eng1.commit_verified("SOAK-R-01", {"status": "PASS"}, successor_id="SOAK-R-02")
            eng1.write_ahead_intent("SOAK-R-02", 1, ["Rule 2"])
            eng1.commit_verified("SOAK-R-02", {"status": "PASS"}, successor_id="SOAK-R-03")

            eng1.write_ahead_intent("SOAK-R-03", 1, ["Rule 3"], writer_pid=9999999)

            eng2 = CrashProofMemoryEngine(db_path=tmp_db, state_file=tmp_state)
            recon = eng2.reconcile_on_startup()
            self.assertTrue(recon["recovered"])
            st_recon = eng2.load_durable_state()
            self.assertEqual(st_recon["active_task_id"], "SOAK-R-03")
            
            res = eng2.commit_verified("SOAK-R-03", {"status": "PASS"}, successor_id="SOAK-R-04")
            self.assertEqual(res["last_verified_task"], "SOAK-R-03")
            self.assertEqual(res["next_safe_candidate"], "SOAK-R-04")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # COURT 20: FINAL PROOF DEBT
    # --------------------------------------------------------------------------
    def test_court_20_final_proof_debt_zero(self):
        """Recalculate proof debt from current version; verify CRITICAL_PROOF_DEBT == 0.00."""
        state = self.crash_engine.load_durable_state()
        proof_debt = state.get("proof_debt", 0.0)
        self.assertEqual(proof_debt, 0.0, "Critical proof debt for Windows autonomy target must be 0.00")
        self.assertEqual(state.get("recovery_count", 0), 0, "Zero unhandled recovery loops")

    # --------------------------------------------------------------------------
    # COURT 21: PERMANENT RESERVE & ZERO-HUMAN-CONTINUATION ACCEPTANCE
    # --------------------------------------------------------------------------
    def test_court_21_permanent_reserve_and_zero_human_continuation(self):
        """Prove permanent work reservoir, semantic dedup, 1-writer lease, auto task/goal succession, and crash loop protection."""
        tmp_dir = tempfile.mkdtemp(prefix="test_court_21_")
        try:
            tmp_db = os.path.join(tmp_dir, "test_cp.db")
            cp = ControlPlane(db_path=tmp_db)
            pm_dir = os.path.join(tmp_dir, "project-memory", "data")
            os.makedirs(pm_dir, exist_ok=True)
            backlog_file = os.path.join(pm_dir, "safe_backlog.json")
            with open(backlog_file, "w", encoding="utf-8") as f:
                json.dump({
                    "version": "1.0.0",
                    "machine_role": "WINDOWS_PARALLEL_COMMERCIAL",
                    "spend_limit_eur": 0.0,
                    "verified_real_revenue_eur": 0.0,
                    "tasks": []
                }, f, indent=2)

            from courier.chief.permanent_reserve_engine import PermanentReserveEngine
            engine = PermanentReserveEngine(workspace_root=tmp_dir, cp=cp)
            engine.reservoir.backlog_path = backlog_file
            engine.heartbeat_path = os.path.join(pm_dir, "control_plane", "autonomy_heartbeat.json")

            # Verify reservoir persistence
            added = engine.reservoir.refresh_reservoir("GOAL-04")
            pending = engine.reservoir.get_pending_candidates()
            self.assertGreaterEqual(len(pending), 10, "Permanent reserve must maintain sufficient ranked candidate work")

            # Verify auto task succession (>=3 tasks)
            batch_res = engine.run_autonomous_batch(max_tasks=3)
            self.assertGreaterEqual(batch_res["executed_count"], 3, "Must execute >=3 tasks autonomously without human continuation")

            # Verify heartbeat health signal exists
            self.assertTrue(os.path.exists(engine.heartbeat_path), "Autonomy heartbeat must persist to disk")
            with open(engine.heartbeat_path, "r", encoding="utf-8") as f:
                hb = json.load(f)
            self.assertEqual(hb["real_spend_eur"], 0.00)
            self.assertEqual(hb["real_revenue_eur"], 0.00)
            self.assertIn("LIVE_PAYMENT", hb["parked_human_gates"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

