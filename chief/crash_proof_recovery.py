"""
crash_proof_recovery.py - Permanent Crash-Proof Memory, Startup Recovery & Idempotency Engine
Canonical Implementation for WINDOWS COURIER PERMANENT CRASH-PROOF MEMORY + SELF-RECOVERY.

Permanent Invariant:
ANTIGRAVITY SESSION != COURIER MEMORY.
The chat is NEVER the source of truth for Courier continuation.
State survives abrupt UI disconnection, task kills, process terminations, and server restarts.
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
import ctypes
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from courier.chief.process_liveness import is_pid_alive

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
RUNTIME_DIR = os.path.join(WORKSPACE_ROOT, "courier", "runtime")
DB_PATH = os.path.join(WORKSPACE_ROOT, "courier", "chief_control_plane.db")
CANONICAL_STATE_FILE = os.path.join(RUNTIME_DIR, "durable_recovery_state.json")
BACKUP_STATE_FILE = os.path.join(RUNTIME_DIR, "durable_recovery_state.bak")
POLICY_FILE = os.path.join(WORKSPACE_ROOT, "courier", "PERMANENT_RECOVERY_POLICY.json")

# Mac-reserved writer scopes that Windows MUST NEVER touch
MAC_RESERVED_SCOPES = [
    "supervisor_standalone.py",
    "customs_agent.py",
    "coordination/mac_to_windows",
    "universuX"
]

class CrashProofMemoryEngine:
    def __init__(
        self,
        db_path: str = DB_PATH,
        state_file: str = CANONICAL_STATE_FILE,
        max_crash_retries: int = 3
    ):
        self.db_path = os.path.abspath(db_path)
        self.state_file = os.path.abspath(state_file)
        self.backup_file = os.path.abspath(self.state_file + ".bak")
        self.max_crash_retries = max_crash_retries
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._init_db()
        self._ensure_policy_file()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS crash_proof_state (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                mission_id TEXT NOT NULL,
                mission_version INTEGER NOT NULL,
                current_goal_id TEXT NOT NULL,
                current_goal_version INTEGER NOT NULL,
                active_task_id TEXT,
                active_task_version INTEGER NOT NULL,
                active_task_fingerprint TEXT,
                task_status TEXT NOT NULL,
                writer_lease TEXT,
                writer_pid INTEGER,
                writer_started_at TEXT,
                last_progress_at TEXT NOT NULL,
                last_verified_task TEXT NOT NULL,
                last_verified_result_json TEXT NOT NULL,
                last_verified_fingerprint TEXT NOT NULL,
                pending_verification INTEGER NOT NULL,
                pending_result_customs INTEGER NOT NULL,
                do_not_repeat_json TEXT NOT NULL,
                open_gaps_json TEXT NOT NULL,
                parked_human_gates_json TEXT NOT NULL,
                mac_reserved_scopes_json TEXT NOT NULL,
                next_safe_candidate TEXT,
                next_automatic_action TEXT NOT NULL,
                recovery_count INTEGER NOT NULL,
                same_task_recovery_count INTEGER NOT NULL,
                last_failure_fingerprint TEXT,
                last_checkpoint_at TEXT NOT NULL,
                state_version INTEGER NOT NULL,
                state_fingerprint TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS recovery_audit_ledger (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                task_id TEXT,
                state_fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def _ensure_policy_file(self):
        if not os.path.exists(POLICY_FILE):
            policy = {
                "schema_version": "1.0",
                "policy_name": "WINDOWS_COURIER_PERMANENT_CRASH_PROOF_POLICY",
                "rules": {
                    "chat_source_of_truth": False,
                    "write_ahead_required": True,
                    "weiter_idempotency_required": True,
                    "max_same_task_recovery_attempts": self.max_crash_retries,
                    "payment_parked_human_gated": True,
                    "automatic_spend_limit_eur": 0.00,
                    "mac_scope_excluded": True,
                    "mac_reserved_scopes": MAC_RESERVED_SCOPES,
                    "weiter_mission_commander": {
                        "definition": "WEITER means reconcile from newest verified state and execute the longest safe chain of highest-value evidence-producing work toward the current north star.",
                        "maximum_forward_progress_mode": True,
                        "stop_condition": "GENUINE_HUMAN_GATE_OR_NO_HIGH_VALUE_SAFE_WORK",
                        "single_small_task_stop_forbidden": True,
                        "parallel_writer_stacking_forbidden": True
                    }
                }
            }
            tmp = POLICY_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(policy, f, indent=2)
            os.replace(tmp, POLICY_FILE)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def compute_fingerprint(data_str: str) -> str:
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    @staticmethod
    def get_resource_diagnostics() -> Dict[str, Any]:
        """Lightweight OS memory and process audit without external dependencies."""
        info = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "memory_load_pct": 50,
            "ram_total_gb": 16.0,
            "ram_available_gb": 8.0,
            "thermal_cause": "UNPROVEN",
            "process_count": 0,
            "suspected_orphans": 0,
            "db_size_bytes": 0
        }
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            info["memory_load_pct"] = stat.dwMemoryLoad
            info["ram_total_gb"] = round(stat.ullTotalPhys / (1024**3), 2)
            info["ram_available_gb"] = round(stat.ullAvailPhys / (1024**3), 2)
        except Exception:
            pass

        if os.path.exists(DB_PATH):
            info["db_size_bytes"] = os.path.getsize(DB_PATH)

        return info

    def load_durable_state(self) -> Dict[str, Any]:
        """Loads canonical state from SQLite, falling back to JSON file or backup if needed."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM crash_proof_state WHERE singleton_id = 1;")
            row = cur.fetchone()
            if row:
                d = dict(row)
                d["last_verified_result"] = json.loads(d["last_verified_result_json"])
                d["do_not_repeat"] = json.loads(d["do_not_repeat_json"])
                d["open_gaps"] = json.loads(d["open_gaps_json"])
                d["parked_human_gates"] = json.loads(d["parked_human_gates_json"])
                d["mac_reserved_scopes"] = json.loads(d["mac_reserved_scopes_json"])

                # Cross-reconcile with checkpoints table if present
                try:
                    cur.execute("SELECT checkpoint_value FROM checkpoints WHERE checkpoint_key = 'LAST_VERIFIED_WINDOWS_CHECKPOINT';")
                    cp_row = cur.fetchone()
                    if cp_row and cp_row[0]:
                        raw_val = cp_row[0]
                        if isinstance(raw_val, str) and raw_val.strip().startswith("{"):
                            ckpt_dict = json.loads(raw_val)
                            ckpt_task = ckpt_dict.get("task_id")
                        else:
                            ckpt_task = str(raw_val)
                        if ckpt_task and ckpt_task != d.get("last_verified_task"):
                            d["last_verified_task"] = ckpt_task
                            if ckpt_task not in d["do_not_repeat"]:
                                d["do_not_repeat"].append(ckpt_task)
                except Exception:
                    pass

                return d

        # Fallback to JSON state file
        for fpath in [self.state_file, self.backup_file]:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if self._validate_state_schema(data):
                            # Restore into SQLite
                            self.save_durable_state(data)
                            return data
                except Exception:
                    continue

        # Initial default state if brand new project
        default_state = self._create_initial_state()
        self.save_durable_state(default_state)
        return default_state

    def _create_initial_state(self) -> Dict[str, Any]:
        now_iso = self._now_iso()
        return {
            "mission_id": "MISSION-AUTONOMY",
            "mission_version": 1,
            "current_goal_id": "GOAL-05",
            "current_goal_version": 1,
            "active_task_id": None,
            "active_task_version": 1,
            "active_task_fingerprint": None,
            "task_status": "IDLE",
            "writer_lease": None,
            "writer_pid": None,
            "writer_started_at": None,
            "last_progress_at": now_iso,
            "last_verified_task": "TASK-WIN-63",
            "last_verified_result": {"status": "PASS", "task_id": "TASK-WIN-63"},
            "last_verified_fingerprint": self.compute_fingerprint("TASK-WIN-63:PASS"),
            "pending_verification": 0,
            "pending_result_customs": 0,
            "do_not_repeat": ["TASK-WIN-63"],
            "open_gaps": ["AUTONOMY_CAPABILITY_GAP"],
            "parked_human_gates": [
                {
                    "gate_id": "HUMAN_GATE_1",
                    "title": "Production Deployment & External Publishing",
                    "reason": "Requires founder approval for Show HN & zero autonomous spend",
                    "status": "PARKED"
                }
            ],
            "mac_reserved_scopes": MAC_RESERVED_SCOPES,
            "next_safe_candidate": "TASK-WIN-64",
            "next_automatic_action": "EXECUTE_SUCCESSOR",
            "recovery_count": 0,
            "same_task_recovery_count": 0,
            "last_failure_fingerprint": None,
            "last_checkpoint_at": now_iso,
            "state_version": 1,
            "state_fingerprint": "INIT_FP"
        }

    def _validate_state_schema(self, data: Dict[str, Any]) -> bool:
        required_keys = [
            "mission_id", "current_goal_id", "task_status",
            "last_verified_task", "last_checkpoint_at"
        ]
        return all(k in data for k in required_keys)

    def save_durable_state(self, state: Dict[str, Any]):
        """Persists state to SQLite and atomic write-ahead JSON file with backup."""
        now_iso = self._now_iso()
        state["last_checkpoint_at"] = now_iso
        state["state_version"] = state.get("state_version", 1) + 1
        
        canonical_str = f"{state['mission_id']}:{state['current_goal_id']}:{state['active_task_id']}:{state['task_status']}:{state['last_verified_task']}:{state['state_version']}:{now_iso}"
        state_fp = self.compute_fingerprint(canonical_str)
        state["state_fingerprint"] = state_fp

        # 1. SQLite Write
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO crash_proof_state (
                singleton_id, mission_id, mission_version, current_goal_id, current_goal_version,
                active_task_id, active_task_version, active_task_fingerprint, task_status,
                writer_lease, writer_pid, writer_started_at, last_progress_at,
                last_verified_task, last_verified_result_json, last_verified_fingerprint,
                pending_verification, pending_result_customs, do_not_repeat_json,
                open_gaps_json, parked_human_gates_json, mac_reserved_scopes_json,
                next_safe_candidate, next_automatic_action, recovery_count,
                same_task_recovery_count, last_failure_fingerprint, last_checkpoint_at,
                state_version, state_fingerprint
            ) VALUES (
                1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            );
            """, (
                state["mission_id"], state["mission_version"], state["current_goal_id"], state["current_goal_version"],
                state["active_task_id"], state["active_task_version"], state["active_task_fingerprint"], state["task_status"],
                state["writer_lease"], state["writer_pid"], state["writer_started_at"], state["last_progress_at"],
                state["last_verified_task"], json.dumps(state["last_verified_result"]), state["last_verified_fingerprint"],
                1 if state.get("pending_verification") else 0, 1 if state.get("pending_result_customs") else 0,
                json.dumps(state["do_not_repeat"]), json.dumps(state["open_gaps"]),
                json.dumps(state["parked_human_gates"]), json.dumps(state["mac_reserved_scopes"]),
                state["next_safe_candidate"], state["next_automatic_action"], state["recovery_count"],
                state["same_task_recovery_count"], state["last_failure_fingerprint"], state["last_checkpoint_at"],
                state["state_version"], state["state_fingerprint"]
            ))

            # Audit event
            event_id = f"EVT-REC-{int(time.time() * 1000)}"
            cur.execute("""
            INSERT INTO recovery_audit_ledger (event_id, event_type, task_id, state_fingerprint, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """, (event_id, "STATE_CHECKPOINT", state["active_task_id"], state_fp, json.dumps({"status": state["task_status"]}), now_iso))
            conn.commit()

        # 2. Dual Write-Ahead File with Backup
        if os.path.exists(self.state_file):
            try:
                import shutil
                shutil.copy2(self.state_file, self.backup_file)
            except Exception:
                pass

        tmp_file = self.state_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_file, self.state_file)

    def write_ahead_intent(
        self,
        task_id: str,
        task_version: int,
        criteria: List[str],
        goal_id: str = "GOAL-05",
        writer_pid: Optional[int] = None
    ) -> Dict[str, Any]:
        """WRITE-AHEAD RULE: Persists task intent BEFORE any code runs."""
        state = self.load_durable_state()
        now_iso = self._now_iso()
        task_fp = self.compute_fingerprint(f"{task_id}:{task_version}:{json.dumps(sorted(criteria))}")

        state["active_task_id"] = task_id
        state["active_task_version"] = task_version
        state["active_task_fingerprint"] = task_fp
        state["task_status"] = "RUNNING"
        state["writer_lease"] = f"LEASE-{task_id}-{int(time.time())}"
        state["writer_pid"] = writer_pid or os.getpid()
        state["writer_started_at"] = now_iso
        state["last_progress_at"] = now_iso
        state["pending_verification"] = 0
        state["pending_result_customs"] = 0

        self.save_durable_state(state)
        return state

    def write_ahead_result(
        self,
        task_id: str,
        result_payload: Dict[str, Any],
        effect_fingerprint: str
    ) -> Dict[str, Any]:
        """Persists task result and side-effect evidence BEFORE Customs verification."""
        state = self.load_durable_state()
        if state["active_task_id"] != task_id:
            state["active_task_id"] = task_id
        
        state["task_status"] = "RESULT_READY"
        state["pending_verification"] = 1
        state["pending_result_customs"] = 1
        state["last_progress_at"] = self._now_iso()
        state["last_verified_result"] = result_payload
        state["last_verified_fingerprint"] = effect_fingerprint

        self.save_durable_state(state)
        return state

    def commit_verified(
        self,
        task_id: str,
        result_payload: Dict[str, Any],
        successor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Commits verified completion and registers task in DO_NOT_REPEAT."""
        state = self.load_durable_state()
        now_iso = self._now_iso()

        state["task_status"] = "VERIFIED"
        state["last_verified_task"] = task_id
        state["last_verified_result"] = result_payload
        state["last_verified_fingerprint"] = self.compute_fingerprint(f"{task_id}:VERIFIED:{now_iso}")
        state["pending_verification"] = 0
        state["pending_result_customs"] = 0
        state["active_task_id"] = None
        state["writer_lease"] = None
        state["writer_pid"] = None
        state["next_safe_candidate"] = successor_id
        state["next_automatic_action"] = "EXECUTE_SUCCESSOR" if successor_id else "DISCOVER_CANDIDATE"
        state["same_task_recovery_count"] = 0

        # Register in DO_NOT_REPEAT
        if task_id not in state["do_not_repeat"]:
            state["do_not_repeat"].append(task_id)

        self.save_durable_state(state)
        return state

    def reconcile_on_startup(self) -> Dict[str, Any]:
        """
        STARTUP RECOVERY & PROCESS RECONCILIATION:
        Discovers and validates durable state upon fresh session start.
        """
        state = self.load_durable_state()
        active_id = state.get("active_task_id")
        status = state.get("task_status")
        pid = state.get("writer_pid")

        reconcile_report = {
            "recovered": True,
            "mission_id": state["mission_id"],
            "current_goal_id": state["current_goal_id"],
            "last_verified_task": state["last_verified_task"],
            "next_safe_candidate": state["next_safe_candidate"],
            "reconciliation_case": "NORMAL",
            "action_required": state["next_automatic_action"]
        }

        if state.get("pending_result_customs") or status == "RESULT_READY":
            reconcile_report["reconciliation_case"] = "CASE_3_RESULT_PENDING_VERIFICATION"
            reconcile_report["action_required"] = "VERIFY_EXISTING_RESULT"
            return reconcile_report

        if status in ("RUNNING", "INTERRUPTED") and active_id:
            # Check process liveness safely without console signals
            pid_alive = is_pid_alive(pid) if pid else False

            if pid_alive:
                # Case 1: Process alive + valid lease -> attach, do NOT duplicate
                reconcile_report["reconciliation_case"] = "CASE_1_PROCESS_ALIVE"
                reconcile_report["action_required"] = "ATTACH_AND_WAIT"
            else:
                # Case 2: Process dead -> Check for crash loop
                state["recovery_count"] = state.get("recovery_count", 0) + 1
                state["same_task_recovery_count"] = state.get("same_task_recovery_count", 0) + 1

                if state["same_task_recovery_count"] > self.max_crash_retries:
                    # Crash loop detected!
                    state["task_status"] = "BLOCKED"
                    state["next_automatic_action"] = "CRASH_LOOP_PREVENTED_SELECT_ALTERNATIVE"
                    self.save_durable_state(state)
                    reconcile_report["reconciliation_case"] = "CRASH_LOOP_DETECTED"
                    reconcile_report["action_required"] = "SELECT_INDEPENDENT_SAFE_WORK"
                    reconcile_report["blocked_task"] = active_id
                    return reconcile_report

                # Safe recovery retry
                state["task_status"] = "INTERRUPTED"
                self.save_durable_state(state)
                reconcile_report["reconciliation_case"] = "CASE_2_PROCESS_DEAD_RESUME"
                reconcile_report["action_required"] = "RETRY_INTERRUPTED_TASK_ONCE"

        elif status in ("VERIFIED", "IDLE"):
            reconcile_report["reconciliation_case"] = "CLEAN_IDLE"
            reconcile_report["action_required"] = "ADVANCE_TO_SUCCESSOR"

        return reconcile_report

    def handle_weiter_signal(self) -> Dict[str, Any]:
        """
        PERMANENT 'weiter' IDEMPOTENCY SEMANTICS:
        Reconciles durable state without re-running verified work or duplicating tasks.
        """
        state = self.load_durable_state()
        active_id = state.get("active_task_id")
        status = state.get("task_status")

        if status == "RUNNING":
            return {
                "decision": "SUPPRESS_DUPLICATE_CONTINUATION",
                "reason": f"Task {active_id} is actively RUNNING under lease {state.get('writer_lease')}",
                "tasks_duplicated": 0,
                "action": "MONITOR_IN_FLIGHT"
            }
        elif status == "VERIFIED":
            return {
                "decision": "ADVANCE_TO_NEXT_GOAL",
                "reason": f"Task {state.get('last_verified_task')} already VERIFIED. Do not repeat.",
                "tasks_duplicated": 0,
                "successor": state.get("next_safe_candidate"),
                "action": "EXECUTE_SUCCESSOR"
            }
        elif status == "INTERRUPTED":
            return {
                "decision": "RESUME_INTERRUPTED_ONCE",
                "task_id": active_id,
                "tasks_duplicated": 0,
                "action": "EXECUTE_INTERRUPTED_RECOVERY"
            }
        else:
            return {
                "decision": "DISCOVER_NEXT_SAFE_TASK",
                "successor": state.get("next_safe_candidate"),
                "tasks_duplicated": 0,
                "action": "EXECUTE_SUCCESSOR"
            }

    def get_bootstrap_summary(self) -> str:
        """Deterministic bootstrap string for a fresh Antigravity agent."""
        state = self.load_durable_state()
        return (
            f"=== COURIER DURABLE MISSION BOOTSTRAP ===\n"
            f"MISSION: {state['mission_id']} (Goal: {state['current_goal_id']})\n"
            f"LAST VERIFIED TASK: {state['last_verified_task']}\n"
            f"ACTIVE/INTERRUPTED TASK: {state.get('active_task_id') or 'NONE'}\n"
            f"TASK STATUS: {state['task_status']}\n"
            f"NEXT SAFE CANDIDATE: {state.get('next_safe_candidate')}\n"
            f"NEXT AUTOMATIC ACTION: {state['next_automatic_action']}\n"
            f"PARKED HUMAN GATES: {len(state.get('parked_human_gates', []))} (Payment/Publishing)\n"
            f"DO_NOT_REPEAT COUNT: {len(state.get('do_not_repeat', []))}\n"
            f"=========================================="
        )
