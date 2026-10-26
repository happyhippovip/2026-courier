"""Red-team regression tests for tools/automation/journal_export.py (found by trying to break it)."""

import hashlib
import io
import json
import os
import shutil
import sqlite3
import sys
import threading
import tracemalloc
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))  # read-only fixture builders
from core_builders import golden_path  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402
from courier_core.journal import Journal

from test_journal_export import export, make_journal, snapshot, tamper  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def live_writer(directory):
    """A journal with an open writer: committed events sit in the -wal file."""
    writer = Journal(Path(directory) / "courier.db").open()
    for event in golden_path():
        writer.append(event)
    assert (Path(directory) / "courier.db-wal").exists()
    return writer


# --- symlink -------------------------------------------------------------------------------

def test_symlink_to_live_wal_database_reads_the_wal_of_the_real_file(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").mkdir()
    writer = live_writer(tmp_path / "real")
    try:
        os.symlink(tmp_path / "real" / "courier.db", tmp_path / "link" / "courier.db")
        direct = export(tmp_path / "real" / "courier.db")
        via_link = export(tmp_path / "link" / "courier.db")
    finally:
        writer.close()
    assert direct[0] == 0 and via_link == direct
    assert json.loads(direct[1].splitlines()[0])["event_count"] == len(golden_path())
    assert os.listdir(tmp_path / "link") == ["courier.db"]  # nothing created next to the link


def test_symlink_chain_and_dangling_symlink(tmp_path):
    real = make_journal(tmp_path / "real.db")
    os.symlink(real, tmp_path / "l1.db")
    os.symlink(tmp_path / "l1.db", tmp_path / "l2.db")
    assert export(tmp_path / "l2.db") == export(real)
    os.symlink(tmp_path / "nowhere.db", tmp_path / "dangling.db")
    code, out, err = export(tmp_path / "dangling.db")
    assert (code, out) == (3, "") and "no journal file" in err


def test_symlinked_idle_journal_stays_unchanged(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    real = make_journal(tmp_path / "a" / "courier.db")
    os.symlink(real, tmp_path / "b" / "courier.db")
    before = {d: snapshot(tmp_path / d) for d in ("a",)}
    assert export(tmp_path / "b" / "courier.db")[0] == 0
    assert snapshot(tmp_path / "a") == before["a"] and os.listdir(tmp_path / "b") == ["courier.db"]


# --- --out must never be the journal -----------------------------------------------------------

def test_out_equal_to_journal_is_refused_and_journal_untouched(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    before = snapshot(tmp_path)
    code, out, err = export(db, "--out", str(db))
    assert code == 2 and "refusing to overwrite" in err
    assert snapshot(tmp_path) == before


def test_out_through_symlink_hardlink_or_sidecar_name_is_refused(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    os.symlink(db, tmp_path / "alias.jsonl")
    os.link(db, tmp_path / "hard.jsonl")
    before = snapshot(tmp_path)
    for target in ("alias.jsonl", "hard.jsonl", "courier.db-wal", "courier.db-shm", "courier.db-journal"):
        assert export(db, "--out", str(tmp_path / target))[0] == 2, target
    assert snapshot(tmp_path) == before


def test_out_relative_path_equal_to_journal_is_refused(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    before = sha(db)
    monkeypatch.chdir(tmp_path)
    assert export("courier.db", "--out", "./courier.db")[0] == 2
    assert sha(db) == before


# --- WAL, concurrent writer, uncommitted transaction ---------------------------------------------

def test_wal_database_with_live_writer_exports_committed_events_and_creates_nothing(tmp_path):
    writer = live_writer(tmp_path)
    try:
        before = {n: v for n, v in snapshot(tmp_path).items() if n.endswith(("-wal", "-shm"))}
        code, out, _ = export(tmp_path / "courier.db")
        after = {n: v for n, v in snapshot(tmp_path).items() if n.endswith(("-wal", "-shm"))}
    finally:
        writer.close()
    assert code == 0 and json.loads(out.splitlines()[0])["event_count"] == len(golden_path())
    assert set(before) == set(after)


def test_uncommitted_writer_transaction_is_neither_blocking_nor_exported(tmp_path):
    writer = live_writer(tmp_path)
    try:
        writer.conn.execute("BEGIN IMMEDIATE")
        code, out, _ = export(tmp_path / "courier.db")
        writer.conn.execute("ROLLBACK")
    finally:
        writer.close()
    assert code == 0 and json.loads(out.splitlines()[0])["event_count"] == len(golden_path())


def test_orphan_wal_without_shm_after_killed_writer(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    writer = live_writer(src)
    try:
        dst = tmp_path / "dst"
        dst.mkdir()
        shutil.copy(src / "courier.db", dst / "courier.db")
        shutil.copy(src / "courier.db-wal", dst / "courier.db-wal")
    finally:
        writer.close()
    code, out, _ = export(dst / "courier.db")
    assert code == 0 and json.loads(out.splitlines()[0])["event_count"] == len(golden_path())


def test_concurrent_writer_every_export_is_a_consistent_snapshot(tmp_path):
    writer = Journal(tmp_path / "courier.db").open()
    stop, errors = threading.Event(), []

    def write():
        n = 0
        try:
            while not stop.is_set() and n < 150:
                for event in golden_path(task_id=f"w{n}"):
                    writer.append(event)
                n += 1
        except Exception as exc:  # pragma: no cover - reported through the assertion
            errors.append(repr(exc))

    thread = threading.Thread(target=write)
    thread.start()
    try:
        seen = []
        for _ in range(25):
            code, out, err = export(tmp_path / "courier.db")
            if code == 3 and "no such table" in err:  # writer has not created the schema yet
                continue
            assert code == 0, err
            lines = [json.loads(line) for line in out.splitlines()]
            header, events = lines[0], lines[1:]
            assert header["chain_ok"] and header["event_count"] == len(events) == header["head_seq"]
            assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
            seen.append(len(events))
    finally:
        stop.set()
        thread.join()
        writer.close()
    assert not errors and seen == sorted(seen)  # snapshots only ever grow


def test_sidecar_appearing_during_an_immutable_read_triggers_a_normal_readonly_reread(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    uris, original = [], je._readonly_uri
    monkeypatch.setattr(je, "_readonly_uri", lambda p, ok=True: uris.append(original(p, ok)) or uris[-1])
    verify = Journal.verify_chain
    state = {"first": True}

    def verify_then_writer_appears(self):
        report = verify(self)
        if state.pop("first", False):
            (tmp_path / "courier.db-wal").write_bytes(b"")  # a writer starts after we chose immutable
        return report

    monkeypatch.setattr(Journal, "verify_chain", verify_then_writer_appears)
    code, out, _ = export(db)
    assert code == 0 and json.loads(out.splitlines()[0])["event_count"] == len(golden_path())
    assert "immutable=1" in uris[0] and all("mode=ro" in u for u in uris)
    assert "immutable=1" not in uris[-1] and len(uris) >= 2


# --- invalid UTF-8 ---------------------------------------------------------------------------------

@pytest.mark.parametrize("column", ["task_id", "ts_utc", "type", "event_id", "dispatch_id"])
def test_invalid_utf8_in_a_text_column_is_a_clean_exit_4(tmp_path, column):
    db = make_journal(tmp_path / "courier.db")
    tamper(db, f"UPDATE events SET {column} = CAST(X'C328FF' AS TEXT) WHERE seq = 2")
    for flags in ((), ("--allow-partial",)):
        code, out, err = export(db, *flags)
        assert code == 4 and out == "" and "Traceback" not in err and "JOURNAL_EXPORT_ERROR" in err, (column, flags)


def test_invalid_utf8_in_payload_is_a_clean_exit_4(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    tamper(db, "UPDATE events SET payload = CAST(X'7B2261223AC328' AS TEXT) WHERE seq = 2")
    code, out, err = export(db)
    assert code == 4 and out == "" and "Traceback" not in err


# --- truncated files -----------------------------------------------------------------------------------

@pytest.mark.parametrize("fraction", [0, 0.002, 0.25, 0.5, 0.9])
def test_truncated_database_file_is_a_clean_exit_3_and_creates_nothing(tmp_path, fraction):
    full = make_journal(tmp_path / "full.db").read_bytes()
    target = tmp_path / "cut" / "courier.db"
    target.parent.mkdir()
    target.write_bytes(full[:int(len(full) * fraction)])
    before = snapshot(target.parent)
    code, out, err = export(target)
    assert (code, out) == (3, "") and "Traceback" not in err
    assert snapshot(target.parent) == before


def test_database_cut_inside_the_unused_tail_still_exports_intact_chain(tmp_path):
    """Dropping 1 byte of an unused tail page does not touch any event: chain verifies, export is complete."""
    full = make_journal(tmp_path / "full.db")
    cut = tmp_path / "cut.db"
    cut.write_bytes(full.read_bytes()[:-1])
    assert export(cut) == export(full)


def test_truncated_wal_never_crashes_and_never_invents_events(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    writer = live_writer(src)
    try:
        wal = (src / "courier.db-wal").read_bytes()
    finally:
        writer.close()
    full_events = len(golden_path())
    for keep in (0, 31, 32, 4000, len(wal) // 2, len(wal) - 1):
        dst = tmp_path / f"cut{keep}"
        dst.mkdir()
        shutil.copy(src / "courier.db", dst / "courier.db")
        (dst / "courier.db-wal").write_bytes(wal[:keep])
        code, out, err = export(dst / "courier.db")
        assert code in (0, 3, 4) and "Traceback" not in err, (keep, code, err)
        if code == 0:
            header = json.loads(out.splitlines()[0])
            assert header["chain_ok"] and header["event_count"] <= full_events


def test_truncated_tail_of_the_chain_is_visible_through_head_seq(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    full_head = json.loads(export(db)[1].splitlines()[0])["head_seq"]
    tamper(db, f"DELETE FROM events WHERE seq = {full_head}")
    header = json.loads(export(db)[1].splitlines()[0])
    assert header["chain_ok"] and header["head_seq"] == full_head - 1  # a consumer compares head_seq/head_hash


# --- huge journal ----------------------------------------------------------------------------------------

def test_large_journal_streams_in_constant_memory_and_is_deterministic(tmp_path):
    db = tmp_path / "courier.db"
    journal = Journal(db).open()
    journal.conn.execute("PRAGMA synchronous=OFF")
    for n in range(2000):
        for event in golden_path(task_id=f"big{n}"):
            journal.append(event)
    journal.close()
    out1, out2 = tmp_path / "one.jsonl", tmp_path / "two.jsonl"
    tracemalloc.start()
    code = je.main([str(db), "--out", str(out1)], stdout=io.StringIO(), stderr=io.StringIO())
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert code == 0 and out1.stat().st_size > 4_000_000
    assert peak < 3_000_000, f"peak {peak} bytes: output must be streamed, not built in memory"
    assert je.main([str(db), "--out", str(out2)], stdout=io.StringIO(), stderr=io.StringIO()) == 0
    assert sha(out1) == sha(out2)
    assert len(out1.read_text().splitlines()) == 2000 * len(golden_path()) + 1


# --- paths, pipes, interruption -------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["a b.db", "x#y.db", "q?z.db", "p%20q.db", "u\u00fc\u00e9.db", "-dash.db", "a'b.db"])
def test_unusual_file_names(tmp_path, name):
    db = make_journal(tmp_path / name)
    code, out, _ = export(db)
    assert code == 0 and json.loads(out.splitlines()[0])["event_count"] == len(golden_path())


def test_directory_empty_file_and_garbage_are_exit_3(tmp_path):
    (tmp_path / "empty.db").write_bytes(b"")
    (tmp_path / "garbage.db").write_bytes(os.urandom(5000))
    for target in (tmp_path, tmp_path / "empty.db", tmp_path / "garbage.db"):
        code, out, err = export(target)
        assert (code, out) == (3, "") and "Traceback" not in err, target


class ClosedPipe:
    def write(self, _):
        raise BrokenPipeError(32, "Broken pipe")


def test_broken_pipe_on_stdout_is_exit_6_and_journal_untouched(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    before = snapshot(tmp_path)
    err = io.StringIO()
    assert je.main([str(db)], stdout=ClosedPipe(), stderr=err) == 6
    assert "cannot write export" in err.getvalue() and snapshot(tmp_path) == before


def test_fold_error_gives_exit_5_and_no_partial_stdout(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    calls = {"n": 0}
    real_apply = je.apply_state

    def failing(state, event):
        calls["n"] += 1
        if calls["n"] == 3:
            raise ValueError("synthetic fold failure")
        return real_apply(state, event)

    monkeypatch.setattr(je, "apply_state", failing)
    code, out, err = export(db)
    assert code == 5 and out == "" and "does not fold" in err


def test_interrupt_while_writing_leaves_no_tmp_file_and_no_half_output(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    target = tmp_path / "export.jsonl"
    target.write_text("previous export\n")
    original, calls = je._walk, {"n": 0}

    def walk(*args, **kwargs):
        calls["n"] += 1
        for index, line in enumerate(original(*args, **kwargs)):
            if calls["n"] == 2 and index == 2:
                raise KeyboardInterrupt
            yield line

    monkeypatch.setattr(je, "_walk", walk)
    with pytest.raises(KeyboardInterrupt):
        export(db, "--out", str(target))
    assert target.read_text() == "previous export\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["courier.db", "export.jsonl"]
