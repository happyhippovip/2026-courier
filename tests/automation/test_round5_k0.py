"""[DRUIDE | ACCOUNT 2] K0 (MAGIER_NACHTEST_R3 R3-1/R3-2/R3-3).

R3-1: the library function normalize_head_hash must answer a wrong TYPE with ExportError(2), not AttributeError/TypeError.
R3-2: every skip in tests/automation carries the same visible reason prefix, so a skip is never mistaken for a pass.
R3-3: the output-directory fsync hits the RIGHT directory and an unopenable directory does not fail the export.
"""

import ast
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from tools.automation import journal_export as je  # noqa: E402

from test_journal_export import export, make_journal  # noqa: E402

HERE = Path(__file__).resolve().parent
PREFIX = "SKIPPED, NOT PASSED: "


# --------------------------------------------------------------------------- R3-1
@pytest.mark.parametrize("value", [123, 0, 1.5, b"a" * 64, bytearray(b"a" * 64), ["a" * 64], {"a": 1}, object(), True])
def test_r3_1_normalize_head_hash_with_a_wrong_type_is_an_export_error_2(value):
    with pytest.raises(je.ExportError) as caught:
        je.normalize_head_hash(value)
    assert caught.value.code == 2 and "--expect-head-hash" in str(caught.value)


def test_r3_1_export_stream_with_a_wrong_type_is_an_export_error_2_before_opening(tmp_path):
    with pytest.raises(je.ExportError) as caught:
        je.export_stream(tmp_path / "does-not-exist.db", expect_head_hash=123)
    assert caught.value.code == 2  # usage first, not "no journal file" (3)


# --------------------------------------------------------------------------- R3-2
def _skip_reasons():
    found = []
    for path in sorted(HERE.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            reason = None
            if name == "pytest.skip":
                reason = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "reason"), None)
            elif name in ("pytest.mark.skipif", "pytest.mark.skip"):
                reason = next((k.value for k in node.keywords if k.arg == "reason"), None)
            else:
                continue
            if isinstance(reason, ast.JoinedStr):
                reason = reason.values[0] if reason.values else None
            text = reason.value if isinstance(reason, ast.Constant) and isinstance(reason.value, str) else None
            found.append((path.name, node.lineno, text))
    return found


def test_r3_2_every_skip_reason_starts_with_the_common_prefix():
    reasons = _skip_reasons()
    assert len(reasons) >= 10, f"the scan must see the skips of the suite, saw {len(reasons)}"
    bad = [f"{name}:{line}: {text!r}" for name, line, text in reasons if not (text or "").startswith(PREFIX)]
    assert not bad, "skip reasons without the prefix 'SKIPPED, NOT PASSED: ':\n" + "\n".join(bad)


def test_r3_2_the_runbook_names_the_prefix():
    text = (HERE / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "SKIPPED, NOT PASSED" in text and "every skip" in text.lower()


# --------------------------------------------------------------------------- R3-3
POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason=PREFIX + "directory fsync is POSIX-only (skipped by design on Windows)")


@POSIX_ONLY
def test_r3_3_the_fsynced_directory_is_the_one_that_holds_the_export(tmp_path, monkeypatch):
    sub = tmp_path / "sub"
    sub.mkdir()
    db = make_journal(tmp_path / "courier.db")
    out = sub / "export.jsonl"
    real_fsync = os.fsync
    synced = []

    def fsync(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            synced.append((info.st_dev, info.st_ino))
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    code, _, err = export(db, "--out", str(out))
    assert code == 0, err
    wanted = os.stat(sub)
    assert synced == [(wanted.st_dev, wanted.st_ino)], f"fsynced {synced}, expected only {sub} ({wanted.st_ino})"
    assert os.stat(tmp_path).st_ino not in [ino for _, ino in synced] and os.stat(tmp_path.parent).st_ino not in [ino for _, ino in synced]


@POSIX_ONLY
def test_r3_3_a_relative_out_path_fsyncs_the_current_directory(tmp_path, monkeypatch):
    db = make_journal(tmp_path / "courier.db")
    monkeypatch.chdir(tmp_path)
    real_fsync = os.fsync
    synced = []

    def fsync(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            synced.append(info.st_ino)
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    code, _, err = export(db, "--out", "export.jsonl")
    assert code == 0 and (tmp_path / "export.jsonl").exists(), err
    assert synced == [os.stat(tmp_path).st_ino]


@POSIX_ONLY
def test_r3_3_a_directory_that_cannot_be_opened_does_not_fail_the_export(tmp_path, monkeypatch):
    sub = tmp_path / "sub"
    sub.mkdir()
    db = make_journal(tmp_path / "courier.db")
    out = sub / "export.jsonl"
    real_open = os.open
    refused = []

    def refusing_open(path, flags, *args, **kwargs):
        if os.path.isdir(path):
            refused.append(str(path))
            raise PermissionError(13, "Permission denied")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", refusing_open)
    code, _, err = export(db, "--out", str(out))
    assert refused, "the exporter never tried to open the output directory"
    assert code == 0 and out.exists() and "Traceback" not in err, err
    assert list(sub.glob(".*.tmp")) == []
