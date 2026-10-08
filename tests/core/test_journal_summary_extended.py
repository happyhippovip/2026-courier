import sqlite3
import pytest

from core_builders import Attempt, created, golden_path, task_event
from courier_core.events import GENESIS_HASH, EventType
from courier_core.journal import DedupeConflict, Journal, JournalError
from courier_core.state_machine import TaskStatus, TransitionError


class TestJournalSummaryExtended:
    """Rigorous edge-case coverage for SQLite journal append-only hash chains and transactions."""

    def test_readonly_mode_nonexistent_database_raises(self, tmp_path):
        j = Journal(tmp_path / "missing.db", readonly=True)
        with pytest.raises(JournalError, match="no journal to inspect"):
            j.open()

    def test_readonly_mode_prevents_modifications(self, tmp_path):
        db_path = tmp_path / "courier.db"
        # First create database with one event
        with Journal(db_path) as j_write:
            j_write.append(created("t1"))

        # Reopen in readonly mode
        with Journal(db_path, readonly=True) as j_ro:
            assert j_ro.head()[0] == 1
            # Appending or writing SQL must fail
            with pytest.raises(JournalError, match="journal is open read-only"):
                j_ro.append(created("t2"))

    def test_unsupported_schema_user_version_fails(self, tmp_path):
        db_path = tmp_path / "corrupt_version.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA user_version = 99")
        conn.close()

        with pytest.raises(JournalError, match="unsupported journal schema version 99"):
            with Journal(db_path) as j:
                pass

    def test_dedupe_conflict_with_divergent_payload(self, tmp_path):
        db_path = tmp_path / "dedupe.db"
        with Journal(db_path) as j:
            e1 = created("t1", dedupe_key="key-alpha", spec={"param": 1})
            res1 = j.append(e1)
            assert res1.duplicate is False

            # Same dedupe_key, but different payload -> must raise DedupeConflict
            e2 = created("t1", dedupe_key="key-alpha", spec={"param": 2})
            with pytest.raises(DedupeConflict):
                j.append(e2)

    def test_illegal_state_transition_rolls_back_completely(self, tmp_path):
        db_path = tmp_path / "rollback.db"
        with Journal(db_path) as j:
            j.append(created("t1"))
            seq_before, hash_before = j.head()

            # Attempt to append TASK_COMPLETE directly on TASK_CREATED (skipping claim/start)
            bad_event = Attempt("t1", 1).complete()
            with pytest.raises(TransitionError):
                j.append(bad_event)

            # Verification: absolutely nothing was written, chain is intact
            seq_after, hash_after = j.head()
            assert seq_after == seq_before
            assert hash_after == hash_before
            assert j.verify_chain().ok is True

    def test_events_filtering_by_seq_and_task(self, tmp_path):
        db_path = tmp_path / "filter.db"
        with Journal(db_path) as j:
            # Create two different tasks
            j.append(created("t1"))
            j.append(created("t2"))
            j.append(Attempt("t1", 1).claimed())
            j.append(Attempt("t2", 1).claimed())

            # Filter by task_id
            t1_events = list(j.events(task_id="t1"))
            assert len(t1_events) == 2
            assert all(e.task_id == "t1" for e in t1_events)

            # Filter by after_seq
            recent_events = list(j.events(after_seq=2))
            assert len(recent_events) == 2
            assert [e.seq for e in recent_events] == [3, 4]

            # Filter by both
            filtered = list(j.events(after_seq=2, task_id="t2"))
            assert len(filtered) == 1
            assert filtered[0].seq == 4
