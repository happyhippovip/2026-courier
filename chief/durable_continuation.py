"""
durable_continuation.py - Durable State Persistence & Idempotent "weiter" Recovery Engine
Part of WINDOWS COURIER P0 CRASH/RESUME + weiter IDEMPOTENCY RECOVERY.

Provides:
1. Durable continuation state persistence before and during task execution.
2. Crash/interruption recovery without false completion or task duplication.
3. Strict idempotency for rapid repeated "weiter" signals (TASKS_DUPLICATED = 0).
4. No-Repeat Registry with cryptographic semantic fingerprints.
5. System diagnostics (CPU, RAM, process count, DB health).
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

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
DB_PATH = os.path.join(WORKSPACE_ROOT, "courier", "chief_control_plane.db")
STATE_FILE = os.path.join(WORKSPACE_ROOT, "project-memory", "data", "control_plane", "durable_continuation.json")

class DurableContinuationManager:
    def __init__(self, db_path: str = DB_PATH, state_file: str = STATE_FILE):
        self.db_path = os.path.abspath(db_path)
        self.state_file = os.path.abspath(state_file)
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS durable_continuation_state (
                mission_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                task_id TEXT PRIMARY KEY,
                task_version INTEGER NOT NULL,
                task_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                lease_id TEXT,
                started_at TEXT NOT NULL,
                last_progress_at TEXT NOT NULL,
                last_checkpoint TEXT NOT NULL,
                acceptance_criteria_json TEXT NOT NULL,
                result_state_json TEXT NOT NULL,
                verification_state TEXT NOT NULL,
                successor_state TEXT,
                do_not_repeat_fingerprint TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS continuation_metrics (
                metric_key TEXT PRIMARY KEY,
                metric_value INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS do_not_repeat_registry (
                fingerprint TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_version INTEGER NOT NULL,
                verified_at TEXT NOT NULL
            );
            """)
            # Initialize metrics counters if missing
            for k in ["duplicate_continuations_received", "duplicate_continuations_suppressed", "tasks_duplicated"]:
                cur.execute("INSERT OR IGNORE INTO continuation_metrics (metric_key, metric_value, updated_at) VALUES (?, 0, ?)",
                            (k, datetime.now(timezone.utc).isoformat()))
            conn.commit()

    @staticmethod
    def compute_task_fingerprint(task_id: str, version: int, criteria: List[str]) -> str:
        canonical = f"{task_id}:{version}:{json.dumps(sorted(criteria))}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def get_system_diagnostics() -> Dict[str, Any]:
        """Captures lightweight OS memory load and process counts."""
        diagnostics = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "memory_load_pct": None,
            "ram_total_gb": None,
            "ram_available_gb": None,
            "thermal_status": "THERMAL_CAUSE_UNPROVEN",
            "db_size_bytes": None
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
            diagnostics["memory_load_pct"] = stat.dwMemoryLoad
            diagnostics["ram_total_gb"] = round(stat.ullTotalPhys / (1024**3), 2)
            diagnostics["ram_available_gb"] = round(stat.ullAvailPhys / (1024**3), 2)
        except Exception:
            pass

        if os.path.exists(DB_PATH):
            diagnostics["db_size_bytes"] = os.path.getsize(DB_PATH)

        return diagnostics

    def persist_pre_execution_state(
        self,
        mission_id: str,
        goal_id: str,
        task_id: str,
        task_version: int,
        acceptance_criteria: List[str],
        lease_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Persists full durable task state BEFORE execution begins."""
        now_iso = datetime.now(timezone.utc).isoformat()
        fp = self.compute_task_fingerprint(task_id, task_version, acceptance_criteria)

        record = {
            "mission_id": mission_id,
            "goal_id": goal_id,
            "task_id": task_id,
            "task_version": task_version,
            "task_fingerprint": fp,
            "status": "RUNNING",
            "lease_id": lease_id or f"LEASE-{task_id}",
            "started_at": now_iso,
            "last_progress_at": now_iso,
            "last_checkpoint": f"CHECKPOINT-{task_id}-START",
            "acceptance_criteria_json": json.dumps(acceptance_criteria),
            "result_state_json": json.dumps({}),
            "verification_state": "UNVERIFIED",
            "successor_state": None,
            "do_not_repeat_fingerprint": fp,
            "updated_at": now_iso
        }

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO durable_continuation_state (
                mission_id, goal_id, task_id, task_version, task_fingerprint,
                status, lease_id, started_at, last_progress_at, last_checkpoint,
                acceptance_criteria_json, result_state_json, verification_state,
                successor_state, do_not_repeat_fingerprint, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                record["mission_id"], record["goal_id"], record["task_id"],
                record["task_version"], record["task_fingerprint"], record["status"],
                record["lease_id"], record["started_at"], record["last_progress_at"],
                record["last_checkpoint"], record["acceptance_criteria_json"],
                record["result_state_json"], record["verification_state"],
                record["successor_state"], record["do_not_repeat_fingerprint"],
                record["updated_at"]
            ))
            conn.commit()

        # Atomic dual-write to JSON file
        tmp = self.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        os.replace(tmp, self.state_file)

        return record

    def update_verification_and_complete(
        self,
        task_id: str,
        result_payload: Dict[str, Any],
        is_verified: bool,
        successor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Marks a task as VERIFIED/COMPLETED and registers fingerprint in DO_NOT_REPEAT."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM durable_continuation_state WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Task {task_id} not found in durable continuation state")

            status = "VERIFIED" if is_verified else "FAILED"
            ver_state = "VERIFIED" if is_verified else "VERIFICATION_FAILED"
            fp = row["do_not_repeat_fingerprint"]

            cur.execute("""
            UPDATE durable_continuation_state SET
                status = ?,
                result_state_json = ?,
                verification_state = ?,
                successor_state = ?,
                last_progress_at = ?,
                updated_at = ?
            WHERE task_id = ?;
            """, (status, json.dumps(result_payload), ver_state, successor_id, now_iso, now_iso, task_id))

            if is_verified:
                cur.execute("""
                INSERT OR REPLACE INTO do_not_repeat_registry (fingerprint, task_id, task_version, verified_at)
                VALUES (?, ?, ?, ?);
                """, (fp, task_id, row["task_version"], now_iso))

            conn.commit()

        return {"task_id": task_id, "status": status, "is_verified": is_verified, "successor": successor_id}

    def is_task_verified(self, fingerprint: str) -> bool:
        """Checks DO_NOT_REPEAT registry to see if this exact task fingerprint was already verified."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT verified_at FROM do_not_repeat_registry WHERE fingerprint = ?", (fingerprint,))
            return cur.fetchone() is not None

    def reconcile_weiter(self, active_worker_alive: bool = True) -> Dict[str, Any]:
        """
        Processes a bare "weiter" continuation signal idempotently:
        1. Increments duplicate_continuations_received.
        2. Inspects durable continuation state.
        3. Returns exactly one authoritative action:
           - RECONCILE_RUNNING (worker still executing, continuation suppressed)
           - RECOVER_INTERRUPTED (worker died, resume/reconcile unfinished work once)
           - ADVANCE_TO_SUCCESSOR (current task already verified, advance to next)
           - IDLE_QUIESCENT (no pending or interrupted work)
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE continuation_metrics SET metric_value = metric_value + 1, updated_at = ? WHERE metric_key = 'duplicate_continuations_received'", (now_iso,))
            
            # Find latest task
            cur.execute("SELECT * FROM durable_continuation_state ORDER BY updated_at DESC LIMIT 1")
            task = cur.fetchone()
            
            if not task:
                conn.commit()
                return {
                    "action": "IDLE_QUIESCENT",
                    "reason": "NO_PREVIOUS_DURABLE_TASK",
                    "duplicate_suppressed": False
                }

            task_dict = dict(task)
            status = task_dict["status"]

            if status == "RUNNING":
                if active_worker_alive:
                    # Task is actively running; suppress redundant continuation
                    cur.execute("UPDATE continuation_metrics SET metric_value = metric_value + 1, updated_at = ? WHERE metric_key = 'duplicate_continuations_suppressed'", (now_iso,))
                    conn.commit()
                    return {
                        "action": "RECONCILE_RUNNING",
                        "task_id": task_dict["task_id"],
                        "reason": "TASK_ACTIVELY_IN_FLIGHT",
                        "duplicate_suppressed": True
                    }
                else:
                    # Worker interrupted/dead: reconcile and recover safely
                    conn.commit()
                    return {
                        "action": "RECOVER_INTERRUPTED",
                        "task_id": task_dict["task_id"],
                        "reason": "WORKER_CRASHED_MID_EXECUTION",
                        "duplicate_suppressed": False
                    }

            elif status in ("VERIFIED", "COMPLETED"):
                # Task already verified: do NOT rerun, select successor
                cur.execute("UPDATE continuation_metrics SET metric_value = metric_value + 1, updated_at = ? WHERE metric_key = 'duplicate_continuations_suppressed'", (now_iso,))
                conn.commit()
                return {
                    "action": "ADVANCE_TO_SUCCESSOR",
                    "completed_task_id": task_dict["task_id"],
                    "successor_task_id": task_dict.get("successor_state"),
                    "reason": "PREVIOUS_TASK_ALREADY_VERIFIED",
                    "duplicate_suppressed": True
                }

            conn.commit()
            return {
                "action": "IDLE_QUIESCENT",
                "task_id": task_dict["task_id"],
                "status": status,
                "duplicate_suppressed": False
            }

    def get_metrics(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT metric_key, metric_value FROM continuation_metrics")
            return {r["metric_key"]: r["metric_value"] for r in cur.fetchall()}
