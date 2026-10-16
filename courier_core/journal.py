"""The Courier v1 journal: SQLite, append-only, hash-chained.

One file (`<COURIER_HOME>/courier.db`) holds the `events` table, the single
source of truth, and the projection tables derived from it. The controller is
the only writer. Every append runs in one IMMEDIATE transaction that

1. answers a repeated submission (same dedupe_key, same content) with the
   already stored event instead of a second row,
2. folds the event through the task state machine (an illegal event raises
   and nothing is written),
3. inserts the event with seq = head + 1 and hash = H(row, prev_hash),
4. updates the projection,

so the journal and its projection can never disagree, and a crash at any
point leaves either the whole event or nothing.

UPDATE and DELETE on `events` are rejected by triggers. verify_chain()
recomputes the chain from the stored bytes and reports the first bad seq.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from courier_core import projection
from courier_core.events import GENESIS_HASH, Event, EventValidationError, chain_hash
from courier_core.state_machine import TaskState

DB_SCHEMA_VERSION = 1

EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    schema_v INTEGER NOT NULL,
    type TEXT NOT NULL,
    task_id TEXT,
    attempt INTEGER,
    dispatch_id TEXT,
    worker_id TEXT,
    result_id TEXT,
    dedupe_key TEXT UNIQUE,
    ts_utc TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_task ON events(task_id, seq);
CREATE INDEX IF NOT EXISTS events_dispatch ON events(dispatch_id, seq);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'courier journal is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'courier journal is append-only'); END;
"""

_EVENT_COLUMNS = ("seq", "event_id", "schema_v", "type", "task_id", "attempt", "dispatch_id", "worker_id",
                  "result_id", "dedupe_key", "ts_utc", "payload", "prev_hash", "hash")


class JournalError(RuntimeError):
    pass


class DedupeConflict(JournalError):
    """A dedupe_key is reused for an event with different content."""


@dataclass(frozen=True)
class AppendResult:
    event: Event
    duplicate: bool
    state: TaskState | None


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    count: int
    head_seq: int
    head_hash: str
    first_bad_seq: int | None = None
    reason: str | None = None


