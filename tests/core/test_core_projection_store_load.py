"""Store/load round-trip pins for courier_core.projection (P9-projection_store_load).

Covers only the SQL store/load layer that the rebuild tests exercise
indirectly: create_schema idempotence and meta rows, is_current / last_seq
edge rows, store INSERT OR REPLACE semantics (including the state=None
system-event path), load_task / load_tasks round-trips, ordering and
filtering, apply_event system/task folding, fold system-event skipping and
error shape, rebuild_in_place restore semantics, rebuild target cleanup and
rollback atomicity, and the empty-projection fingerprint.

No journal behavior change, no DB outside tmp_path / :memory:, no network.

Non-overlap: open PR #323 pins is_current version checks, unsealed-event
rejection, missing-task loads and _from_row arity on
tests/core/test_core_projection.py; open PR #352/#429 pin work_packet, not
this module. This file is new and touches no file any open PR changes.
"""

from __future__ import annotations

import contextlib
import hashlib
import sqlite3

import pytest

from core_builders import Attempt, created, golden_path, stable
from courier_core.events import SYSTEM_EVENTS, Event, EventType
from courier_core.journal import Journal
from courier_core.projection import (
    PROJECTION_VERSION,
    ProjectionError,
    _from_row,
    _to_row,
    apply_event,
    create_schema,
    fold,
    is_current,
    last_seq,
    load_task,
    load_tasks,
    projection_hash,
    rebuild,
    rebuild_in_place,
    store,
)
from courier_core.state_machine import TaskStatus, TransitionError


def mem():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return conn


def sealed_history(tmp_path, events):
    """Append events to a scratch journal and return the sealed copies."""
    path = tmp_path / "courier.db"
    with Journal(path) as journal:
        for event in events:
            journal.append(event)
        return list(journal.events())


def test_projection_version_is_two():
    assert PROJECTION_VERSION == 2


def test_create_schema_sets_version_and_zero_last_seq():
    with contextlib.closing(mem()) as conn:
        version = conn.execute("SELECT value FROM projection_meta WHERE key = 'version'").fetchone()
        assert version is not None and version[0] == str(PROJECTION_VERSION)
        assert last_seq(conn) == 0
        assert is_current(conn)


def test_create_schema_preserves_existing_meta_rows():
    with contextlib.closing(mem()) as conn:
        conn.execute("UPDATE projection_meta SET value = '9999' WHERE key = 'version'")
        conn.execute("UPDATE projection_meta SET value = '41' WHERE key = 'last_seq'")
        create_schema(conn)
        version = conn.execute("SELECT value FROM projection_meta WHERE key = 'version'").fetchone()
        assert version[0] == "9999"
        assert last_seq(conn) == 41
        assert not is_current(conn)


def test_is_current_false_when_version_row_absent():
    with contextlib.closing(mem()) as conn:
        conn.execute("DELETE FROM projection_meta WHERE key = 'version'")
        assert not is_current(conn)


def test_last_seq_zero_when_row_absent():
    with contextlib.closing(mem()) as conn:
        conn.execute("DELETE FROM projection_meta WHERE key = 'last_seq'")
        assert last_seq(conn) == 0


def test_is_current_false_without_tables():
    with contextlib.closing(sqlite3.connect(":memory:")) as conn:
        assert not is_current(conn)


def test_store_and_load_task_round_trip(tmp_path):
    sealed = sealed_history(tmp_path, golden_path("t1"))
    with Journal(tmp_path / "courier.db") as journal:
        state = journal.tasks()[0]
    with contextlib.closing(mem()) as conn:
        store(conn, state, sealed[-1].seq)
        loaded = load_task(conn, "t1")
        assert loaded == state
        assert last_seq(conn) == sealed[-1].seq


def test_row_encoding_uses_integers_for_bools_and_json_for_params(tmp_path):
    attempt = Attempt("t1", 1)
    sealed_history(tmp_path, [created("t1"), attempt.claimed(), attempt.started()])
    with Journal(tmp_path / "courier.db") as journal:
        state = journal.tasks()[0]
    assert state.started is True and state.cancel_requested is False
    with contextlib.closing(mem()) as conn:
        store(conn, state, 3)
        row = conn.execute("SELECT started, cancel_requested, params FROM tasks WHERE task_id = 't1'").fetchone()
        assert (row[0], row[1]) == (1, 0)
        assert isinstance(row[2], str)
        assert load_task(conn, "t1") == state


def test_to_row_from_row_round_trip_preserves_types(tmp_path):
    sealed_history(tmp_path, [created("t1")])
    with Journal(tmp_path / "courier.db") as journal:
        state = journal.tasks()[0]
    assert _from_row(_to_row(state)) == state


def test_load_tasks_orders_by_created_seq_not_task_id(tmp_path):
    sealed_history(tmp_path, [created("zzz"), created("aaa")])
    with Journal(tmp_path / "courier.db") as journal:
        states = load_tasks(journal.conn)
    assert [s.task_id for s in states] == ["zzz", "aaa"]


def test_load_tasks_status_filter(tmp_path):
    attempt = Attempt("t1", 1)
    sealed_history(tmp_path, [created("t1"), *attempt.happy(), created("t2")])
    with Journal(tmp_path / "courier.db") as journal:
        assert [s.task_id for s in load_tasks(journal.conn, TaskStatus.COMPLETE.value)] == ["t1"]
        assert [s.task_id for s in load_tasks(journal.conn, TaskStatus.QUEUED.value)] == ["t2"]
        assert len(load_tasks(journal.conn)) == 2
        assert load_tasks(journal.conn, TaskStatus.FAILED.value) == []


