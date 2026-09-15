"""Fenced remote-execution and atomic-artifact lifecycle boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
UNSAFE_RETRY = {"UNKNOWN", "QUARANTINED", "RECONCILIATION_REQUIRED"}


class RemoteLifecycleError(RuntimeError):
    pass


class ArtifactLifecycleError(RuntimeError):
    pass


def _fingerprint(value: bytes | str) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


class RemoteLifecycleLedger:
    """Durably fences remote effects; local clients are never remote identity."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS remote_executions (
                    task_id TEXT NOT NULL, attempt INTEGER NOT NULL, owner_generation TEXT NOT NULL,
                    remote_execution_id TEXT, remote_target TEXT NOT NULL, command_fingerprint TEXT NOT NULL,
                    effect_fingerprint TEXT NOT NULL, result_fingerprint TEXT, state TEXT NOT NULL,
                    PRIMARY KEY(task_id, attempt, owner_generation)
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.ledger_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def start(self, task_id: str, attempt: int, generation: str, remote_id: str, target: str, command: str, effect: str) -> None:
        if not remote_id:
            raise RemoteLifecycleError("AMBIGUOUS_REMOTE_ID_QUARANTINED")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO remote_executions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'STARTING')",
                (task_id, attempt, generation, remote_id, target, _fingerprint(command), _fingerprint(effect)),
            )
            conn.execute(
                "UPDATE remote_executions SET state='RUNNING' WHERE task_id=? AND attempt=? AND owner_generation=?",
                (task_id, attempt, generation),
            )

    def connection_lost(self, task_id: str, attempt: int, generation: str) -> None:
        self._set(task_id, attempt, generation, "UNKNOWN")

    def reconcile(self, task_id: str, attempt: int, generation: str, state: str, effect: str) -> None:
        if state not in TERMINAL:
            self._set(task_id, attempt, generation, "RECONCILIATION_REQUIRED")
            raise RemoteLifecycleError("RECONCILIATION_REQUIRED")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT effect_fingerprint FROM remote_executions WHERE task_id=? AND attempt=? AND owner_generation=?",
                (task_id, attempt, generation),
            ).fetchone()
            if not row or row[0] != _fingerprint(effect):
                self._set(task_id, attempt, generation, "QUARANTINED")
                raise RemoteLifecycleError("REMOTE_EFFECT_FENCE_REJECTED")
            conn.execute(
                "UPDATE remote_executions SET state=? WHERE task_id=? AND attempt=? AND owner_generation=?",
                (state, task_id, attempt, generation),
            )

    def accept_result(self, task_id: str, attempt: int, generation: str, result: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM remote_executions WHERE task_id=? AND attempt=? AND owner_generation=?",
                (task_id, attempt, generation),
            ).fetchone()
            if not row or row[0] != "COMPLETED":
                raise RemoteLifecycleError("LATE_OR_UNFENCED_RESULT_QUARANTINED")
            conn.execute(
                "UPDATE remote_executions SET result_fingerprint=? WHERE task_id=? AND attempt=? AND owner_generation=?",
                (_fingerprint(result), task_id, attempt, generation),
            )

    def retry_allowed(self, task_id: str, attempt: int, generation: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM remote_executions WHERE task_id=? AND attempt=? AND owner_generation=?",
                (task_id, attempt, generation),
            ).fetchone()
        return bool(row and row[0] == "FAILED")

    def _set(self, task_id: str, attempt: int, generation: str, state: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE remote_executions SET state=? WHERE task_id=? AND attempt=? AND owner_generation=?",
                (state, task_id, attempt, generation),
            )


