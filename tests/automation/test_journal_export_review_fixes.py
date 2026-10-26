"""[DRUIDE | ACCOUNT 2] Regression tests for the independent review (SCHURKE_REVIEW.md EX-1/EX-3/EX-4/T-3/B3, MAGIER B3).

Real behaviour, no mocks of the code under test: real SQLite files, real writer processes, a real exporter process
whose stdout pipe is not drained while the writer runs.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from core_builders import Attempt, created, golden_path  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402
from courier_core.journal import Journal

from test_journal_export import export, make_journal, snapshot, tamper, without_sidecars  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX file permissions / process behaviour")
CHMOD_INEFFECTIVE = sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0)
NEEDS_EFFECTIVE_CHMOD = pytest.mark.skipif(
    CHMOD_INEFFECTIVE, reason="SKIPPED, NOT PASSED: chmod 555 does not make a directory read-only for root/Windows; the same "
                              "read-only-medium code path is exercised there by test_journal_export_round3.py::test_n_e5_* (forced medium)")

WRITER = textwrap.dedent("""
    import itertools, sys
    sys.path.insert(0, sys.argv[1] + "/tests/core"); sys.path.insert(0, sys.argv[1])
    import core_builders; core_builders._counter = itertools.count(1_000_000)
    from core_builders import Attempt, created
    from courier_core.journal import Journal
    j = Journal(sys.argv[2]).open(); j.conn.execute("PRAGMA synchronous=OFF"); j.conn.execute("PRAGMA busy_timeout=1"); a = Attempt(task_id="late")
    j.append(created(task_id="late")); j.append(a.claimed()); j.append(a.started())
    for n in range(int(sys.argv[3])):
        j.append(a.progress("w" * 800 + str(n)))
        if n % 20 == 19:
            j.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # like the real controller: the main file changes
    j.close()
