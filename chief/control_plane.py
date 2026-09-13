"""
control_plane.py - Canonical SQLite Control Plane for Courier Chief
Enforces WAL mode, synchronous=FULL, BEGIN IMMEDIATE, and durable event ledgers.
"""

import os
import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union

from .types import (
    Lane, Host, TaskStatus, FindingStatus, FindingSeverity,
    PatchStatus, RegisteredFinding, RegisteredPatch, TwoLevelDone
)


DEFAULT_DB_PATH = r"C:\Users\lol\2026-workspace\courier\chief_control_plane.db"


class ControlPlane:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.abspath(db_path or DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=10.0,
            isolation_level=None  # Managed manually via BEGIN IMMEDIATE
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = FULL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                # 1. Handoffs
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    origin_lane TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    host_os TEXT NOT NULL,
                    mac_host_access INTEGER NOT NULL,
                    production_write_authority INTEGER NOT NULL,
                    sha256_hash TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    ingested_at TEXT NOT NULL
                );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_handoffs_lane ON handoffs(origin_lane);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_handoffs_hash ON handoffs(sha256_hash);")

                # 2. Findings Registry
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    origin_lane TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reproduction_ref TEXT,
                    evidence_hash TEXT,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);")

                # 3. Patches Registry
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS patches (
                    patch_id TEXT PRIMARY KEY,
                    batch_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT NOT NULL,
                    target_files_json TEXT NOT NULL,
                    reproduction_scripts_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)

                # 4. Canonical Tasks & Two-Level Done
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    origin_lane TEXT NOT NULL,
                    status TEXT NOT NULL,
                    local_step_erledigt INTEGER NOT NULL,
                    gesamtaufgabe_erledigt INTEGER NOT NULL,
                    blocker TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    active_agent TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)

                # 5. Cross-Machine Single Writer Locks
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS resource_locks (
                    resource_id TEXT PRIMARY KEY,
                    held_by_lane TEXT NOT NULL,
                    held_by_host TEXT NOT NULL,
                    lock_type TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                """)

                # 6. Outbound Dispatch Queue (Zero-Copy Inter-Agent Bus)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_queue (
                    dispatch_id TEXT PRIMARY KEY,
                    target_lane TEXT NOT NULL,
                    target_host TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    source_lane TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    dispatched_at TEXT
                );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_queue(status);")

                # 7. Tamper-Evident Event Ledger
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_ledger (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    lane TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    delta_json TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                """)

                # 8. Checkpoints (Section 8 Exactly-Once & Durable Resume)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_key TEXT PRIMARY KEY,
                    checkpoint_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)

                cursor.execute("PRAGMA user_version = 14;")
                cursor.execute("COMMIT;")
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def record_handoff(
        self,
        handoff_id: str,
        source_file: str,
        origin_lane: Lane,
        assignment_id: str,
        role: str,
        timestamp_utc: str,
        host_os: Host,
        mac_host_access: bool,
        production_write_authority: bool,
        sha256_hash: str,
        payload: Dict[str, Any],
        validation_status: str = "VERIFIED"
    ) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload, ensure_ascii=False)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                # Check if hash already recorded
                cursor.execute("SELECT handoff_id FROM handoffs WHERE sha256_hash = ?", (sha256_hash,))
                row = cursor.fetchone()
                if row:
                    cursor.execute("COMMIT;")
                    return False  # Already ingested

                cursor.execute("""
                INSERT INTO handoffs (
                    handoff_id, source_file, origin_lane, assignment_id,
                    role, timestamp_utc, host_os, mac_host_access,
                    production_write_authority, sha256_hash, payload_json,
                    validation_status, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    handoff_id, source_file, origin_lane.value, assignment_id,
                    role, timestamp_utc, host_os.value, 1 if mac_host_access else 0,
                    1 if production_write_authority else 0, sha256_hash, payload_str,
                    validation_status, now_iso
                ))

                self._record_event_tx(cursor, "HANDOFF_INGESTED", origin_lane.value, handoff_id, {
                    "source_file": source_file,
                    "assignment_id": assignment_id,
                    "sha256_hash": sha256_hash
                })

                cursor.execute("COMMIT;")
                return True
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def upsert_finding(
        self,
        finding_id: str,
        origin_lane: Lane,
        title: str,
        status: FindingStatus,
        severity: FindingSeverity,
        description: str,
        reproduction_ref: Optional[str] = None,
        evidence_hash: Optional[str] = None
    ) -> str:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT status FROM findings WHERE finding_id = ?", (finding_id,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                    UPDATE findings SET
                        status = ?, severity = ?, description = ?,
                        reproduction_ref = COALESCE(?, reproduction_ref),
                        evidence_hash = COALESCE(?, evidence_hash),
                        updated_at = ?
                    WHERE finding_id = ?;
                    """, (status.value, severity.value, description, reproduction_ref, evidence_hash, now_iso, finding_id))
                    action = "UPDATED"
                else:
                    cursor.execute("""
                    INSERT INTO findings (
                        finding_id, origin_lane, title, status, severity,
                        description, reproduction_ref, evidence_hash,
                        first_seen_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        finding_id, origin_lane.value, title, status.value, severity.value,
                        description, reproduction_ref, evidence_hash, now_iso, now_iso
                    ))
                    action = "CREATED"

                self._record_event_tx(cursor, f"FINDING_{action}", origin_lane.value, finding_id, {
                    "status": status.value,
                    "severity": severity.value,
                    "action": action
                })
                cursor.execute("COMMIT;")
                return action
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def upsert_patch(
        self,
        patch_id: str,
        batch_name: str,
        status: PatchStatus,
        description: str,
        target_files: List[str],
        reproduction_scripts: List[str]
    ) -> str:
        now_iso = datetime.now(timezone.utc).isoformat()
        target_json = json.dumps(target_files)
        repro_json = json.dumps(reproduction_scripts)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT status FROM patches WHERE patch_id = ?", (patch_id,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                    UPDATE patches SET
                        batch_name = ?, status = ?, description = ?,
                        target_files_json = ?, reproduction_scripts_json = ?,
                        updated_at = ?
                    WHERE patch_id = ?;
                    """, (batch_name, status.value, description, target_json, repro_json, now_iso, patch_id))
                    action = "UPDATED"
                else:
                    cursor.execute("""
                    INSERT INTO patches (
                        patch_id, batch_name, status, description,
                        target_files_json, reproduction_scripts_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (patch_id, batch_name, status.value, description, target_json, repro_json, now_iso, now_iso))
                    action = "CREATED"

                self._record_event_tx(cursor, f"PATCH_{action}", "CHIEF", patch_id, {
                    "batch_name": batch_name,
                    "status": status.value
                })
                cursor.execute("COMMIT;")
                return action
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def upsert_task(
        self,
        task_id: str,
        assignment_id: str,
        origin_lane: Lane,
        status: TaskStatus,
        two_level_done: TwoLevelDone,
        active_agent: str = "CHIEF"
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT task_id FROM tasks WHERE task_id = ? OR assignment_id = ?", (task_id, assignment_id))
                existing = cursor.fetchone()
                if existing:
                    resolved_task_id = existing["task_id"]
                    cursor.execute("""
                    UPDATE tasks SET
                        assignment_id = ?, status = ?, local_step_erledigt = ?,
                        gesamtaufgabe_erledigt = ?, blocker = ?, next_step = ?,
                        active_agent = ?, updated_at = ?
                    WHERE task_id = ?;
                    """, (
                        assignment_id, status.value,
                        1 if two_level_done.local_step_erledigt else 0,
                        1 if two_level_done.gesamtaufgabe_erledigt else 0,
                        two_level_done.blocker, two_level_done.next_step,
                        active_agent, now_iso, resolved_task_id
                    ))
                else:
                    cursor.execute("""
                    INSERT INTO tasks (
                        task_id, assignment_id, origin_lane, status,
                        local_step_erledigt, gesamtaufgabe_erledigt,
                        blocker, next_step, active_agent, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        task_id, assignment_id, origin_lane.value, status.value,
                        1 if two_level_done.local_step_erledigt else 0,
                        1 if two_level_done.gesamtaufgabe_erledigt else 0,
                        two_level_done.blocker, two_level_done.next_step,
                        active_agent, now_iso, now_iso
                    ))

                self._record_event_tx(cursor, "TASK_STATE_CHANGED", origin_lane.value, task_id, {
                    "status": status.value,
                    "local_step_erledigt": two_level_done.local_step_erledigt,
                    "gesamtaufgabe_erledigt": two_level_done.gesamtaufgabe_erledigt,
                    "blocker": two_level_done.blocker
                })
                cursor.execute("COMMIT;")
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def acquire_lock(
        self,
        resource_id: str,
        lane: Lane,
        host: Host,
        lock_type: str = "WRITE",
        ttl_seconds: int = 300
    ) -> Tuple[bool, str]:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        expires_dt = datetime.fromtimestamp(now_dt.timestamp() + ttl_seconds, tz=timezone.utc)
        expires_iso = expires_dt.isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT held_by_lane, held_by_host, expires_at FROM resource_locks WHERE resource_id = ?", (resource_id,))
                row = cursor.fetchone()
                if row:
                    held_lane = row["held_by_lane"]
                    held_host = row["held_by_host"]
                    exp_iso = row["expires_at"]
                    # Check if expired
                    if exp_iso > now_iso:
                        if held_lane == lane.value and held_host == host.value:
                            # Renew lock
                            cursor.execute("UPDATE resource_locks SET expires_at = ? WHERE resource_id = ?", (expires_iso, resource_id))
                            cursor.execute("COMMIT;")
                            return True, "LOCK_RENEWED"
                        cursor.execute("COMMIT;")
                        return False, f"SINGLE_WRITER_CONFLICT: Held by {held_lane} on {held_host} until {exp_iso}"
                    else:
                        # Expired, take over
                        cursor.execute("""
                        UPDATE resource_locks SET
                            held_by_lane = ?, held_by_host = ?, lock_type = ?,
                            acquired_at = ?, expires_at = ?
                        WHERE resource_id = ?;
                        """, (lane.value, host.value, lock_type, now_iso, expires_iso, resource_id))
                else:
                    cursor.execute("""
                    INSERT INTO resource_locks (resource_id, held_by_lane, held_by_host, lock_type, acquired_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """, (resource_id, lane.value, host.value, lock_type, now_iso, expires_iso))

                self._record_event_tx(cursor, "LOCK_ACQUIRED", lane.value, resource_id, {
                    "host": host.value,
                    "lock_type": lock_type,
                    "expires_at": expires_iso
                })
                cursor.execute("COMMIT;")
                return True, "LOCK_ACQUIRED"
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def release_lock(self, resource_id: str, lane: Lane) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("SELECT held_by_lane FROM resource_locks WHERE resource_id = ?", (resource_id,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("COMMIT;")
                    return False
                if row["held_by_lane"] != lane.value:
                    cursor.execute("COMMIT;")
                    return False

                cursor.execute("DELETE FROM resource_locks WHERE resource_id = ?", (resource_id,))
                self._record_event_tx(cursor, "LOCK_RELEASED", lane.value, resource_id, {})
                cursor.execute("COMMIT;")
                return True
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def get_active_locks(self) -> List[Dict[str, Any]]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT resource_id, held_by_lane, held_by_host, lock_type, acquired_at, expires_at
            FROM resource_locks WHERE expires_at > ?
            ORDER BY acquired_at ASC;
            """, (now_iso,))
            return [dict(r) for r in cursor.fetchall()]

    def clean_expired_locks(self) -> int:
        """Prunes expired resource locks from the database."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("DELETE FROM resource_locks WHERE expires_at <= ?;", (now_iso,))
                pruned = cursor.rowcount
                cursor.execute("COMMIT;")
                return pruned
            except Exception:
                cursor.execute("ROLLBACK;")
                raise


    def enqueue_dispatch(
        self,
        dispatch_id: str,
        target_lane: Lane,
        target_host: Host,
        assignment_id: str,
        prompt_text: str,
        envelope_data: Dict[str, Any],
        source_lane: Lane = Lane.WINDOWS_CLI_1
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        env_json = json.dumps(envelope_data, ensure_ascii=False)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("""
                INSERT OR REPLACE INTO dispatch_queue (
                    dispatch_id, target_lane, target_host, assignment_id,
                    source_lane, prompt_text, envelope_json, status,
                    created_at, dispatched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'STAGED', ?, NULL);
                """, (
                    dispatch_id, target_lane.value, target_host.value, assignment_id,
                    source_lane.value, prompt_text, env_json, now_iso
                ))
                self._record_event_tx(cursor, "DISPATCH_ENQUEUED", source_lane.value, dispatch_id, {
                    "target_lane": target_lane.value,
                    "target_host": target_host.value,
                    "assignment_id": assignment_id
                })
                cursor.execute("COMMIT;")
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def get_pending_dispatches(self, target_lane: Optional[Lane] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if target_lane:
                cursor.execute("""
                SELECT * FROM dispatch_queue WHERE status = 'STAGED' AND target_lane = ?
                ORDER BY created_at ASC;
                """, (target_lane.value,))
            else:
                cursor.execute("""
                SELECT * FROM dispatch_queue WHERE status = 'STAGED'
                ORDER BY created_at ASC;
                """)
            return [dict(r) for r in cursor.fetchall()]

    def mark_dispatched(self, dispatch_id: str):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("""
                UPDATE dispatch_queue SET status = 'DISPATCHED', dispatched_at = ?
                WHERE dispatch_id = ?;
                """, (now_iso, dispatch_id))
                self._record_event_tx(cursor, "DISPATCH_SENT", "CHIEF", dispatch_id, {})
                cursor.execute("COMMIT;")
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def get_all_findings(self) -> List[RegisteredFinding]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM findings ORDER BY finding_id ASC;")
            res = []
            for r in cursor.fetchall():
                res.append(RegisteredFinding(
                    finding_id=r["finding_id"],
                    origin_lane=Lane.from_str(r["origin_lane"]),
                    title=r["title"],
                    status=FindingStatus(r["status"]),
                    severity=FindingSeverity(r["severity"]),
                    description=r["description"],
                    reproduction_ref=r["reproduction_ref"],
                    evidence_hash=r["evidence_hash"],
                    created_at=r["first_seen_at"],
                    updated_at=r["updated_at"]
                ))
            return res

    def get_all_patches(self) -> List[RegisteredPatch]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patches ORDER BY patch_id ASC;")
            res = []
            for r in cursor.fetchall():
                res.append(RegisteredPatch(
                    patch_id=r["patch_id"],
                    batch_name=r["batch_name"],
                    status=PatchStatus(r["status"]),
                    description=r["description"],
                    target_files=json.loads(r["target_files_json"]),
                    reproduction_scripts=json.loads(r["reproduction_scripts_json"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"]
                ))
            return res

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks ORDER BY updated_at DESC;")
            return [dict(r) for r in cursor.fetchall()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?;", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT event_id, event_type, lane, entity_id, delta_json, timestamp_utc, prev_hash, event_hash
            FROM event_ledger ORDER BY event_id DESC LIMIT ?;
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def _record_event_tx(self, cursor: sqlite3.Cursor, event_type: str, lane: str, entity_id: str, delta_data: Dict[str, Any]):
        now_iso = datetime.now(timezone.utc).isoformat()
        delta_str = json.dumps(delta_data, sort_keys=True)

        cursor.execute("SELECT event_hash FROM event_ledger ORDER BY event_id DESC LIMIT 1;")
        last = cursor.fetchone()
        prev_hash = last["event_hash"] if last else "GENESIS_ROOT_00000000000000000000000000000000000000000000000000000000"

        hasher = hashlib.sha256()
        hasher.update(prev_hash.encode("utf-8"))
        hasher.update(event_type.encode("utf-8"))
        hasher.update(lane.encode("utf-8"))
        hasher.update(entity_id.encode("utf-8"))
        hasher.update(delta_str.encode("utf-8"))
        hasher.update(now_iso.encode("utf-8"))
        event_hash = hasher.hexdigest()

        cursor.execute("""
        INSERT INTO event_ledger (event_type, lane, entity_id, delta_json, timestamp_utc, prev_hash, event_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (event_type, lane, entity_id, delta_str, now_iso, prev_hash, event_hash))

    def set_checkpoint(self, checkpoint_key: str, checkpoint_value: Union[str, Dict[str, Any]]) -> None:
        """Persists an authoritative named checkpoint with rich structured metadata."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if isinstance(checkpoint_value, dict):
            val_dict = dict(checkpoint_value)
            if "verified_at" not in val_dict:
                val_dict["verified_at"] = now_iso
            val_str = json.dumps(val_dict)
        else:
            val_str = str(checkpoint_value)
            try:
                val_dict = json.loads(val_str) if val_str.startswith("{") else {"task_id": val_str, "verified_at": now_iso}
            except Exception:
                val_dict = {"task_id": val_str, "verified_at": now_iso}

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")
            try:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_key TEXT PRIMARY KEY,
                    checkpoint_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)
                if checkpoint_key == "LAST_VERIFIED_WINDOWS_CHECKPOINT":
                    import re
                    cursor.execute("SELECT checkpoint_value FROM checkpoints WHERE checkpoint_key = ?;", (checkpoint_key,))
                    row = cursor.fetchone()
                    if row:
                        old_raw = str(row["checkpoint_value"])
                        try:
                            old_dict = json.loads(old_raw) if old_raw.startswith("{") else {"task_id": old_raw}
                        except Exception:
                            old_dict = {"task_id": old_raw}

                        def _num(val: Any) -> int:
                            m = re.match(r"^TASK-WIN-(\d+)$", str(val))
                            return int(m.group(1)) if m and len(m.group(1)) < 8 else -1

                        old_gen = old_dict.get("state_generation")
                        new_gen = val_dict.get("state_generation")
                        old_n = _num(old_dict.get("task_id", old_raw))
                        new_n = _num(val_dict.get("task_id", val_str))

                        # Monotonic check: state generation first, then task number
                        if old_gen is not None and new_gen is not None:
                            if new_gen < old_gen:
                                cursor.execute("COMMIT;")
                                return
                        if new_n != -1 and old_n != -1 and new_n < old_n:
                            cursor.execute("COMMIT;")
                            return

                cursor.execute("""
                INSERT INTO checkpoints (checkpoint_key, checkpoint_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(checkpoint_key) DO UPDATE SET
                    checkpoint_value = excluded.checkpoint_value,
                    updated_at = excluded.updated_at;
                """, (checkpoint_key, val_str, now_iso))
                cursor.execute("COMMIT;")
            except Exception:
                cursor.execute("ROLLBACK;")
                raise

    def get_checkpoint(self, checkpoint_key: str) -> Optional[str]:
        """Retrieves an authoritative named checkpoint task ID (string for backward compatibility)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT checkpoint_value FROM checkpoints WHERE checkpoint_key = ?;", (checkpoint_key,))
                row = cursor.fetchone()
                if not row:
                    return None
                val = str(row["checkpoint_value"])
                if val.startswith("{"):
                    try:
                        d = json.loads(val)
                        return d.get("task_id", val)
                    except Exception:
                        return val
                return val
            except sqlite3.OperationalError:
                return None

    def get_checkpoint_record(self, checkpoint_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves the full structured checkpoint metadata record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT checkpoint_value, updated_at FROM checkpoints WHERE checkpoint_key = ?;", (checkpoint_key,))
                row = cursor.fetchone()
                if not row:
                    return None
                val = str(row["checkpoint_value"])
                updated_at = str(row["updated_at"])
                if val.startswith("{"):
                    try:
                        d = json.loads(val)
                        if "updated_at" not in d:
                            d["updated_at"] = updated_at
                        return d
                    except Exception:
                        pass
                return {
                    "task_id": val,
                    "task_version": 1,
                    "state_generation": None,
                    "result_fingerprint": None,
                    "verified_at": updated_at,
                    "updated_at": updated_at
                }
            except sqlite3.OperationalError:
                return None


