"""Journal status export: integrity gate, determinism, broken chains, read-only proof."""

import hashlib
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from core_builders import Attempt, created, golden_path
from courier_core import journal_export as je
from courier_core.events import Event, EventType
from courier_core.journal import Journal

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_journal(path, events=None):
    with Journal(path) as journal:
        for event in (golden_path() if events is None else events):
            journal.append(event)
    return Path(path)


def snapshot(directory):
    out = {}
    for item in sorted(Path(directory).iterdir()):
        stat = item.stat()
        out[item.name] = (stat.st_size, stat.st_mtime_ns, hashlib.sha256(item.read_bytes()).hexdigest())
    return out


def export(path, *flags):
    out, err = io.StringIO(), io.StringIO()
    code = je.main([str(path), *flags], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def tamper(path, *statements):
    """Edit a journal behind the append-only triggers, as a bad actor or a corrupt disk would."""
    conn = sqlite3.connect(str(path))
    conn.execute("DROP TRIGGER events_no_update")
    conn.execute("DROP TRIGGER events_no_delete")
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    conn.close()


def lines_of(text):
    return [json.loads(line) for line in text.splitlines()]


# ------------------------------------------------------------ integrity / content

def test_export_of_golden_path_lists_every_state_change_in_sequence_order(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    code, text, err = export(db)
    assert code == 0 and err == ""
    header, *events = lines_of(text)
    assert header["record"] == "header" and header["chain_ok"] is True and header["partial"] is False
    assert header["event_count"] == 6 and header["head_seq"] == 6 and header["format"] == je.FORMAT
    assert [e["seq"] for e in events] == [1, 2, 3, 4, 5, 6]
    assert [(e["from_status"], e["to_status"]) for e in events] == [
        (None, "QUEUED"), ("QUEUED", "CLAIMED"), ("CLAIMED", "RUNNING"), ("RUNNING", "VERIFYING"),
        ("VERIFYING", "ACCEPTED"), ("ACCEPTED", "COMPLETE")]
    assert header["head_hash"] == events[-1]["hash"]
    with Journal(db, readonly=True) as journal:  # the export is exactly the journal, nothing invented
        stored = list(journal.events())
    assert [(e["seq"], e["type"], e["hash"], e["ts_utc"]) for e in events] == [
        (s.seq, s.type.value, s.hash, s.ts_utc) for s in stored]


def test_every_line_is_sorted_compact_json_and_no_export_time_leaks(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    _, text, _ = export(db)
    for line in text.splitlines():
        value = json.loads(line)
        assert line == json.dumps(value, sort_keys=True, separators=(",", ":"))
    assert text.endswith("\n")
    assert str(tmp_path) not in text  # the path of the file is not part of the data


def test_payload_is_never_copied_only_its_sha256(tmp_path):
    secret = "owner-token-LOOKS-SECRET"
    db = make_journal(tmp_path / "courier.db", [created(secret_note=secret)])
    _, text, _ = export(db)
    assert secret not in text
    record = lines_of(text)[1]
    with Journal(db, readonly=True) as journal:
        payload_text = journal.conn.execute("SELECT payload FROM events WHERE seq = 1").fetchone()[0]
    assert record["payload_sha256"] == hashlib.sha256(payload_text.encode()).hexdigest()


def test_only_transitions_drops_events_without_status_change(tmp_path):
    attempt = Attempt()
    db = make_journal(tmp_path / "courier.db", [created(), attempt.claimed(), attempt.started(), attempt.progress()])
    _, all_text, _ = export(db)
    _, only_text, _ = export(db, "--only-transitions")
    assert len(lines_of(all_text)) == 5 and len(lines_of(only_text)) == 4
    assert all(e["transition"] for e in lines_of(only_text)[1:])
    assert lines_of(only_text)[0]["only_transitions"] is True


def test_system_events_are_exported_without_a_task_status(tmp_path):
    events = [Event(type=EventType.CONTROLLER_STARTED, event_id="evt-sys-1", ts_utc="2026-10-01T00:00:00.000000Z"),
              *golden_path()]
    db = make_journal(tmp_path / "courier.db", events)
    record = lines_of(export(db)[1])[1]
    assert record["type"] == "CONTROLLER_STARTED" and record["from_status"] is None and record["to_status"] is None
    assert record["transition"] is False


# ------------------------------------------------------------ repeatability

def test_repeated_export_is_byte_identical_and_stdout_equals_out_file(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    runs = [export(db)[1] for _ in range(3)]
    assert len({hashlib.sha256(r.encode()).hexdigest() for r in runs}) == 1
    out_file = tmp_path / "status.jsonl"
    assert je.main([str(db), "--out", str(out_file)], stderr=io.StringIO()) == 0
    assert out_file.read_bytes() == runs[0].encode()


def test_copy_of_a_journal_in_another_place_exports_identical_bytes(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    (tmp_path / "elsewhere").mkdir()
    copy = shutil.copyfile(db, tmp_path / "elsewhere" / "renamed.sqlite")
    assert export(db)[1] == export(copy)[1]


def test_command_line_entry_point_matches_in_process_export(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    proc = subprocess.run([sys.executable, "-m", "courier_core.journal_export", str(db)], cwd=REPO_ROOT,
                          capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=60)
    assert proc.returncode == 0 and proc.stdout == export(db)[1].encode()


# ------------------------------------------------------------ broken chains

@pytest.mark.parametrize("name,statements,first_bad", [
    ("modified_row", ["UPDATE events SET ts_utc = '2026-12-31T00:00:00.000000Z' WHERE seq = 3"], 3),
    ("modified_payload_same_json", ["UPDATE events SET payload = payload || ' ' WHERE seq = 2"], 2),
    ("missing_row", ["DELETE FROM events WHERE seq = 3"], 4),
    ("swapped_order", ["UPDATE events SET seq = -1 WHERE seq = 2", "UPDATE events SET seq = 2 WHERE seq = 3",
                       "UPDATE events SET seq = 3 WHERE seq = -1"], 2),
])
def test_broken_chain_exits_4_and_exports_nothing_by_default(tmp_path, name, statements, first_bad):
    db = make_journal(tmp_path / "courier.db")
    tamper(db, *statements)
    code, text, err = export(db)
    assert code == 4 and text == ""
    assert "hash chain broken" in err and f"seq {first_bad}" in err


def test_allow_partial_exports_only_the_verified_prefix_and_still_exits_4(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    tamper(db, "UPDATE events SET ts_utc = '2026-12-31T00:00:00.000000Z' WHERE seq = 4")
    code, text, err = export(db, "--allow-partial")
    assert code == 4 and "PARTIAL" in err
    header, *events = lines_of(text)
    assert header["chain_ok"] is False and header["partial"] is True and header["first_bad_seq"] == 4
    assert [e["seq"] for e in events] == [1, 2, 3]


def test_tail_truncation_is_visible_in_header_head_seq(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    full_head = lines_of(export(db)[1])[0]["head_hash"]
    tamper(db, "DELETE FROM events WHERE seq = 6")
    code, text, _ = export(db)
    header = lines_of(text)[0]
    assert code == 0 and header["head_seq"] == 5 and header["head_hash"] != full_head


def test_bad_json_payload_and_unknown_type_are_chain_failures_not_crashes(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    tamper(db, "UPDATE events SET payload = '{not json' WHERE seq = 2")
    assert export(db)[0] == 4
    db2 = make_journal(tmp_path / "second.db")
    tamper(db2, "UPDATE events SET type = 'MADE_UP' WHERE seq = 2")
    assert export(db2)[0] == 4


# ------------------------------------------------------------ empty / missing / not a journal

def test_empty_journal_exports_header_only_with_exit_0(tmp_path):
    db = tmp_path / "courier.db"
    Journal(db).open().close()
    code, text, _ = export(db)
    assert code == 0
    (header,) = lines_of(text)
    assert header["event_count"] == 0 and header["head_seq"] == 0 and header["chain_ok"] is True
    assert header["head_hash"] == "0" * 64


def test_missing_file_exits_3_and_creates_nothing(tmp_path):
    code, text, err = export(tmp_path / "nope.db")
    assert code == 3 and text == "" and "no journal file" in err
    assert list(tmp_path.iterdir()) == []


def test_non_database_and_foreign_database_exit_3(tmp_path):
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"this is not sqlite" * 100)
    foreign = tmp_path / "foreign.db"
    conn = sqlite3.connect(str(foreign))
    conn.execute("CREATE TABLE other(x)")
    conn.commit()
    conn.close()
    for path in (junk, foreign):
        before = snapshot(tmp_path)
        code, text, err = export(path)
        assert code == 3 and text == "" and "cannot read journal" in err
        assert snapshot(tmp_path) == before


def test_usage_error_exits_2(capsys):
    assert je.main([]) == 2


def test_unwritable_out_path_exits_6_after_a_good_read(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    err = io.StringIO()
    assert je.main([str(db), "--out", str(tmp_path / "missing_dir" / "x.jsonl")], stderr=err) == 6


# ------------------------------------------------------------ read-only proof

def test_export_changes_nothing_on_an_idle_journal_and_creates_no_sidecars(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["courier.db"]
    before = snapshot(tmp_path)
    for _ in range(3):
        assert export(db)[0] == 0
    assert snapshot(tmp_path) == before  # same names, sizes, mtimes (ns) and sha256


def test_export_works_on_a_read_only_directory_and_file(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    before = snapshot(tmp_path)
    os.chmod(db, 0o444)
    os.chmod(tmp_path, 0o555)
    try:
        if os.access(tmp_path, os.W_OK):
            pytest.skip("running with privileges that ignore directory permissions")
        assert export(db)[0] == 0
    finally:
        os.chmod(tmp_path, 0o755)
        os.chmod(db, 0o644)
    assert snapshot(tmp_path) == before


def test_export_beside_a_live_writer_leaves_database_and_wal_untouched_and_adds_no_files(tmp_path):
    db = tmp_path / "courier.db"
    writer = Journal(db).open()  # live controller: WAL + SHM exist and hold committed events
    try:
        for event in golden_path():
            writer.append(event)
        names_before = sorted(p.name for p in tmp_path.iterdir())
        assert "courier.db-wal" in names_before
        before = snapshot(tmp_path)
        code, text, _ = export(db)
        after = snapshot(tmp_path)
    finally:
        writer.close()
    assert code == 0 and len(lines_of(text)) == 7  # committed WAL events are included
    assert sorted(after) == names_before, "export must not create or remove files"
    for name in ("courier.db", "courier.db-wal"):
        assert after[name] == before[name], f"{name} changed"


def test_export_does_not_use_the_network(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")

    def deny(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    assert export(db)[0] == 0


def test_module_imports_no_network_clock_or_model_libraries():
    source = (REPO_ROOT / "courier_core" / "journal_export.py").read_text(encoding="utf-8")
    for banned in ("import requests", "import socket", "import urllib", "import http", "import subprocess",
                   "import time", "import random", "import uuid", "datetime", "utc_now", "new_id"):
        assert banned not in source, banned
    assert "INSERT" not in source and "UPDATE" not in source and "DELETE" not in source


def test_control_a_plain_mode_ro_open_would_have_created_sidecars(tmp_path):
    """Why the exporter opens idle journals immutable: SQLite's own mode=ro reader
    creates -wal/-shm beside a WAL database (this is the behaviour being avoided)."""
    db = make_journal(tmp_path / "courier.db")
    conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    conn.execute("SELECT count(*) FROM events").fetchone()
    conn.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["courier.db", "courier.db-shm", "courier.db-wal"]
