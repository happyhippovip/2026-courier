"""L2 invariants: deterministic projections and replay."""

import contextlib
import sqlite3

import pytest

from core_builders import golden_path, mixed_history, stable
from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_core.projection import (
    ProjectionError, fold, projection_hash, rebuild, is_current, load_task, apply_event, _from_row, PROJECTION_VERSION
)
from courier_core.state_machine import TaskStatus


def ro(path):
    return contextlib.closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True))


def fill(path, events):
    with Journal(path) as j:
        for event in events:
            j.append(event)
        return projection_hash(j.conn)


def test_rebuild_reproduces_the_live_projection(tmp_path):
    live = fill(tmp_path / "courier.db", mixed_history())
    with Journal(tmp_path / "courier.db") as j:
        out = rebuild(j, tmp_path / "rebuilt.db")
        assert j.verify_projection()
    with ro(out) as conn:
        assert projection_hash(conn) == live
        statuses = dict(conn.execute("SELECT task_id, status FROM tasks"))
    assert statuses == {"ta": "COMPLETE", "tb": "COMPLETE", "tc": "COMPLETE"}


def test_rebuild_overwrites_a_stale_target(tmp_path):
    live = fill(tmp_path / "courier.db", golden_path())
    (tmp_path / "rebuilt.db").write_bytes(b"garbage")
    with Journal(tmp_path / "courier.db") as j:
        out = rebuild(j, tmp_path / "rebuilt.db")
    with ro(out) as conn:
        assert projection_hash(conn) == live


def test_identical_histories_give_identical_chains_and_projections(tmp_path):
    events = mixed_history()
    fill(tmp_path / "a.db", events)
    fill(tmp_path / "b.db", events)
    with ro(tmp_path / "a.db") as a, ro(tmp_path / "b.db") as b:
        assert a.execute("SELECT hash FROM events ORDER BY seq").fetchall() == \
            b.execute("SELECT hash FROM events ORDER BY seq").fetchall()
        assert projection_hash(a) == projection_hash(b)


def test_projection_does_not_depend_on_event_ids_or_timestamps(tmp_path):
    first = fill(tmp_path / "a.db", golden_path())
    second = fill(tmp_path / "b.db", golden_path())  # fresh ids and timestamps
    assert first == second


def test_controller_lifecycle_events_do_not_change_the_fingerprint(tmp_path):
    path = tmp_path / "courier.db"
    before = fill(path, golden_path())
    with Journal(path) as j:
        j.append(Event(**stable(type=EventType.CONTROLLER_STOPPED)))
        j.append(Event(**stable(type=EventType.CONTROLLER_STARTED)))
        assert projection_hash(j.conn) == before


def test_sql_projection_matches_pure_fold(tmp_path):
    events = mixed_history()
    with Journal(tmp_path / "courier.db") as j:
        for event in events:
            j.append(event)
        stored = {state.task_id: state for state in j.tasks()}
        replayed = fold(j.events())
    assert stored == replayed
    assert replayed["tc"].late_results == 1 and replayed["tb"].attempt == 3


def test_illegal_history_cannot_be_rebuilt(tmp_path):
    path = tmp_path / "courier.db"
    fill(path, golden_path())
    with Journal(path) as j:
        good = list(j.events())
        # forge a second completion behind the journal's back (triggers bypassed via raw insert)
        forged = good[-1].sealed(7, good[-1].hash)
        j.conn.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            7, "forged", forged.schema_v, forged.type.value, forged.task_id, forged.attempt, forged.dispatch_id,
            forged.worker_id, forged.result_id, None, forged.ts_utc, forged.payload_json, forged.prev_hash,
            forged.sealed(7, good[-1].hash).hash))
        with pytest.raises(ProjectionError, match="seq 7"):
            rebuild(j, tmp_path / "rebuilt.db")


def test_golden_harness_offline_verify_and_rebuild_contract(tmp_path):
    """The exact calls tests/golden makes on a copy of a live journal."""
    path = tmp_path / "courier.db"
    with Journal(path) as live:
        for event in mixed_history():
            live.append(event)
        live_hash = projection_hash(live.conn)
        copy = tmp_path / "copy.db"
        with ro(path) as src, contextlib.closing(sqlite3.connect(str(copy))) as dst:
            src.backup(dst)
    journal = Journal(copy)
    journal.open()
    try:
        report = journal.verify_chain()
        out = rebuild(journal, tmp_path / "rebuilt.db")
    finally:
        journal.close()
    assert report.ok
    with ro(copy) as c, ro(out) as r:
        assert projection_hash(c) == live_hash == projection_hash(r)
    with ro(out) as r:
        assert r.execute("SELECT status FROM tasks WHERE task_id='ta'").fetchone()[0] == TaskStatus.COMPLETE.value


def test_fingerprint_distinguishes_states(tmp_path):
    complete = fill(tmp_path / "a.db", golden_path())
    partial = fill(tmp_path / "b.db", golden_path()[:3])
    other_task = fill(tmp_path / "c.db", golden_path("t-other"))
    assert len({complete, partial, other_task}) == 3
    with Journal(tmp_path / "a.db") as j:
        j.conn.execute("UPDATE tasks SET status = 'FAILED' WHERE task_id = 't1'")
        assert projection_hash(j.conn) != complete
        assert not j.verify_projection()


def test_is_current_checks_version(tmp_path):
    path = tmp_path / "courier.db"
    with contextlib.closing(sqlite3.connect(str(path))) as conn:
        assert not is_current(conn)
    fill(path, golden_path())
    with contextlib.closing(sqlite3.connect(str(path))) as conn:
        assert is_current(conn)
        conn.execute("UPDATE projection_meta SET value = '9999' WHERE key = 'version'")
        assert not is_current(conn)


def test_apply_event_rejects_unsealed_events(tmp_path):
    path = tmp_path / "courier.db"
    fill(path, golden_path())
    with Journal(path) as j:
        unsealed = Event(**stable(type=EventType.CONTROLLER_STARTED))
        with pytest.raises(ProjectionError, match="only sealed events"):
            apply_event(j.conn, unsealed)


def test_load_non_existent_task(tmp_path):
    path = tmp_path / "courier.db"
    fill(path, golden_path())
    with Journal(path) as j:
        assert load_task(j.conn, "non_existent") is None
        assert load_task(j.conn, None) is None


def test_from_row_column_count_mismatch():
    with pytest.raises(ValueError, match="Column count mismatch"):
        _from_row((1, 2))