class AtomicArtifactStore:
    """Attempt-scoped artifact promotion with durable generation/effect fencing."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(ledger_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS artifact_promotions (
                    destination TEXT PRIMARY KEY, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                    owner_generation TEXT NOT NULL, effect_fingerprint TEXT NOT NULL,
                    artifact_fingerprint TEXT NOT NULL, state TEXT NOT NULL
                )"""
            )

    def temp_path(self, destination: Path, task_id: str, attempt: int) -> Path:
        return destination.with_name(f"{destination.name}.tmp.{task_id}.{attempt}")

    def write(self, destination: Path, task_id: str, attempt: int, data: bytes) -> Path:
        path = self.temp_path(destination, task_id, attempt)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as artifact:
            artifact.write(data)
            artifact.flush()
            os.fsync(artifact.fileno())
        return path

    def promote(
        self, destination: Path, task_id: str, attempt: int, generation: str, effect: str,
        *, allow_replace: bool = False, crash_after: str | None = None,
    ) -> None:
        temp = self.temp_path(destination, task_id, attempt)
        with sqlite3.connect(self.ledger_path) as conn:
            content_fingerprint = _fingerprint(temp.read_bytes()) if temp.exists() else None
            current = conn.execute(
                "SELECT task_id, attempt, owner_generation, effect_fingerprint, artifact_fingerprint, state "
                "FROM artifact_promotions WHERE destination=?", (str(destination),)
            ).fetchone()
            if current:
                if current[:4] == (task_id, attempt, generation, _fingerprint(effect)):
                    if current[5] == "COMPLETED":
                        self._verify_final(destination, current[4])
                        return
                    if self.reconcile(destination, task_id, attempt, generation, effect) != "PREPARED_RESUME_ALLOWED":
                        raise ArtifactLifecycleError("PREPARED_RECONCILIATION_REJECTED")
                elif not allow_replace:
                    raise ArtifactLifecycleError("ARTIFACT_PROMOTION_FENCE_REJECTED")
            if not temp.exists():
                raise ArtifactLifecycleError("TEMP_ARTIFACT_MISSING")
            if destination.exists() and not allow_replace:
                raise ArtifactLifecycleError("DESTINATION_EXISTS_QUARANTINED")
            conn.execute(
                "INSERT OR REPLACE INTO artifact_promotions VALUES (?, ?, ?, ?, ?, ?, 'PREPARED')",
                (str(destination), task_id, attempt, generation, _fingerprint(effect), content_fingerprint),
            )
            if crash_after == "PREPARED":
                return
            os.replace(temp, destination)
            directory = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            if crash_after == "RENAMED":
                return
            self._verify_final(destination, content_fingerprint)
            conn.execute(
                "UPDATE artifact_promotions SET state='COMPLETED' WHERE destination=?",
                (str(destination),),
            )

    def reconcile(self, destination: Path, task_id: str, attempt: int, generation: str, effect: str) -> str:
        temp = self.temp_path(destination, task_id, attempt)
        with sqlite3.connect(self.ledger_path) as conn:
            row = conn.execute(
                "SELECT task_id, attempt, owner_generation, effect_fingerprint, artifact_fingerprint, state "
                "FROM artifact_promotions WHERE destination=?", (str(destination),)
            ).fetchone()
            expected = (task_id, attempt, generation, _fingerprint(effect))
            if not row or row[:4] != expected:
                raise ArtifactLifecycleError("UNKNOWN_ARTIFACT_QUARANTINED")
            if row[5] == "COMPLETED":
                self._verify_final(destination, row[4])
                return "COMPLETED_VERIFIED"
            if temp.exists() and destination.exists():
                self._quarantine(conn, destination)
                raise ArtifactLifecycleError("PREPARED_BOTH_PRESENT_QUARANTINED")
            if temp.exists() and not destination.exists():
                return "PREPARED_RESUME_ALLOWED"
            if not temp.exists() and destination.exists():
                self._verify_final(destination, row[4])
                conn.execute("UPDATE artifact_promotions SET state='COMPLETED' WHERE destination=?", (str(destination),))
                return "RENAMED_EFFECT_RECOVERED"
            self._quarantine(conn, destination)
            raise ArtifactLifecycleError("PREPARED_ARTIFACT_MISSING_QUARANTINED")

    def reconcile_temp(self, destination: Path, task_id: str, attempt: int) -> str:
        return "STALE_TEMP_PRESERVED_QUARANTINED" if self.temp_path(destination, task_id, attempt).exists() else "NO_OWNED_TEMP"

    @staticmethod
    def _verify_final(destination: Path, expected_fingerprint: str) -> None:
        if not destination.exists() or _fingerprint(destination.read_bytes()) != expected_fingerprint:
            raise ArtifactLifecycleError("FINAL_ARTIFACT_FINGERPRINT_MISMATCH_QUARANTINED")

    @staticmethod
    def _quarantine(conn: sqlite3.Connection, destination: Path) -> None:
        conn.execute("UPDATE artifact_promotions SET state='QUARANTINED' WHERE destination=?", (str(destination),))
