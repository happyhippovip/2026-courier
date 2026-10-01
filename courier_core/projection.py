"""Deterministic projections of the journal.

The `tasks` table is a pure function of the event sequence: every row is the
TaskState that courier_core.state_machine.apply produces when the events are
folded in seq order. The journal updates it inside the same transaction as
the event insert; rebuild() reproduces it from the events alone, and
projection_hash() fingerprints it so live, copied and rebuilt projections can
be compared byte for byte.

Only data derived from events is stored here. Wall-clock time, lease
deadlines and process state never enter a projection.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import fields
from pathlib import Path
from typing import Iterable

from courier_core.events import Event, SYSTEM_EVENTS, canonical_json
from courier_core.state_machine import TaskState, apply

PROJECTION_VERSION = 2  # 2: resolution, decided_by

_COLUMNS = [f.name for f in fields(TaskState)]
_JSON_COLUMNS = {"params"}
_BOOL_COLUMNS = {"started", "cancel_requested"}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    {", ".join(f"{name} {'INTEGER' if name in _BOOL_COLUMNS else 'TEXT' if name in _JSON_COLUMNS else ''}".strip()
               for name in _COLUMNS if name != "task_id")}
);
CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status);
CREATE TABLE IF NOT EXISTS projection_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class ProjectionError(RuntimeError):
    """The event sequence cannot be folded (corrupt or illegal history)."""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the projection tables; safe inside the caller's transaction."""
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.execute("INSERT OR IGNORE INTO projection_meta(key, value) VALUES ('version', ?)",
                 (str(PROJECTION_VERSION),))
    conn.execute("INSERT OR IGNORE INTO projection_meta(key, value) VALUES ('last_seq', '0')")


def is_current(conn: sqlite3.Connection) -> bool:
    """False if the stored projection was built by another projection version."""
    try:
        row = conn.execute("SELECT value FROM projection_meta WHERE key = 'version'").fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None and row[0] == str(PROJECTION_VERSION)


def rebuild_in_place(conn: sqlite3.Connection, events: Iterable[Event]) -> None:
    """Replace the projection tables by a fresh fold (caller owns the transaction).

    The projection is derived data, so a projection written by an older build
    is rebuilt from the journal instead of being migrated column by column.
    """
    conn.execute("DROP TABLE IF EXISTS tasks")
    conn.execute("DROP TABLE IF EXISTS projection_meta")
    create_schema(conn)
    for event in events:
        try:
            apply_event(conn, event)
        except ValueError as exc:
            raise ProjectionError(f"seq {event.seq}: {exc}") from exc


def _to_row(state: TaskState) -> list:
    record = state.to_record()
    row = []
    for name in _COLUMNS:
        value = record[name]
        if name in _JSON_COLUMNS:
            value = canonical_json(value)
        elif name in _BOOL_COLUMNS:
            value = int(value)
        row.append(value)
    return row


def _from_row(row: sqlite3.Row | tuple) -> TaskState:
    if len(_COLUMNS) != len(row):
        raise ValueError(f"Column count mismatch: expected {len(_COLUMNS)}, got {len(row)}")
    record = dict(zip(_COLUMNS, row))
    for name in _JSON_COLUMNS:
        record[name] = json.loads(record[name])
    for name in _BOOL_COLUMNS:
        record[name] = bool(record[name])
    return TaskState.from_record(record)


def load_task(conn: sqlite3.Connection, task_id: str | None) -> TaskState | None:
    if task_id is None:
        return None
    row = conn.execute(f"SELECT {', '.join(_COLUMNS)} FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return _from_row(tuple(row)) if row else None


def load_tasks(conn: sqlite3.Connection, status: str | None = None) -> list[TaskState]:
    query = f"SELECT {', '.join(_COLUMNS)} FROM tasks"
    args: tuple = ()
    if status is not None:
        query += " WHERE status = ?"
        args = (status,)
    return [_from_row(tuple(row)) for row in conn.execute(query + " ORDER BY created_seq, task_id", args)]


def store(conn: sqlite3.Connection, state: TaskState | None, seq: int) -> None:
    if state is not None:
        conn.execute(f"INSERT OR REPLACE INTO tasks({', '.join(_COLUMNS)}) VALUES ({', '.join('?' * len(_COLUMNS))})",
                     _to_row(state))
    conn.execute("UPDATE projection_meta SET value = ? WHERE key = 'last_seq'", (str(seq),))


def apply_event(conn: sqlite3.Connection, event: Event) -> TaskState | None:
    """Fold one sealed event into the projection tables (caller owns the transaction)."""
    if event.seq is None:
        raise ProjectionError("only sealed events (with seq) can be projected")
    if event.type in SYSTEM_EVENTS:
        store(conn, None, event.seq)
        return None
    new_state = apply(load_task(conn, event.task_id), event)
    store(conn, new_state, event.seq)
    return new_state


def last_seq(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM projection_meta WHERE key = 'last_seq'").fetchone()
    return int(row[0]) if row else 0


def projection_hash(conn: sqlite3.Connection) -> str:
    """sha256 of every task row in task_id order, in canonical encoding.

    Controller lifecycle events only advance last_seq, which is deliberately
    not hashed: restarting the controller must not change the fingerprint.
    """
    digest = hashlib.sha256()
    digest.update(f"courier-projection-v{PROJECTION_VERSION}\n".encode())
    for row in conn.execute(f"SELECT {', '.join(_COLUMNS)} FROM tasks ORDER BY task_id"):
        digest.update(canonical_json(list(row)).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def fold(events: Iterable[Event]) -> dict[str, TaskState]:
    """Pure in-memory replay; the reference the SQL projection must match."""
    tasks: dict[str, TaskState] = {}
    for event in events:
        if event.type in SYSTEM_EVENTS:
            continue
        try:
            tasks[event.task_id] = apply(tasks.get(event.task_id), event)
        except ValueError as exc:
            raise ProjectionError(f"seq {event.seq}: {exc}") from exc
    return tasks


def rebuild(journal, out_path: str | os.PathLike) -> Path:
    """Replay every journal event into a fresh projection database at out_path."""
    out = Path(out_path)
    for suffix in ("", "-wal", "-shm"):
        Path(str(out) + suffix).unlink(missing_ok=True)
    conn = sqlite3.connect(str(out), isolation_level=None)
    try:
        conn.execute("BEGIN")
        create_schema(conn)
        for event in journal.events():
            try:
                apply_event(conn, event)
            except ValueError as exc:
                raise ProjectionError(f"seq {event.seq}: {exc}") from exc
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return out
