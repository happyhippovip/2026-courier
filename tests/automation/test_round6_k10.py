"""[DRUIDE | ACCOUNT 2] K10: test gaps from the journal_export sweep and the critical watcher survivors (restart, recovery, journal integrity).
No change to the tools. Each test names the sweep mutant it kills (ids: deliver/SWEEP_K1_*.jsonl, line numbers of the sweep baseline bfe7dea0a).
"""

import io
import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from core_builders import golden_path  # noqa: E402
from courier_core.journal import JournalError  # noqa: E402
from test_ci_watcher_v2 import DONE, SHA, Clock, Gh  # noqa: E402
from test_journal_export import export, make_journal  # noqa: E402
from test_round5_k0c import TAKER, lock_file_of, state_file_of, watch  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402


# --- journal export: the --out file is complete on disk BEFORE the fsync and the rename (journal_export:359 handle.flush) ---

def test_k10_the_export_file_holds_all_its_bytes_when_it_is_fsynced(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    out = tmp_path / "export.jsonl"
    seen = []
    real_fsync = os.fsync

    def fsync(fd):
        if stat.S_ISREG(os.fstat(fd).st_mode):
            seen.append(os.fstat(fd).st_size)  # what the OS has got at the moment of the fsync (a Python-side buffer would not count)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    code, _, err = export(db, "--out", str(out))
    assert code == 0, err
    total = out.stat().st_size
    assert total > 0 and total in seen, f"fsync saw {seen}, the finished file has {total} bytes"


# --- journal export to stdout: the binary sink is flushed (journal_export:372 sink.flush) ---------------------------------

def test_k10_the_stdout_sink_is_flushed_at_the_end(tmp_path):
    db = make_journal(tmp_path / "courier.db")

    class Sink(io.BytesIO):
        flushed = 0

        def flush(self):
            Sink.flushed += 1
            super().flush()

    class Stdout:
        buffer = Sink()

    assert je.main([str(db)], stdout=Stdout(), stderr=io.StringIO()) == 0
    assert Sink.flushed >= 1 and Stdout.buffer.getvalue().count(b"\n") > 1


# --- the handle the exporter reads through can never append (journal_export:166 readonly=True) -----------------------------

def test_k10_the_readonly_journal_handle_refuses_to_append(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    journal = je.open_readonly(db)
    try:
        with pytest.raises(JournalError, match="read-only"):
            journal.append(golden_path()[0])
    finally:
        journal.close()


# --- watcher: the O_EXCL fallback (Windows) -----------------------------------------------------------------------------

def test_k10_reset_state_releases_its_lock_file_so_the_next_watch_is_not_locked(tmp_path, monkeypatch):  # ci_watcher_v2:465 lock.release()
    monkeypatch.setattr(w, "fcntl", None)
    first = watch(tmp_path, Gh(DONE), Clock(), dispatch=lambda: None)
    assert first["status"] == w.COMPLETED
    assert not lock_file_of(tmp_path).exists()
    assert w.reset_state("WK", SHA, tmp_path)["status"] == "RESET"
    assert not lock_file_of(tmp_path).exists(), "reset_state left its O_EXCL lock behind: the next run would be LOCKED for hours"
    again = watch(tmp_path, Gh(DONE), Clock())
    assert again["status"] != w.LOCKED


def test_k10_a_fresh_foreign_lock_gives_locked_with_zero_polls_and_no_gh_call(tmp_path, monkeypatch):  # :492 polls 0->1
    monkeypatch.setattr(w, "fcntl", None)
    lock_file_of(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    lock_file_of(tmp_path).write_text(TAKER)
    gh = Gh(DONE)
    result = watch(tmp_path, gh, Clock())
    assert result["status"] == w.LOCKED and result["exit_code"] == 13 and result["polls_this_call"] == 0
    assert gh.commands == [] and lock_file_of(tmp_path).read_text() == TAKER


def test_k10_a_state_dir_that_does_not_exist_yet_is_created_with_its_parents(tmp_path):  # :487 parents=True, :442
    nested = tmp_path / "a" / "b"
    result = watch(nested, Gh(DONE), Clock(), dispatch=lambda: None)
    assert result["status"] == w.COMPLETED and state_file_of(nested).exists()
    other = tmp_path / "c" / "d"
    assert w.reset_state("WK", SHA, other)["status"] == "NO_STATE" and other.is_dir()


def test_k10_a_stale_lock_that_vanishes_before_the_takeover_is_just_taken(tmp_path, monkeypatch):  # :343 return True
    monkeypatch.setattr(w, "fcntl", None)
    lock = w._Lock(tmp_path / "x.lock", stale_after=10)
    excl = tmp_path / "x.lock.x"
    excl.write_text(TAKER)
    old = excl.stat().st_mtime - 1000
    os.utime(excl, (old, old))
    lock._stale_hook = lambda: excl.unlink()  # the previous owner cleaned up right after we decided "stale"
    assert lock.acquire() is True and excl.read_text() == lock.token
    lock.release()