def test_store_replaces_existing_row_and_moves_last_seq(tmp_path):
    events = golden_path("t1")
    sealed = sealed_history(tmp_path, events)
    early, late = fold(events[:1])["t1"], fold(events)["t1"]
    assert early != late
    with contextlib.closing(mem()) as conn:
        store(conn, early, 1)
        store(conn, late, sealed[-1].seq)
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert count == 1
        assert load_task(conn, "t1") == late
        assert last_seq(conn) == sealed[-1].seq


def test_store_none_advances_last_seq_without_task_row():
    with contextlib.closing(mem()) as conn:
        store(conn, None, 7)
        assert last_seq(conn) == 7
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_apply_event_system_event_advances_seq_only(tmp_path):
    system = Event(**stable(type=EventType.CONTROLLER_STARTED))
    assert system.type in SYSTEM_EVENTS
    sealed = sealed_history(tmp_path, [system])
    with contextlib.closing(mem()) as conn:
        assert apply_event(conn, sealed[0]) is None
        assert last_seq(conn) == sealed[0].seq
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_apply_event_task_event_returns_and_persists_state(tmp_path):
    sealed = sealed_history(tmp_path, [created("t1")])
    with contextlib.closing(mem()) as conn:
        state = apply_event(conn, sealed[0])
        assert state is not None and state.task_id == "t1"
        assert state.status is TaskStatus.QUEUED
        assert load_task(conn, "t1") == state
        assert last_seq(conn) == sealed[0].seq


def test_apply_event_illegal_history_raises_transition_error():
    ghost = Event(**stable(type=EventType.TASK_COMPLETE, task_id="ghost", attempt=1,
                           dispatch_id="d-ghost", result_id="r-ghost")).sealed(5, "0" * 64)
    with contextlib.closing(mem()) as conn:
        with pytest.raises(TransitionError):
            apply_event(conn, ghost)


def test_fold_skips_system_events_and_empty_input():
    assert fold([]) == {}
    system = Event(**stable(type=EventType.CONTROLLER_STOPPED)).sealed(1, "0" * 64)
    assert fold([system]) == {}
    task = created("t1")
    replayed = fold([system, task])
    assert list(replayed) == ["t1"]


def test_fold_error_message_carries_seq():
    ghost = Event(**stable(type=EventType.TASK_COMPLETE, task_id="ghost", attempt=1,
                           dispatch_id="d-ghost", result_id="r-ghost")).sealed(5, "0" * 64)
    with pytest.raises(ProjectionError, match="seq 5"):
        fold([ghost])


def test_rebuild_in_place_restores_corrupted_projection(tmp_path):
    events = golden_path("t1")
    sealed = sealed_history(tmp_path, events)
    with contextlib.closing(mem()) as conn:
        for event in sealed:
            apply_event(conn, event)
        before = projection_hash(conn)
        conn.execute("UPDATE tasks SET status = 'FAILED' WHERE task_id = 't1'")
        assert projection_hash(conn) != before
        rebuild_in_place(conn, sealed)
        assert projection_hash(conn) == before
        assert load_task(conn, "t1").status is TaskStatus.COMPLETE
        assert last_seq(conn) == sealed[-1].seq


def test_rebuild_in_place_rejects_illegal_history_with_seq(tmp_path):
    good = sealed_history(tmp_path, golden_path("t1"))
    forged = good[-1].sealed(7, good[-1].hash)
    with contextlib.closing(mem()) as conn:
        with pytest.raises(ProjectionError, match="seq 7"):
            rebuild_in_place(conn, [*good, forged])


def test_empty_projection_hash_is_version_prefix_only():
    expected = hashlib.sha256(f"courier-projection-v{PROJECTION_VERSION}\n".encode()).hexdigest()
    with contextlib.closing(mem()) as conn:
        assert projection_hash(conn) == expected
        store(conn, None, 9)
        assert projection_hash(conn) == expected


def test_rebuild_returns_path_and_cleans_sidecar_files(tmp_path):
    events = golden_path("t1")
    path = tmp_path / "courier.db"
    with Journal(path) as journal:
        for event in events:
            journal.append(event)
        live = projection_hash(journal.conn)
        out = tmp_path / "rebuilt.db"
        for suffix in ("", "-wal", "-shm"):
            (tmp_path / f"rebuilt.db{suffix}").write_bytes(b"garbage")
        result = rebuild(journal, out)
    assert result == out
    for suffix in ("-wal", "-shm"):
        assert not (tmp_path / f"rebuilt.db{suffix}").exists()
    with contextlib.closing(sqlite3.connect(str(out))) as conn:
        assert projection_hash(conn) == live


def test_rebuild_rolls_back_leaving_no_partial_rows(tmp_path):
    path = tmp_path / "courier.db"
    with Journal(path) as journal:
        for event in golden_path("t1"):
            journal.append(event)
        good = list(journal.events())
        forged = good[-1].sealed(7, good[-1].hash)
        journal.conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (7, "forged", forged.schema_v, forged.type.value, forged.task_id, forged.attempt,
             forged.dispatch_id, forged.worker_id, forged.result_id, None, forged.ts_utc,
             forged.payload_json, forged.prev_hash, forged.sealed(7, good[-1].hash).hash))
        with pytest.raises(ProjectionError, match="seq 7"):
            rebuild(journal, tmp_path / "rebuilt.db")
    # The failed rebuild rolls back everything, including the fresh schema:
    # no partial projection rows survive.
    with contextlib.closing(sqlite3.connect(str(tmp_path / "rebuilt.db"))) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tasks'").fetchone()
        assert tables is None
