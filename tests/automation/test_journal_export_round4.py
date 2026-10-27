"""[DRUIDE | ACCOUNT 2] Round 4 (SCHURKE_REREVIEW NIT): `--out` makes the rename durable by fsyncing the output directory (POSIX).

Real SQLite journal and the real `main()`; the only seams are wrappers around os.replace/os.fsync that record the order.
"""

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from tools.automation import journal_export as je  # noqa: E402

from test_journal_export import export, make_journal  # noqa: E402

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="SKIPPED, NOT PASSED: directory fsync is POSIX-only (skipped by design on Windows)")


def record(monkeypatch):
    calls = []
    real_replace, real_fsync = os.replace, os.fsync

    def replace(src, dst, *a, **k):
        calls.append(("replace", str(dst)))
        return real_replace(src, dst, *a, **k)

    def fsync(fd):
        calls.append(("fsync_dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync_file", None))
        return real_fsync(fd)

    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(os, "fsync", fsync)
    return calls


@POSIX_ONLY
def test_n_r4_out_fsyncs_the_directory_after_the_rename(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    out = tmp_path / "export.jsonl"
    calls = record(monkeypatch)
    code, _, err = export(db, "--out", str(out))
    assert code == 0 and out.exists(), err
    kinds = [kind for kind, _ in calls]
    assert "replace" in kinds and "fsync_dir" in kinds, kinds
    assert kinds.index("fsync_dir") > kinds.index("replace"), f"directory fsync must come after the rename: {kinds}"
    assert kinds.index("fsync_file") < kinds.index("replace")  # data first, then the rename


@POSIX_ONLY
def test_n_r4_a_filesystem_that_refuses_directory_fsync_does_not_fail_the_export(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    out = tmp_path / "export.jsonl"
    real_fsync = os.fsync

    def fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(22, "Invalid argument")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    code, _, err = export(db, "--out", str(out))
    assert code == 0 and out.exists() and "Traceback" not in err, err
    assert list(tmp_path.glob(".*.tmp")) == []


def test_n_r4_stdout_export_does_not_fsync_any_directory(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    calls = record(monkeypatch)
    code, out, _ = export(db)
    assert code == 0 and out
    assert "fsync_dir" not in [kind for kind, _ in calls]
