"""L2 invariants: the SQLite journal (append-only, hash chain, dedupe, atomicity)."""

import itertools
import json
import sqlite3
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from core_builders import Attempt, created, golden_path, task_event
from courier_core.events import GENESIS_HASH, EventType
from courier_core.journal import DedupeConflict, Journal
from courier_core.projection import projection_hash
from courier_core.state_machine import TaskStatus, TransitionError

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def journal(tmp_path):
    with Journal(tmp_path / "courier.db") as j:
        yield j


def append_all(journal, events):
    return [journal.append(event) for event in events]


def test_open_creates_wal_journal_with_contract_columns(journal):
    assert journal.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    columns = [row[1] for row in journal.conn.execute("PRAGMA table_info(events)")]
    assert columns == ["seq", "event_id", "schema_v", "type", "task_id", "attempt", "dispatch_id", "worker_id",
                       "result_id", "dedupe_key", "ts_utc", "payload", "prev_hash", "hash"]
    assert journal.head() == (0, GENESIS_HASH)
    assert journal.verify_chain().ok


def test_golden_path_is_chained_contiguously(journal):
    results = append_all(journal, golden_path())
    assert [r.event.seq for r in results] == [1, 2, 3, 4, 5, 6]
    assert results[0].event.prev_hash == GENESIS_HASH
    for previous, current in zip(results, results[1:]):
        assert current.event.prev_hash == previous.event.hash
    report = journal.verify_chain()
    assert report.ok and report.count == 6 and report.head_hash == results[-1].event.hash
    assert journal.task("t1").status is TaskStatus.COMPLETE
    assert [e.type for e in journal.events(task_id="t1")] == [
        EventType.TASK_CREATED, EventType.TASK_CLAIMED, EventType.TASK_STARTED, EventType.RESULT_READY,
        EventType.RESULT_ACCEPTED, EventType.TASK_COMPLETE]
    assert all(json.loads(row[0]) is not None for row in journal.conn.execute("SELECT payload FROM events"))


