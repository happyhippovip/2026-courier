"""[DRUIDE | ACCOUNT 2] K2 findings: cases the seeded fuzz (test_round5_k2_fuzz.py) found, pinned as fixed regression tests."""

import io
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_round5_k2_fuzz import build, edit, export  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402


@pytest.mark.parametrize("column", ["event_id", "type", "task_id", "dispatch_id", "worker_id", "result_id", "ts_utc", "payload", "prev_hash", "hash"])
@pytest.mark.parametrize("seq", [1, 3])
def test_k2_f1_invalid_utf8_in_any_text_column_is_exit_4_never_a_traceback(tmp_path, column, seq):
    path, count, _ = build(tmp_path, 5)
    edit(path, f"UPDATE events SET {column} = CAST(x'c3ff41' AS TEXT) WHERE seq = {seq}")
    code, out, err = export(path)
    assert code == 4 and out == "" and err.startswith("JOURNAL_EXPORT_ERROR code=4"), (code, err)
    assert "Traceback" not in err


@pytest.mark.parametrize("needle", [b"BEFORE UPDATE ON events", b"CREATE TABLE events", b"events_task", b"projection_meta"])
def test_k2_f1_invalid_utf8_inside_the_stored_schema_is_exit_4_not_a_traceback(tmp_path, needle):
    """Found by seed 83 of the byte-flip fuzz: a flipped bit in the SQL text of sqlite_master made sqlite3 raise UnicodeDecodeError at open time."""
    path, _, _ = build(tmp_path, 83)
    data = path.read_bytes()
    assert needle in data
    path.write_bytes(data.replace(needle, needle[:-1] + b"\xcf", 1))  # same length, last character replaced by an invalid UTF-8 byte
    code, out, err = export(path)
    assert code in (3, 4) and out == "" and err.startswith("JOURNAL_EXPORT_ERROR") and "Traceback" not in err, (code, err)