""")


def big_journal(path, progress=6000):
    with Journal(path) as journal:
        journal.conn.execute("PRAGMA synchronous=OFF")
        attempt = Attempt(task_id="p")
        for event in (created(task_id="p"), attempt.claimed(), attempt.started()):
            journal.append(event)
        for n in range(progress):
            journal.append(attempt.progress("y" * 600 + str(n)))
    return Path(path)


def exporter_process(db, *flags):
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.Popen([sys.executable, "-m", "tools.automation.journal_export", str(db), *flags], cwd=REPO_ROOT,
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def run_writer(db, events):
    subprocess.run([sys.executable, "-c", WRITER, str(REPO_ROOT), str(db), str(events)], check=True, cwd=REPO_ROOT,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=120)


# ------------------------------------------------------------------ EX-3 (BLOCKER)

def test_ex3_writer_starting_while_the_output_pipe_is_blocked_cannot_truncate_the_export(tmp_path):
    """Schurke repro ex3: header says N events, exit 0, fewer lines. Contract now: if exit 0, every announced
    line is there; any deviation is a defined error code, never a silent short export."""
    db = big_journal(tmp_path / "courier.db")
    proc = exporter_process(db)
    header = json.loads(proc.stdout.readline())  # exporter is now blocked writing into the full pipe (pass 2)
    run_writer(db, 1500)  # a live controller starts, appends and checkpoints in the middle of the export
    rest = proc.stdout.read().splitlines()
    err = proc.stderr.read().decode()
    code = proc.wait(timeout=60)
    assert header["event_count"] == 6003 and header["chain_ok"] is True
    if code == 0:
        assert len(rest) == header["event_count"], "exit 0 with a short export"
        assert json.loads(rest[-1])["hash"] == header["head_hash"]
    else:
        assert code == je.EXIT_CHANGED and "JOURNAL_EXPORT_ERROR code=7" in err


def test_ex3_the_default_open_is_a_snapshot_reader_not_immutable_on_a_writable_medium(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    journal = je.open_readonly(db)
    try:
        assert journal.immutable_open is False
    finally:
        journal.close()


def test_ex3_the_second_pass_refuses_a_snapshot_that_differs_from_the_verified_one(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    journal = je.open_readonly(db)
    try:
        count = len(golden_path())
        assert len(list(je._walk(journal, count, False, journal.verify_chain().head_hash))) == count
        with pytest.raises(je.ExportError) as short:  # fewer events than were verified
            list(je._walk(journal, count + 4, False, None))
        assert short.value.code == je.EXIT_CHANGED
        with pytest.raises(je.ExportError) as other:  # same count, different head
            list(je._walk(journal, count, False, "0" * 64))
        assert other.value.code == je.EXIT_CHANGED
    finally:
        journal.close()


@NEEDS_EFFECTIVE_CHMOD
def test_ex3_immutable_read_on_a_read_only_medium_detects_a_change_and_exits_7(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    os.chmod(tmp_path, 0o555)
    try:
        assert not os.access(tmp_path, os.W_OK), "chmod 555 had no effect on this filesystem: not skipping silently"
        stream, code, close = je.export_stream(db)
        try:
            next(stream)  # header: pass 1 is done, pass 2 has not started
            os.utime(db, ns=(1_000_000_000, 1_000_000_000))  # the file is replaced/touched underneath the reader
            with pytest.raises(je.ExportError) as caught:
                list(stream)
            assert caught.value.code == je.EXIT_CHANGED
        finally:
            close()
    finally:
        os.chmod(tmp_path, 0o755)


@NEEDS_EFFECTIVE_CHMOD
def test_ex3_changed_journal_with_out_never_replaces_the_previous_export(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    target = tmp_path / "export.jsonl"
    target.write_text("previous export\n")
    os.chmod(tmp_path, 0o555)  # no tmp file possible here: use a second directory for --out
    try:
        assert not os.access(tmp_path, os.W_OK), "chmod 555 had no effect on this filesystem: not skipping silently"
        outdir = tmp_path.parent / (tmp_path.name + "_out")
        outdir.mkdir()
        out = outdir / "export.jsonl"
        out.write_text("previous export\n")
        stream, _, close = je.export_stream(db)
        try:
            os.utime(db, ns=(2_000_000_000, 2_000_000_000))
            with pytest.raises(je.ExportError):
                list(stream)
        finally:
            close()
        assert out.read_text() == "previous export\n"
    finally:
        os.chmod(tmp_path, 0o755)


# ------------------------------------------------------------------ EX-4

@NEEDS_EFFECTIVE_CHMOD
def test_ex4_read_only_directory_exports_cleanly_and_creates_nothing(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    before = snapshot(tmp_path)
    os.chmod(tmp_path, 0o555)
    try:
        assert not os.access(tmp_path, os.W_OK), "chmod 555 had no effect on this filesystem: not skipping silently"
        code, out, err = export(db)
    finally:
        os.chmod(tmp_path, 0o755)
    assert code == 0 and "Traceback" not in err and len(out.splitlines()) == len(golden_path()) + 1
    assert snapshot(tmp_path) == before  # not even sidecars


@NEEDS_EFFECTIVE_CHMOD
def test_ex4_read_only_directory_with_a_changed_file_has_its_own_exit_code_not_a_traceback(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    os.chmod(tmp_path, 0o555)
    try:
        assert not os.access(tmp_path, os.W_OK), "chmod 555 had no effect on this filesystem: not skipping silently"
        stream, _, close = je.export_stream(db)
        os.utime(db, ns=(3_000_000_000, 3_000_000_000))
        with pytest.raises(je.ExportError) as caught:
            list(stream)
        close()
    finally:
        os.chmod(tmp_path, 0o755)
    assert caught.value.code == 7


# ------------------------------------------------------------------ EX-1 honest documentation

def test_ex1_docs_state_that_shm_may_change_and_that_db_and_wal_never_do():
    doc = je.__doc__
    assert "-shm" in doc and "never writes to the journal database or its -wal" in doc
    assert "writes nothing but" not in doc
    assert "exit 7" in doc.replace("Exit codes", "") or "7 journal changed" in doc


# ------------------------------------------------------------------ B3 truncated tail

def test_b3_a_cut_off_tail_is_not_detectable_alone_so_the_header_says_head_not_checked(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    tamper(db, f"DELETE FROM events WHERE seq = {len(golden_path())}")  # last event removed, chain still valid
    code, out, _ = export(db)
    header = json.loads(out.splitlines()[0])
    assert code == 0 and header["chain_ok"] and header["head_seq"] == len(golden_path()) - 1
    assert header["head_checked"] is False  # the consumer must not read exit 0 as "complete"


def test_b3_expect_head_hash_detects_the_cut_off_tail_with_exit_8(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    good = json.loads(export(db)[1].splitlines()[0])["head_hash"]
    code, out, _ = export(db, "--expect-head-hash", good)
    assert code == 0 and json.loads(out.splitlines()[0])["head_checked"] is True
    tamper(db, f"DELETE FROM events WHERE seq = {len(golden_path())}")
    code, out, err = export(db, "--expect-head-hash", good)
    assert code == 8 and out == "" and "differs from expected" in err
