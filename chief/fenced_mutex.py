"""
fenced_mutex.py - Automated Conflict Resolution & Resource Mutex Lease Stealing Guard
Part of TASK-WIN-64: Automated Conflict Resolution & Resource Mutex Lease Stealing Guard.

Provides distributed resource locking with monotonic fencing tokens (epochs),
safe lease stealing with liveness verification, split-brain preemption guards,
and cryptographic event auditing.
"""

import os
import sys
import time
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
DB_PATH = os.path.join(WORKSPACE_ROOT, "courier", "chief_control_plane.db")

def _safe_is_pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == 259
                return False
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False

class FencedMutexManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fenced_resource_locks (
                resource_id TEXT PRIMARY KEY,
                holder_id TEXT NOT NULL,
                holder_host TEXT NOT NULL,
                holder_pid INTEGER,
                epoch INTEGER NOT NULL,
                lease_token TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_heartbeat_at TEXT NOT NULL,
                state TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fenced_mutex_events (
                event_id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                holder_id TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _calc_token(resource_id: str, holder_id: str, epoch: int, timestamp: str) -> str:
        raw = f"{resource_id}:{holder_id}:{epoch}:{timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _record_event_tx(self, cursor: sqlite3.Cursor, resource_id: str, event_type: str, holder_id: str, epoch: int, payload: Dict[str, Any]):
        event_id = f"EVT-MUTEX-{int(time.time() * 1000)}-{os.urandom(3).hex()}"
        now_iso = self._now_iso()
        cursor.execute("""
        INSERT INTO fenced_mutex_events (event_id, resource_id, event_type, holder_id, epoch, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (event_id, resource_id, event_type, holder_id, epoch, json.dumps(payload), now_iso))

    def acquire(
        self,
        resource_id: str,
        holder_id: str,
        holder_host: str = "WINDOWS",
        holder_pid: Optional[int] = None,
        ttl_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Acquires or re-enters a fenced mutex.
        If locked and expired, triggers safe stealing guard.
        """
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        expires_dt = datetime.fromtimestamp(now_dt.timestamp() + ttl_seconds, tz=timezone.utc)
        expires_iso = expires_dt.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT * FROM fenced_resource_locks WHERE resource_id = ?", (resource_id,))
                row = cursor.fetchone()

                if not row or row["state"] == "RELEASED":
                    # Clean acquisition
                    prev_epoch = row["epoch"] if row else 0
                    new_epoch = prev_epoch + 1
                    token = self._calc_token(resource_id, holder_id, new_epoch, now_iso)

                    cursor.execute("""
                    INSERT OR REPLACE INTO fenced_resource_locks (
                        resource_id, holder_id, holder_host, holder_pid,
                        epoch, lease_token, acquired_at, expires_at, last_heartbeat_at, state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
                    """, (resource_id, holder_id, holder_host, holder_pid, new_epoch, token, now_iso, expires_iso, now_iso))

                    self._record_event_tx(cursor, resource_id, "MUTEX_ACQUIRED", holder_id, new_epoch, {
                        "host": holder_host,
                        "pid": holder_pid,
                        "expires_at": expires_iso
                    })
                    cursor.execute("COMMIT;")
                    return {
                        "acquired": True,
                        "status": "ACQUIRED",
                        "resource_id": resource_id,
                        "holder_id": holder_id,
                        "epoch": new_epoch,
                        "lease_token": token,
                        "expires_at": expires_iso
                    }

                # Reentrant check
                if row["holder_id"] == holder_id and row["holder_host"] == holder_host:
                    token = row["lease_token"]
                    epoch = row["epoch"]
                    cursor.execute("""
                    UPDATE fenced_resource_locks SET
                        expires_at = ?, last_heartbeat_at = ?, state = 'ACTIVE'
                    WHERE resource_id = ?;
                    """, (expires_iso, now_iso, resource_id))

                    self._record_event_tx(cursor, resource_id, "MUTEX_REENTERED", holder_id, epoch, {
                        "expires_at": expires_iso
                    })
                    cursor.execute("COMMIT;")
                    return {
                        "acquired": True,
                        "status": "REENTERED",
                        "resource_id": resource_id,
                        "holder_id": holder_id,
                        "epoch": epoch,
                        "lease_token": token,
                        "expires_at": expires_iso
                    }

                # Lock held by someone else
                if row["expires_at"] > now_iso and row["state"] == "ACTIVE":
                    cursor.execute("COMMIT;")
                    return {
                        "acquired": False,
                        "status": "CONFLICT_HELD",
                        "resource_id": resource_id,
                        "held_by": row["holder_id"],
                        "held_host": row["holder_host"],
                        "epoch": row["epoch"],
                        "expires_at": row["expires_at"]
                    }

                # Lock exists but is expired: delegate to stealing protocol
                cursor.execute("COMMIT;")
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

        # Attempt steal outside the transaction
        return self.attempt_steal(
            resource_id=resource_id,
            candidate_id=holder_id,
            candidate_host=holder_host,
            candidate_pid=holder_pid,
            ttl_seconds=ttl_seconds
        )

    def renew(
        self,
        resource_id: str,
        holder_id: str,
        lease_token: str,
        ttl_seconds: int = 30
    ) -> Dict[str, Any]:
        """Extends an active lease if the token and holder match."""
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        expires_dt = datetime.fromtimestamp(now_dt.timestamp() + ttl_seconds, tz=timezone.utc)
        expires_iso = expires_dt.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT * FROM fenced_resource_locks WHERE resource_id = ?", (resource_id,))
                row = cursor.fetchone()

                if not row:
                    cursor.execute("COMMIT;")
                    return {"renewed": False, "error": "LOCK_NOT_FOUND"}

                if row["state"] == "PREEMPTED":
                    cursor.execute("COMMIT;")
                    return {"renewed": False, "error": "LEASE_PREEMPTED", "current_epoch": row["epoch"]}

                if row["holder_id"] != holder_id or row["lease_token"] != lease_token:
                    cursor.execute("COMMIT;")
                    return {"renewed": False, "error": "TOKEN_MISMATCH", "current_epoch": row["epoch"]}

                epoch = row["epoch"]
                cursor.execute("""
                UPDATE fenced_resource_locks SET
                    expires_at = ?, last_heartbeat_at = ?
                WHERE resource_id = ?;
                """, (expires_iso, now_iso, resource_id))

                self._record_event_tx(cursor, resource_id, "MUTEX_RENEWED", holder_id, epoch, {
                    "expires_at": expires_iso
                })
                cursor.execute("COMMIT;")
                return {
                    "renewed": True,
                    "resource_id": resource_id,
                    "holder_id": holder_id,
                    "epoch": epoch,
                    "expires_at": expires_iso
                }
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def release(
        self,
        resource_id: str,
        holder_id: str,
        lease_token: str
    ) -> Dict[str, Any]:
        """Voluntarily releases a held mutex."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT * FROM fenced_resource_locks WHERE resource_id = ?", (resource_id,))
                row = cursor.fetchone()

                if not row:
                    cursor.execute("COMMIT;")
                    return {"released": True, "message": "NO_LOCK_EXISTED"}

                if row["holder_id"] != holder_id or row["lease_token"] != lease_token:
                    cursor.execute("COMMIT;")
                    return {"released": False, "error": "NOT_HOLDER_OR_INVALID_TOKEN"}

                epoch = row["epoch"]
                cursor.execute("UPDATE fenced_resource_locks SET state = 'RELEASED' WHERE resource_id = ?", (resource_id,))
                self._record_event_tx(cursor, resource_id, "MUTEX_RELEASED", holder_id, epoch, {})
                cursor.execute("COMMIT;")
                return {"released": True, "resource_id": resource_id, "epoch": epoch}
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def validate_fencing_token(
        self,
        resource_id: str,
        holder_id: str,
        lease_token: str,
        epoch: int
    ) -> Dict[str, Any]:
        """
        CRITICAL SPLIT-BRAIN FENCING GUARD:
        Verifies that a worker's token and epoch are still authoritative.
        Any preempted worker attempting to write is immediately blocked.
        """
        now_iso = self._now_iso()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fenced_resource_locks WHERE resource_id = ?", (resource_id,))
            row = cursor.fetchone()

            if not row:
                return {"valid": False, "reason": "LOCK_NOT_FOUND"}

            if row["state"] != "ACTIVE":
                return {"valid": False, "reason": f"LOCK_INACTIVE_STATE_{row['state']}", "current_epoch": row["epoch"]}

            if row["epoch"] != epoch:
                return {"valid": False, "reason": "STALE_EPOCH", "current_epoch": row["epoch"], "presented_epoch": epoch}

            if row["holder_id"] != holder_id or row["lease_token"] != lease_token:
                return {"valid": False, "reason": "TOKEN_OR_HOLDER_MISMATCH"}

            if row["expires_at"] < now_iso:
                return {"valid": False, "reason": "LEASE_EXPIRED", "expired_at": row["expires_at"]}

            return {
                "valid": True,
                "resource_id": resource_id,
                "holder_id": holder_id,
                "epoch": epoch,
                "remaining_ttl_sec": (datetime.fromisoformat(row["expires_at"]) - datetime.now(timezone.utc)).total_seconds()
            }

    def attempt_steal(
        self,
        resource_id: str,
        candidate_id: str,
        candidate_host: str = "WINDOWS",
        candidate_pid: Optional[int] = None,
        ttl_seconds: int = 30,
        grace_period_sec: float = 2.0
    ) -> Dict[str, Any]:
        """
        Steals an expired or abandoned lease with strict liveness verification:
        1. Checks if lease has expired.
        2. If local process: checks os.kill(pid, 0) for ESRCH.
        3. If remote: ensures grace period has elapsed.
        4. Increments epoch to fence off old holder.
        """
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        now_ts = now_dt.timestamp()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT * FROM fenced_resource_locks WHERE resource_id = ?", (resource_id,))
                row = cursor.fetchone()

                if not row:
                    cursor.execute("COMMIT;")
                    return self.acquire(resource_id, candidate_id, candidate_host, candidate_pid, ttl_seconds)

                exp_dt = datetime.fromisoformat(row["expires_at"])
                exp_ts = exp_dt.timestamp()

                # Rule 1: Cannot steal unexpired active lease
                if exp_ts > now_ts and row["state"] == "ACTIVE":
                    cursor.execute("COMMIT;")
                    return {
                        "acquired": False,
                        "status": "STEAL_REJECTED_STILL_ACTIVE",
                        "held_by": row["holder_id"],
                        "expires_at": row["expires_at"],
                        "remaining_sec": exp_ts - now_ts
                    }

                # Rule 2: Liveness check for local holder
                holder_dead = False
                steal_reason = "LEASE_EXPIRED"
                
                if row["holder_host"] == candidate_host and row["holder_pid"]:
                    if _safe_is_pid_alive(row["holder_pid"]):
                        # Process is alive: must respect grace period
                        if (now_ts - exp_ts) < grace_period_sec:
                            cursor.execute("COMMIT;")
                            return {
                                "acquired": False,
                                "status": "STEAL_REJECTED_LOCAL_PROCESS_ALIVE",
                                "holder_pid": row["holder_pid"],
                                "held_by": row["holder_id"]
                            }
                        steal_reason = "LOCAL_PROCESS_HELD_PAST_GRACE"
                    else:
                        holder_dead = True
                        steal_reason = "LOCAL_PROCESS_DEAD_ESRCH"
                else:
                    # Remote holder: require grace period after expiration
                    if (now_ts - exp_ts) < grace_period_sec:
                        cursor.execute("COMMIT;")
                        return {
                            "acquired": False,
                            "status": "STEAL_REJECTED_REMOTE_GRACE_ACTIVE",
                            "held_by": row["holder_id"],
                            "held_host": row["holder_host"]
                        }
                    steal_reason = "REMOTE_LEASE_EXPIRED_PAST_GRACE"

                # Execute Steal & Increment Fencing Token (Epoch)
                old_holder = row["holder_id"]
                old_epoch = row["epoch"]
                new_epoch = old_epoch + 1
                new_token = self._calc_token(resource_id, candidate_id, new_epoch, now_iso)
                new_expires_dt = datetime.fromtimestamp(now_ts + ttl_seconds, tz=timezone.utc)
                new_expires_iso = new_expires_dt.isoformat()

                cursor.execute("""
                UPDATE fenced_resource_locks SET
                    holder_id = ?, holder_host = ?, holder_pid = ?,
                    epoch = ?, lease_token = ?, acquired_at = ?,
                    expires_at = ?, last_heartbeat_at = ?, state = 'ACTIVE'
                WHERE resource_id = ?;
                """, (candidate_id, candidate_host, candidate_pid, new_epoch, new_token, now_iso, new_expires_iso, now_iso, resource_id))

                self._record_event_tx(cursor, resource_id, "MUTEX_STOLEN", candidate_id, new_epoch, {
                    "previous_holder": old_holder,
                    "previous_epoch": old_epoch,
                    "steal_reason": steal_reason,
                    "holder_dead": holder_dead,
                    "expires_at": new_expires_iso
                })
                cursor.execute("COMMIT;")

                return {
                    "acquired": True,
                    "status": "STOLEN_SAFELY",
                    "steal_reason": steal_reason,
                    "resource_id": resource_id,
                    "previous_holder": old_holder,
                    "holder_id": candidate_id,
                    "epoch": new_epoch,
                    "lease_token": new_token,
                    "expires_at": new_expires_iso
                }
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def get_lock(self, resource_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fenced_resource_locks WHERE resource_id = ?", (resource_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_active_locks(self) -> list:
        now_iso = self._now_iso()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM fenced_resource_locks
            WHERE state = 'ACTIVE' AND expires_at > ?
            ORDER BY acquired_at ASC;
            """, (now_iso,))
            return [dict(r) for r in cursor.fetchall()]
