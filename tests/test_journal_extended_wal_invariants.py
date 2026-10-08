import sqlite3
import pytest

from tests.core.core_builders import created, Attempt
from courier_core.events import GENESIS_HASH, Event, EventType
from courier_core.journal import DedupeConflict, Journal, JournalError


def test_journal_context_manager_and_closed_lifecycle(tmp_path):
    db_path = tmp_path / "lifecycle.db"
    with Journal(db_path) as j:
        assert j.conn is not None
        assert j.head() == (0, GENESIS_HASH)

    # After exiting context manager, accessing conn raises JournalError
    with pytest.raises(JournalError, match="journal is not open"):
        _ = j.conn


def test_journal_triggers_prevent_update_and_delete(tmp_path):
    db_path = tmp_path / "triggers.db"
    with Journal(db_path) as j:
        res = j.append(created("t1"))
        assert res.event.seq == 1
        assert res.duplicate is False

        # Direct UPDATE must fail closed due to BEFORE UPDATE trigger
        with pytest.raises(sqlite3.IntegrityError, match="courier journal is append-only"):
            j.conn.execute("UPDATE events SET payload = 'tampered' WHERE seq = 1")

        # Direct DELETE must fail closed due to BEFORE DELETE trigger
        with pytest.raises(sqlite3.IntegrityError, match="courier journal is append-only"):
            j.conn.execute("DELETE FROM events WHERE seq = 1")

        # Row remains untouched and intact
        row = j.conn.execute("SELECT seq, task_id FROM events WHERE seq = 1").fetchone()
        assert tuple(row) == (1, "t1")
        assert j.verify_chain().ok is True


def test_get_event_by_dedupe_key_and_conflicts(tmp_path):
    db_path = tmp_path / "dedupe.db"
    with Journal(db_path) as j:
        ev1 = created("task-dedupe")
        res1 = j.append(ev1)
        assert res1.duplicate is False

        # Retrieval by key
        found = j.get_event_by_dedupe_key("created:task-dedupe")
        assert found is not None
        assert found.task_id == "task-dedupe"

        # Missing key returns None
        assert j.get_event_by_dedupe_key("nonexistent:key") is None

        # Identical re-submission returns deduped event
        res2 = j.append(ev1)
        assert res2.duplicate is True
        assert res2.event.seq == res1.event.seq

        # Conflicting submission with same dedupe_key but different payload raises DedupeConflict
        conflicting = Event(
            type=EventType.TASK_CREATED,
            task_id="task-dedupe",
            dedupe_key="created:task-dedupe",
            payload={
                "adapter": "synthetic",
                "effect_class": "non_idempotent",
                "max_attempts": 99,
                "lease_ttl_s": 999,
                "params": {"altered": True},
            },
        )
        with pytest.raises(DedupeConflict):
            j.append(conflicting)


def test_journal_verify_chain_on_multiple_events(tmp_path):
    db_path = tmp_path / "chain.db"
    with Journal(db_path) as j:
        # Empty chain
        report0 = j.verify_chain()
        assert report0.ok is True
        assert report0.count == 0
        assert report0.head_seq == 0
        assert report0.first_bad_seq is None

        # 3 events in sequence
        a = Attempt("t-chain", 1)
        j.append(created("t-chain"))
        j.append(a.claimed())
        j.append(a.started())

        report1 = j.verify_chain()
        assert report1.ok is True
        assert report1.count == 3
        assert report1.head_seq == 3
        assert report1.first_bad_seq is None
        assert j.head()[0] == 3
