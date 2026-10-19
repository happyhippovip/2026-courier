"""P9 hardening for courier_core.journal: lifecycle, read-only mode, reads and guards.

Complements tests/core/test_core_journal.py (chain, dedupe, crash, concurrency)
without touching it: read-only open, sealed-event rejection, schema-version
fence, close semantics, quick_check/guards_present/projection_current,
claim_for_dispatch, tasks(status=...), events(after_seq=...),
get_event_by_dedupe_key miss, head tracking, prev_hash-link and invalid-row
chain reports, duplicate state echo, and projection-vs-chain divergence.
No network. SQLite on tmp_path only.
"""

import json
import sqlite3

import pytest

from core_builders import Attempt, created, golden_path
from courier_core.events import GENESIS_HASH, EventType
from courier_core.journal import DedupeConflict, Journal, JournalError
from courier_core.state_machine import TaskStatus


@pytest.fixture
def journal(tmp_path):
    with Journal(tmp_path / "courier.db") as j:
        yield j


def append_all(journal, events):
    return [journal.append(event) for event in events]


def drop_events_triggers(conn):
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='events'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')


def test_conn_before_open_raises(tmp_path):
    journal = Journal(tmp_path / "courier.db")
    with pytest.raises(JournalError, match="not open"):
        journal.conn  # noqa: B018


def test_close_is_idempotent_and_guards_conn(tmp_path):
    journal = Journal(tmp_path / "courier.db").open()
    journal.close()
    journal.close()
    with pytest.raises(JournalError, match="not open"):
        journal.conn  # noqa: B018


def test_double_open_returns_self(journal):
    assert journal.open() is journal


def test_readonly_open_missing_file_raises(tmp_path):
    with pytest.raises(JournalError, match="no journal to inspect"):
        Journal(tmp_path / "missing.db", readonly=True).open()


def test_readonly_journal_reads_but_refuses_append(tmp_path):
    path = tmp_path / "courier.db"
    with Journal(path) as writer:
        append_all(writer, golden_path())
        head = writer.head()
    with Journal(path, readonly=True) as reader:
        assert reader.head() == head
        assert len(list(reader.events())) == 6
        assert reader.task("t1").status is TaskStatus.COMPLETE
        with pytest.raises(JournalError, match="read-only"):
            reader.append(created("t2"))


def test_append_sealed_event_is_rejected(journal):
    sealed = journal.append(created()).event
    assert sealed.seq == 1 and sealed.hash is not None
    with pytest.raises(JournalError, match="already sealed"):
        journal.append(sealed)
    assert journal.head()[0] == 1


def test_unsupported_schema_version_is_rejected(tmp_path):
    path = tmp_path / "courier.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA user_version=999")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(JournalError, match="unsupported journal schema version 999"):
        Journal(path).open()


def test_quick_check_reports_ok_empty_and_populated(journal):
    assert journal.quick_check() == "ok"
    append_all(journal, golden_path())
    assert journal.quick_check() == "ok"


def test_guards_present_on_fresh_and_reopened_journals(tmp_path):
    path = tmp_path / "courier.db"
    with Journal(path) as journal:
        assert journal.guards_present()
    with Journal(path) as journal:
        assert journal.guards_present()


def test_guards_absent_after_trigger_drop(journal):
    drop_events_triggers(journal.conn)
    assert not journal.guards_present()


def test_projection_current_on_fresh_journal(journal):
    assert journal.projection_current()


def test_verify_projection_true_empty_and_populated(journal):
    assert journal.verify_projection()
    append_all(journal, golden_path())
    assert journal.verify_projection()


def test_projection_tamper_diverges_from_chain(journal):
    append_all(journal, golden_path())
    journal.conn.execute("DELETE FROM tasks WHERE task_id = 't1'")
    assert journal.task("t1") is None
    assert not journal.verify_projection()
    assert journal.verify_chain().ok