def test_events_are_append_only(journal):
    append_all(journal, golden_path())
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        journal.conn.execute("UPDATE events SET payload = '{}' WHERE seq = 1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        journal.conn.execute("DELETE FROM events WHERE seq = 6")
    assert journal.verify_chain().ok


def test_illegal_event_writes_nothing(journal):
    append_all(journal, [created()])
    head, digest = journal.head(), projection_hash(journal.conn)
    with pytest.raises(TransitionError):
        journal.append(Attempt(attempt=2).claimed())
    with pytest.raises(TransitionError):
        journal.append(Attempt().result_ready())
    assert journal.head() == head and projection_hash(journal.conn) == digest
    assert journal.task("t1").status is TaskStatus.QUEUED


def test_duplicate_result_is_acknowledged_not_appended(journal):
    a = Attempt()
    append_all(journal, [created(), a.claimed(), a.started()])
    first = journal.append(a.result_ready())
    again = journal.append(a.result_ready())  # same content, new event_id and ts
    assert not first.duplicate and again.duplicate
    assert again.event.seq == first.event.seq and again.event.event_id == first.event.event_id
    assert journal.head()[0] == 4


def test_reused_dedupe_key_with_other_content_is_a_conflict(journal):
    a = Attempt()
    append_all(journal, [created(), a.claimed(), a.started(), a.result_ready()])
    head = journal.head()
    with pytest.raises(DedupeConflict):
        journal.append(a.result_ready(sha="f" * 64))
    assert journal.head() == head


def test_completion_is_stored_exactly_once(journal):
    append_all(journal, golden_path())
    a = Attempt()
    assert journal.append(a.complete()).duplicate
    with pytest.raises(DedupeConflict):
        journal.append(a._ev(EventType.TASK_COMPLETE, result_id="r-other"))
    rows = journal.conn.execute("SELECT COUNT(*) FROM events WHERE type = 'TASK_COMPLETE'").fetchone()[0]
    assert rows == 1


def test_tampering_is_located_by_verify_chain(journal):
    append_all(journal, golden_path())
    conn = journal.conn
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='events'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    body = json.loads(conn.execute("SELECT payload FROM events WHERE seq = 2").fetchone()[0])
    body["ttl_s"] = 600
    conn.execute("UPDATE events SET payload = ? WHERE seq = 2", (json.dumps(body),))
    report = journal.verify_chain()
    assert not report.ok and report.first_bad_seq == 2 and "hash mismatch" in report.reason
    assert report.head_seq == 1


def test_deleted_event_is_detected_as_a_gap(journal):
    append_all(journal, golden_path())
    conn = journal.conn
    conn.execute("DROP TRIGGER events_no_delete")
    conn.execute("DELETE FROM events WHERE seq = 3")
    report = journal.verify_chain()
    assert not report.ok and report.first_bad_seq == 4 and "gap" in report.reason


def test_state_survives_reopen(tmp_path):
    path = tmp_path / "courier.db"
    with Journal(path) as j:
        append_all(j, golden_path()[:4])
        before = (j.head(), projection_hash(j.conn))
    with Journal(path) as j:
        assert (j.head(), projection_hash(j.conn)) == before
        append_all(j, golden_path()[4:])
        assert j.verify_chain().ok and j.task("t1").status is TaskStatus.COMPLETE


CRASH_SCRIPT = textwrap.dedent("""
    import os, sys
    sys.path.insert(0, {root!r}); sys.path.insert(0, {tests!r})
    from core_builders import Attempt, created
    from courier_core.journal import Journal
    j = Journal({db!r}).open()
    j.append(created())
    if {mode!r} == "before_insert":
        import courier_core.projection as projection
        real_store = projection.store
        def dying_store(conn, state, seq):
            real_store(conn, state, seq)
            os._exit(17)
        projection.store = dying_store
    else:
        j.conn.create_function("die", 0, lambda: os._exit(17))
        j.conn.execute("CREATE TEMP TRIGGER die_after_insert AFTER INSERT ON events BEGIN SELECT die(); END")
    j.append(Attempt().claimed())
    os._exit(0)
""")


@pytest.mark.parametrize("mode", ["before_insert", "after_insert_before_commit"])
def test_crash_mid_append_leaves_whole_event_or_nothing(tmp_path, mode):
    db = tmp_path / "courier.db"
    script = CRASH_SCRIPT.format(root=str(REPO_ROOT), tests=str(Path(__file__).parent), db=str(db), mode=mode)
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 17, proc.stderr
    with Journal(db) as j:
        assert j.head()[0] == 1
        assert j.verify_chain().ok
        assert j.task("t1").status is TaskStatus.QUEUED and j.task("t1").attempt == 0
        assert j.verify_projection()
        j.append(Attempt().claimed())
        assert j.task("t1").status is TaskStatus.CLAIMED


def test_concurrent_appends_stay_contiguous(journal):
    errors = []

    def writer(n):
        try:
            for i in range(25):
                journal.append(created(f"c{n}-{i}"))
                journal.append(task_event(EventType.TASK_CANCEL_REQUESTED, task_id=f"c{n}-{i}"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert errors == []
    seqs = [row[0] for row in journal.conn.execute("SELECT seq FROM events ORDER BY seq")]
    assert seqs == list(range(1, 401))
    assert journal.verify_chain().ok and journal.verify_projection()


def test_read_only_reader_sees_committed_state_while_writer_is_open(journal):
    append_all(journal, golden_path())
    reader = sqlite3.connect(journal.path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        assert projection_hash(reader) == projection_hash(journal.conn)
        assert reader.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 6
    finally:
        reader.close()


def test_semantics_preserving_byte_edit_is_still_tampering(journal):
    """The chain covers the stored bytes, not just the JSON meaning."""
    append_all(journal, golden_path())
    conn = journal.conn
    conn.execute("DROP TRIGGER events_no_update")
    stored = conn.execute("SELECT payload FROM events WHERE seq = 1").fetchone()[0]
    reordered = json.dumps(dict(reversed(list(json.loads(stored).items()))), indent=1)
    assert json.loads(reordered) == json.loads(stored) and reordered != stored
    conn.execute("UPDATE events SET payload = ? WHERE seq = 1", (reordered,))
    report = journal.verify_chain()
    assert not report.ok and report.first_bad_seq == 1
