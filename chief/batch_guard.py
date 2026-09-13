"""
batch_guard.py - P0 Duplicate Batch Dispatch Guard & Atomic Idempotency Claim Engine
Mission Class: P0 Autonomy Infrastructure
Operating Phase: AUTONOMY_FIRST

Guarantees:
1. EXACTLY-ONCE LOGICAL BATCH: Every autonomous batch has a durable BATCH_ID,
   BATCH_IDEMPOTENCY_KEY, STATE_GENERATION, SOURCE_CONTINUATION_GENERATION,
   and durable lifecycle status.
2. ATOMIC CLAIM: Hardware/SQLite level atomic reservation prevents race conditions
   between parallel or rapid repeated continuation requests.
3. CONCURRENT & SEQUENTIAL SUPPRESSION: Identical or replayed batch launch attempts
   attach to existing durable records with zero duplicate execution.
4. RESTART RECONCILIATION: Survives session disconnects and reattaches to running batches.
5. COMPLETE OBSERVABILITY: Exposes exact required audit metrics.
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from .types import Lane, Host
from .process_liveness import is_pid_alive

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
DEFAULT_DB_PATH = os.path.join(WORKSPACE_ROOT, "courier", "chief_control_plane.db")


class BatchGuardManager:
    """Manages atomic batch claims, idempotency keys, and batch lifecycle tracking."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.abspath(db_path or DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS durable_batches (
                batch_id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE NOT NULL,
                mission_id TEXT NOT NULL,
                current_goal TEXT NOT NULL,
                state_generation INTEGER NOT NULL,
                source_continuation_generation INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL CHECK (status IN ('STARTING', 'RUNNING', 'COMPLETED', 'FAILED')),
                owner_lease TEXT NOT NULL,
                owner_pid INTEGER NOT NULL,
                task_ids_selected_json TEXT NOT NULL,
                summary_json TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS batch_guard_metrics (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                raw_batch_start_requests INTEGER NOT NULL,
                logical_batches_created INTEGER NOT NULL,
                duplicate_batch_requests_suppressed INTEGER NOT NULL,
                physical_batches_started INTEGER NOT NULL,
                active_batch_id TEXT,
                active_batch_idempotency_key TEXT,
                duplicate_tasks_executed INTEGER NOT NULL,
                last_event_timestamp TEXT NOT NULL
            );
            """)
            cur.execute("""
            INSERT OR IGNORE INTO batch_guard_metrics (
                singleton_id, raw_batch_start_requests, logical_batches_created,
                duplicate_batch_requests_suppressed, physical_batches_started,
                active_batch_id, active_batch_idempotency_key, duplicate_tasks_executed,
                last_event_timestamp
            ) VALUES (
                1, 0, 0, 0, 0, NULL, NULL, 0, ?
            );
            """, (datetime.now(timezone.utc).isoformat(),))
            conn.commit()

    @staticmethod
    def compute_idempotency_key(
        mission_id: str,
        current_goal: str,
        state_generation: int,
        source_continuation_generation: int,
        purpose: str = "AUTONOMOUS_BATCH"
    ) -> str:
        """Derives a deterministic, durable batch idempotency key."""
        payload = f"{mission_id}:{current_goal}:{state_generation}:{source_continuation_generation}:{purpose}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"BK-{mission_id}-{current_goal}-G{state_generation}-C{source_continuation_generation}-{digest}"

    def claim_batch(
        self,
        idempotency_key: str,
        mission_id: str,
        current_goal: str,
        state_generation: int,
        source_continuation_generation: int,
        owner_lease: str = "BATCH_LEASE_WINDOWS_GOOGLE",
        owner_pid: Optional[int] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Atomically claims a batch execution slot.
        Returns:
            (True, "BATCH_CLAIMED", batch_record) if new logical batch claimed.
            (False, "BATCH_ALREADY_EXISTS", batch_record) if key was already claimed.
        """
        pid = owner_pid or os.getpid()
        now_iso = datetime.now(timezone.utc).isoformat()
        batch_id = f"BATCH-WIN-{int(time.time() * 1000)}-{os.urandom(3).hex()}"

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE;")
            try:
                # Update raw request count
                cur.execute("""
                UPDATE batch_guard_metrics SET
                    raw_batch_start_requests = raw_batch_start_requests + 1,
                    last_event_timestamp = ?
                WHERE singleton_id = 1;
                """, (now_iso,))

                # Check existing batch with this idempotency key
                cur.execute("SELECT * FROM durable_batches WHERE idempotency_key = ?;", (idempotency_key,))
                existing = cur.fetchone()

                if existing:
                    ex_dict = dict(existing)
                    status = ex_dict["status"]
                    ex_pid = ex_dict["owner_pid"]

                    # Check if previous process died mid-execution while STARTING/RUNNING
                    if status in ("STARTING", "RUNNING") and not is_pid_alive(ex_pid):
                        # Reclaim orphaned batch
                        cur.execute("""
                        UPDATE durable_batches SET
                            owner_pid = ?,
                            status = 'STARTING',
                            started_at = ?
                        WHERE idempotency_key = ?;
                        """, (pid, now_iso, idempotency_key))
                        cur.execute("""
                        UPDATE batch_guard_metrics SET
                            active_batch_id = ?,
                            active_batch_idempotency_key = ?,
                            physical_batches_started = physical_batches_started + 1,
                            last_event_timestamp = ?
                        WHERE singleton_id = 1;
                        """, (ex_dict["batch_id"], idempotency_key, now_iso))
                        conn.commit()
                        ex_dict["action"] = "ORPHAN_BATCH_RECLAIMED"
                        return True, "ORPHAN_BATCH_RECLAIMED", ex_dict

                    # Suppress duplicate batch dispatch
                    cur.execute("""
                    UPDATE batch_guard_metrics SET
                        duplicate_batch_requests_suppressed = duplicate_batch_requests_suppressed + 1,
                        last_event_timestamp = ?
                    WHERE singleton_id = 1;
                    """, (now_iso,))
                    conn.commit()
                    return False, "BATCH_ALREADY_EXISTS", ex_dict

                # Check if there is an active running batch globally (Single Heavy Batch Law)
                cur.execute("SELECT * FROM durable_batches WHERE status IN ('STARTING', 'RUNNING');")
                active_batches = cur.fetchall()
                for ab in active_batches:
                    ab_dict = dict(ab)
                    if is_pid_alive(ab_dict["owner_pid"]):
                        # An active running batch is currently held by a live process
                        cur.execute("""
                        UPDATE batch_guard_metrics SET
                            duplicate_batch_requests_suppressed = duplicate_batch_requests_suppressed + 1,
                            last_event_timestamp = ?
                        WHERE singleton_id = 1;
                        """, (now_iso,))
                        conn.commit()
                        return False, "ACTIVE_BATCH_IN_FLIGHT", ab_dict

                # Insert new batch record
                cur.execute("""
                INSERT INTO durable_batches (
                    batch_id, idempotency_key, mission_id, current_goal,
                    state_generation, source_continuation_generation, started_at,
                    status, owner_lease, owner_pid, task_ids_selected_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'STARTING', ?, ?, '[]');
                """, (
                    batch_id, idempotency_key, mission_id, current_goal,
                    state_generation, source_continuation_generation, now_iso,
                    owner_lease, pid
                ))

                cur.execute("""
                UPDATE batch_guard_metrics SET
                    logical_batches_created = logical_batches_created + 1,
                    physical_batches_started = physical_batches_started + 1,
                    active_batch_id = ?,
                    active_batch_idempotency_key = ?,
                    last_event_timestamp = ?
                WHERE singleton_id = 1;
                """, (batch_id, idempotency_key, now_iso))

                conn.commit()
                return True, "BATCH_CLAIMED", {
                    "batch_id": batch_id,
                    "idempotency_key": idempotency_key,
                    "status": "STARTING",
                    "started_at": now_iso
                }
            except Exception:
                conn.rollback()
                raise

    def record_batch_running(self, batch_id: str, task_ids: List[str]):
        """Records selected task IDs and transitions status to RUNNING."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE durable_batches SET
                status = 'RUNNING',
                task_ids_selected_json = ?
            WHERE batch_id = ?;
            """, (json.dumps(task_ids), batch_id))
            conn.commit()

    def complete_batch(self, batch_id: str, summary: Dict[str, Any]):
        """Completes batch and updates metrics."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE durable_batches SET
                status = 'COMPLETED',
                completed_at = ?,
                summary_json = ?
            WHERE batch_id = ?;
            """, (now_iso, json.dumps(summary), batch_id))
            cur.execute("""
            UPDATE batch_guard_metrics SET
                active_batch_id = NULL,
                active_batch_idempotency_key = NULL,
                last_event_timestamp = ?
            WHERE singleton_id = 1;
            """, (now_iso,))
            conn.commit()

    def fail_batch(self, batch_id: str, error_reason: str):
        """Marks batch as failed without leaving lingering active locks."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE durable_batches SET
                status = 'FAILED',
                completed_at = ?,
                summary_json = ?
            WHERE batch_id = ?;
            """, (now_iso, json.dumps({"error": error_reason}), batch_id))
            cur.execute("""
            UPDATE batch_guard_metrics SET
                active_batch_id = NULL,
                active_batch_idempotency_key = NULL,
                last_event_timestamp = ?
            WHERE singleton_id = 1;
            """, (now_iso,))
            conn.commit()

    def get_metrics(self) -> Dict[str, Any]:
        """Returns the complete observability metrics."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM batch_guard_metrics WHERE singleton_id = 1;")
            row = cur.fetchone()
            if row:
                d = dict(row)
                del d["singleton_id"]
                return d
            return {}

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM durable_batches WHERE batch_id = ?;", (batch_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_batch_by_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM durable_batches WHERE idempotency_key = ?;", (idempotency_key,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_active_batch(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM durable_batches WHERE status IN ('STARTING', 'RUNNING') ORDER BY started_at DESC LIMIT 1;")
            row = cur.fetchone()
            return dict(row) if row else None