class Journal:
    """The journal file.

    readonly=True opens an existing journal for inspection only: no schema is
    created or migrated and append() is refused, so integrity checks and a
    degraded controller never write to a file that may be evidence.
    """

    def __init__(self, path: str | os.PathLike, readonly: bool = False):
        self.path = Path(path)
        self.readonly = readonly
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    # -- lifecycle ------------------------------------------------------------
    def open(self) -> "Journal":
        if self._conn is not None:
            return self
        if self.readonly:
            if not self.path.exists():
                raise JournalError(f"{self.path}: no journal to inspect")
            conn = sqlite3.connect(str(self.path), isolation_level=None, check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA query_only=ON")
            self._conn = conn
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except Exception:
            pass
        if not self.path.exists():
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
                os.close(fd)
            except Exception:
                pass
        else:
            try:
                os.chmod(self.path, 0o600)
            except Exception:
                pass
        conn = sqlite3.connect(str(self.path), isolation_level=None, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=30000")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, DB_SCHEMA_VERSION):
            conn.close()
            raise JournalError(f"{self.path}: unsupported journal schema version {version}")
        try:
            # Every statement is idempotent (IF NOT EXISTS / INSERT OR IGNORE),
            # so an interrupted first open is completed by the next one.
            conn.executescript(EVENTS_SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            if not projection.is_current(conn):
                rows = conn.execute("SELECT * FROM events ORDER BY seq").fetchall()
                projection.rebuild_in_place(conn, (Event.from_row(row) for row in rows))
            projection.create_schema(conn)
            conn.execute(f"PRAGMA user_version={DB_SCHEMA_VERSION}")
            conn.execute("COMMIT")
        except (projection.ProjectionError, ValueError) as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.close()
            raise JournalError(f"{self.path}: projection cannot be rebuilt: {exc}") from exc
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.close()
            raise
        self._conn = conn
        return self

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> "Journal":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise JournalError("journal is not open")
        return self._conn

    # -- reads ----------------------------------------------------------------
    def head(self) -> tuple[int, str]:
        row = self.conn.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        return (row["seq"], row["hash"]) if row else (0, GENESIS_HASH)

    def events(self, after_seq: int = 0, task_id: str | None = None) -> Iterator[Event]:
        query = f"SELECT {', '.join(_EVENT_COLUMNS)} FROM events WHERE seq > ?"
        args: list = [after_seq]
        if task_id is not None:
            query += " AND task_id = ?"
            args.append(task_id)
        rows = self.conn.execute(query + " ORDER BY seq", args).fetchall()
        for row in rows:
            yield Event.from_row(row)

    def get_event_by_dedupe_key(self, key: str) -> Event | None:
        row = self.conn.execute(f"SELECT {', '.join(_EVENT_COLUMNS)} FROM events WHERE dedupe_key = ?",
                                (key,)).fetchone()
        return Event.from_row(row) if row else None

    def claim_for_dispatch(self, dispatch_id: str) -> Event | None:
        """The TASK_CLAIMED event that issued dispatch_id, if any."""
        row = self.conn.execute(
            f"SELECT {', '.join(_EVENT_COLUMNS)} FROM events WHERE dispatch_id = ? AND type = 'TASK_CLAIMED' "
            "ORDER BY seq LIMIT 1", (dispatch_id,)).fetchone()
        return Event.from_row(row) if row else None

    def task(self, task_id: str) -> TaskState | None:
        return projection.load_task(self.conn, task_id)

    def tasks(self, status: str | None = None) -> list[TaskState]:
        return projection.load_tasks(self.conn, status)

    # -- the only write path --------------------------------------------------
    def append(self, event: Event) -> AppendResult:
        if self.readonly:
            raise JournalError("journal is open read-only")
        if event.seq is not None or event.hash is not None:
            raise JournalError("event is already sealed; append unsealed events only")
        with self._lock:
            conn = self.conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                if event.dedupe_key is not None:
                    existing = self.get_event_by_dedupe_key(event.dedupe_key)
                    if existing is not None:
                        if existing.content() != event.content():
                            raise DedupeConflict(
                                f"dedupe_key {event.dedupe_key!r} already used by seq {existing.seq} "
                                "with different content")
                        conn.execute("ROLLBACK")
                        return AppendResult(existing, True, self.task(existing.task_id)
                                            if existing.task_id else None)
                seq, prev_hash = self.head()
                sealed = event.sealed(seq + 1, prev_hash)
                state = projection.apply_event(conn, sealed)  # raises TransitionError on illegal events
                conn.execute(
                    f"INSERT INTO events({', '.join(_EVENT_COLUMNS)}) VALUES ({', '.join('?' * len(_EVENT_COLUMNS))})",
                    (sealed.seq, sealed.event_id, sealed.schema_v, sealed.type.value, sealed.task_id,
                     sealed.attempt, sealed.dispatch_id, sealed.worker_id, sealed.result_id, sealed.dedupe_key,
                     sealed.ts_utc, sealed.payload_json, sealed.prev_hash, sealed.hash))
                conn.execute("COMMIT")
                return AppendResult(sealed, False, state)
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    # -- integrity --------------------------------------------------------------
    def verify_chain(self) -> ChainReport:
        """Recompute every hash from the stored bytes; report the first break."""
        expected_seq, prev_hash, count = 1, GENESIS_HASH, 0
        rows = self.conn.execute(f"SELECT {', '.join(_EVENT_COLUMNS)} FROM events ORDER BY seq")
        for row in rows:
            reason = self._row_defect(row, expected_seq, prev_hash)
            if reason is not None:
                return ChainReport(False, count, expected_seq - 1, prev_hash,
                                   first_bad_seq=row["seq"], reason=reason)
            prev_hash, expected_seq, count = row["hash"], expected_seq + 1, count + 1
        return ChainReport(True, count, expected_seq - 1, prev_hash)

    @staticmethod
    def _row_defect(row: sqlite3.Row, expected_seq: int, prev_hash: str) -> str | None:
        if row["seq"] != expected_seq:
            return f"sequence gap: expected {expected_seq}, found {row['seq']}"
        if row["prev_hash"] != prev_hash:
            return "prev_hash does not link to the previous event"
        try:
            event = Event.from_row(row)
        except (EventValidationError, ValueError, TypeError) as exc:
            return f"stored event is invalid: {exc}"
        if chain_hash(event, payload_text=row["payload"]) != row["hash"]:
            return "hash mismatch: stored event was modified"
        return None

    def quick_check(self) -> str:
        """SQLite's structural check ('ok' when healthy); bounded, read-only."""
        rows = self.conn.execute("PRAGMA quick_check").fetchall()
        return "; ".join(str(row[0]) for row in rows)

    def guards_present(self) -> bool:
        """True if the append-only triggers on `events` are installed."""
        names = {row[0] for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'events'")}
        return {"events_no_update", "events_no_delete"} <= names

    def projection_current(self) -> bool:
        """False if the projection predates this build (the next writable open rebuilds it)."""
        return projection.is_current(self.conn)

    def verify_projection(self) -> bool:
        """True if the stored projection equals a pure in-memory replay."""
        expected = projection.fold(self.events())
        actual = {state.task_id: state for state in self.tasks()}
        return expected == actual
