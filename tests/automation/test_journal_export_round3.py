"""[DRUIDE | ACCOUNT 2] Last fix round (SCHURKE_REREVIEW.md N-E1..N-E5, MAGIER_NACHTEST.md E4 note) for tools/automation/journal_export.py.

Real SQLite files and the real `main()`; the only seam used is monkeypatching `medium_is_read_only` to force the
read-only-medium path so that it is tested even where chmod has no effect (root, Windows).
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from core_builders import golden_path  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402

from test_journal_export import export, make_journal, snapshot, tamper  # noqa: E402


def good_head(db):
    return json.loads(export(db)[1].splitlines()[0])["head_hash"]


# ------------------------------------------------------------------ (1) --expect-head-hash is validated / normalised (N-E3)

@pytest.mark.parametrize("junk", ["", "zzz", "abc", "g" * 64, "a" * 63, "a" * 65, "0x" + "a" * 62, "a" * 32 + " " + "a" * 31,
                                  "../../etc/passwd", "ａ" * 64])
def test_n_e3_a_malformed_head_hash_is_a_usage_error_not_a_head_mismatch(tmp_path, junk):
    db = make_journal(tmp_path / "courier.db")
    before = snapshot(tmp_path)
    code, out, err = export(db, "--expect-head-hash", junk)
    assert code == 2 and out == "" and "--expect-head-hash" in err and "Traceback" not in err
    assert snapshot(tmp_path) == before  # refused before the journal was even opened


def test_n_e3_upper_case_and_surrounding_whitespace_are_normalised(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    head = good_head(db)
    for variant in (head.upper(), f" {head}\n", head.upper() + "\r\n"):
        code, out, err = export(db, "--expect-head-hash", variant)
        assert code == 0, err
        assert json.loads(out.splitlines()[0])["head_checked"] is True


def test_n_e3_a_well_formed_but_different_head_is_still_exit_8(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    code, out, err = export(db, "--expect-head-hash", "0" * 64)
    assert code == 8 and out == "" and "differs from expected" in err


def test_n_e3_the_library_validates_too(tmp_path):
    db = make_journal(tmp_path / "courier.db")
    with pytest.raises(je.ExportError) as caught:
        je.export_stream(db, expect_head_hash="NOT-A-HASH")
    assert caught.value.code == je.EXIT_USAGE
    lines, code = je.export_lines(db, expect_head_hash=good_head(db).upper())
    assert code == 0 and json.loads(lines[0])["head_checked"] is True


# ------------------------------------------------------------------ (2) documentation (N-E1, N-E2, E4 note)

def test_n_e1_n_e2_e4_the_module_docs_state_the_operational_consequences():
    doc = " ".join(je.__doc__.split()).lower()
    # N-E1: sidecars belong to whoever exports
    assert "as the user that runs the controller" in doc and "sidecar" in doc and "owner" in doc
    # N-E2: a held snapshot stops checkpoints, the WAL grows; prefer --out, never stall the consumer
    assert "wal" in doc and "grow" in doc and "checkpoint" in doc and "--out" in doc and "do not stall" in doc
    # E4: with stdout the lines are already out when exit 7 is reported
    assert "stdout" in doc and "check the exit code" in doc and "discard" in doc


def test_n_e1_the_help_text_points_at_the_exit_code_contract(capsys):
    assert je.main(["--help"]) == 0
    helptext = " ".join(capsys.readouterr().out.split()).lower()
    assert "check the exit code" in helptext and "stdout" in helptext


# ------------------------------------------------------------------ (3a) the read-only-medium path is tested even as root / on Windows (N-E5)

@pytest.fixture
def forced_read_only_medium(monkeypatch):
    monkeypatch.setattr(je, "medium_is_read_only", lambda path: True)


def test_n_e5_forced_read_only_medium_opens_immutable_and_a_change_is_exit_7(tmp_path, forced_read_only_medium):
    db = make_journal(tmp_path / "courier.db")
    journal = je.open_readonly(db)
    try:
        assert journal.immutable_open is True
    finally:
        journal.close()
    stream, _, close = je.export_stream(db)
    try:
        next(stream)  # header: pass 1 is done
        os.utime(db, ns=(1_000_000_000, 1_000_000_000))
        with pytest.raises(je.ExportError) as caught:
            list(stream)
        assert caught.value.code == je.EXIT_CHANGED
    finally:
        close()


def changing_after_header(monkeypatch, db):
    real = je.export_stream

    def wrapped(*args, **kwargs):
        stream, code, close = real(*args, **kwargs)

        def lines():
            yield next(stream)
            os.utime(db, ns=(2_000_000_000, 2_000_000_000))  # the journal changes under the immutable reader
            yield from stream
        return lines(), code, close

    monkeypatch.setattr(je, "export_stream", wrapped)


def test_n_e5_forced_read_only_medium_exit_7_with_out_keeps_the_old_export(tmp_path, monkeypatch, forced_read_only_medium):
    db = make_journal(tmp_path / "courier.db")
    outdir = tmp_path / "out"
    outdir.mkdir()
    target = outdir / "export.jsonl"
    target.write_text("previous export\n")
    changing_after_header(monkeypatch, db)
    assert je.main([str(db), "--out", str(target)]) == 7
    assert target.read_text() == "previous export\n"
    assert [p.name for p in outdir.iterdir()] == ["export.jsonl"]  # no temp file left


def test_e4_note_forced_read_only_medium_exit_7_on_stdout_comes_after_lines_were_written(tmp_path, monkeypatch, forced_read_only_medium):
    db = make_journal(tmp_path / "courier.db")
    changing_after_header(monkeypatch, db)
    code, out, err = export(db)
    assert code == 7 and "code=7" in err
    assert out.splitlines() and json.loads(out.splitlines()[0])["record"] == "header"  # already out: the consumer must check the exit code


# ------------------------------------------------------------------ (3b) the BEGIN snapshot is load-bearing (N-E4)

def test_n_e4_pass_2_reads_the_snapshot_of_pass_1_even_if_the_journal_is_rewritten_in_between(tmp_path):
    """The snapshot (one transaction over pass 1 and pass 2) must hide a concurrent rewrite: the export is the
    verified journal, complete, exit 0. Without the single BEGIN pass 2 sees the shortened journal and fails with 7."""
    db = make_journal(tmp_path / "courier.db")
    stream, code, close = je.export_stream(db)
    try:
        header = json.loads(next(stream))  # pass 1 (verification) is done
        tamper(db, f"DELETE FROM events WHERE seq = {len(golden_path())}")  # another connection commits a change now
        rest = list(stream)  # pass 2 must still deliver the verified snapshot
    finally:
        close()
    assert code == 0 and len(rest) == header["event_count"] == len(golden_path())
    assert json.loads(rest[-1])["hash"] == header["head_hash"]