def test_claim_for_dispatch_hit_and_miss(journal):
    attempt = Attempt()
    append_all(journal, [created(), attempt.claimed(), attempt.started()])
    claim = journal.claim_for_dispatch(attempt.dispatch_id)
    assert claim is not None
    assert claim.type is EventType.TASK_CLAIMED
    assert claim.dispatch_id == attempt.dispatch_id
    assert journal.claim_for_dispatch("d-unknown-9") is None


def test_tasks_status_filter(journal):
    append_all(journal, golden_path("t1"))
    journal.append(created("t2"))
    assert sorted(t.task_id for t in journal.tasks()) == ["t1", "t2"]
    assert [t.task_id for t in journal.tasks(status="COMPLETE")] == ["t1"]
    assert [t.task_id for t in journal.tasks(status="QUEUED")] == ["t2"]
    assert journal.tasks(status="FAILED") == []


def test_events_after_seq_and_unknown_task(journal):
    append_all(journal, golden_path())
    assert [e.seq for e in journal.events(after_seq=4)] == [5, 6]
    assert len(list(journal.events(task_id="t1"))) == 6
    assert list(journal.events(task_id="t-unknown")) == []


def test_get_event_by_dedupe_key_hit_and_miss(journal):
    stored = journal.append(created("t1")).event
    assert stored.dedupe_key is not None
    found = journal.get_event_by_dedupe_key(stored.dedupe_key)
    assert found is not None and found.event_id == stored.event_id
    assert journal.get_event_by_dedupe_key("k-unknown") is None


def test_head_tracks_appends(journal):
    assert journal.head() == (0, GENESIS_HASH)
    first = journal.append(created()).event
    assert journal.head() == (1, first.hash)
    last = append_all(journal, golden_path("t2"))[-1].event
    assert journal.head() == (7, last.hash)


def test_prev_hash_break_is_located(journal):
    append_all(journal, golden_path())
    drop_events_triggers(journal.conn)
    journal.conn.execute("UPDATE events SET prev_hash = ? WHERE seq = 2", ("0" * 64,))
    report = journal.verify_chain()
    assert not report.ok
    assert report.first_bad_seq == 2
    assert "prev_hash" in report.reason


def test_invalid_stored_row_is_located(journal):
    append_all(journal, golden_path())
    drop_events_triggers(journal.conn)
    journal.conn.execute("UPDATE events SET payload = 'not-json{{' WHERE seq = 1")
    report = journal.verify_chain()
    assert not report.ok
    assert report.first_bad_seq == 1
    assert "invalid" in report.reason


def test_duplicate_append_echoes_prior_event_and_state(journal):
    attempt = Attempt()
    append_all(journal, [created(), attempt.claimed(), attempt.started()])
    first = journal.append(attempt.result_ready())
    again = journal.append(attempt.result_ready())
    assert not first.duplicate and again.duplicate
    assert again.event.seq == first.event.seq
    assert again.event.event_id == first.event.event_id
    assert again.event.hash == first.event.hash
    assert again.state == first.state


def test_dedupe_conflict_message_names_key(journal):
    attempt = Attempt()
    append_all(journal, [created(), attempt.claimed(), attempt.started(), attempt.result_ready()])
    with pytest.raises(DedupeConflict, match="already used"):
        journal.append(attempt.result_ready(sha="f" * 64))


def test_empty_chain_report_shape(journal):
    report = journal.verify_chain()
    assert report.ok and report.count == 0
    assert (report.head_seq, report.head_hash) == (0, GENESIS_HASH)
    assert report.first_bad_seq is None and report.reason is None


def test_event_payload_bytes_round_trip(journal):
    journal.append(created("t1", effect_class="idempotent"))
    stored = journal.conn.execute("SELECT payload FROM events WHERE seq = 1").fetchone()[0]
    assert json.loads(stored)["effect_class"] == "idempotent"
    assert journal.verify_chain().ok
