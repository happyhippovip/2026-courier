"""Bootstrap + request-refusal pins for courier_worker.adapter_runner.

P9 test hardening (tests only, no behavior change). Pins the import-time
bootstrap contract (package root on ``sys.path``, closed ``ALLOWED`` set,
documented exit-code table) and the fail-closed request-entry boundaries of
``main``: wrong argument counts, unreadable or invalid request files, and
non-allowlisted adapters all return exit code 2 with no report or workdir
side effects.

Only refusal paths are exercised, so the adapter implementation is never
imported and no child process is spawned. No network calls, no credentials.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import courier_worker.adapter_runner as runner


def _files_under(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def _write_request(tmp_path: Path, name: str, payload) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


# -- import-time bootstrap ----------------------------------------------------


def test_package_root_on_sys_path():
    expected = str(Path(runner.__file__).resolve().parents[1])
    assert expected in sys.path


def test_allowed_is_closed_synthetic_set():
    assert isinstance(runner.ALLOWED, frozenset)
    assert runner.ALLOWED == frozenset({"synthetic"})
    assert set(runner.ALLOWED) == {"synthetic"}


def test_docstring_documents_exit_code_table():
    doc = runner.__doc__ or ""
    assert "- 0" in doc
    assert "- 2" in doc
    assert "- 3" in doc
    assert "- 1" in doc


# -- argument-count boundaries ------------------------------------------------


def test_no_args_refused(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.main([]) == 2
    assert "exactly one request path" in capsys.readouterr().err
    assert _files_under(tmp_path) == set()


def test_two_args_refused(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.main(["a.json", "b.json"]) == 2
    assert "exactly one request path" in capsys.readouterr().err
    assert _files_under(tmp_path) == set()


def test_three_args_refused(capsys):
    assert runner.main(["a.json", "b.json", "c.json"]) == 2
    assert "exactly one request path" in capsys.readouterr().err


# -- unreadable or invalid request files --------------------------------------


def test_missing_request_file_refused(capsys, tmp_path):
    missing = tmp_path / "missing.json"
    assert runner.main([str(missing)]) == 2
    assert "unreadable request" in capsys.readouterr().err
    assert not missing.exists()
    assert _files_under(tmp_path) == set()


def test_directory_as_request_refused(capsys, tmp_path):
    assert runner.main([str(tmp_path)]) == 2
    assert "unreadable request" in capsys.readouterr().err
    assert _files_under(tmp_path) == set()


def test_truncated_json_refused(capsys, tmp_path):
    path = tmp_path / "truncated.json"
    path.write_text('{"adapter": "synthe', encoding="utf-8")
    assert runner.main([str(path)]) == 2
    assert "unreadable request" in capsys.readouterr().err
    assert _files_under(tmp_path) == {"truncated.json"}


# -- non-allowlisted adapters --------------------------------------------------


def test_non_dict_json_refused(capsys, tmp_path):
    path = _write_request(tmp_path, "list.json", ["synthetic"])
    assert runner.main([path]) == 2
    assert "not allowlisted" in capsys.readouterr().err
    assert _files_under(tmp_path) == {"list.json"}


def test_missing_adapter_key_refused(capsys, tmp_path):
    path = _write_request(tmp_path, "nokey.json", {"workdir": "w"})
    assert runner.main([path]) == 2
    assert "not allowlisted" in capsys.readouterr().err
    assert _files_under(tmp_path) == {"nokey.json"}


def test_adapter_case_variant_refused(capsys, tmp_path):
    for name, adapter in (("upper.json", "SYNTHETIC"), ("mixed.json", "Synthetic")):
        path = _write_request(tmp_path, name, {"adapter": adapter})
        assert runner.main([path]) == 2, adapter
        assert "not allowlisted" in capsys.readouterr().err
    assert _files_under(tmp_path) == {"upper.json", "mixed.json"}


def test_adapter_affix_refused(capsys, tmp_path):
    for name, adapter in (("empt.json", ""), ("lead.json", " synthetic"), ("trail.json", "synthetic ")):
        path = _write_request(tmp_path, name, {"adapter": adapter})
        assert runner.main([path]) == 2, repr(adapter)
        assert "not allowlisted" in capsys.readouterr().err
    assert _files_under(tmp_path) == {"empt.json", "lead.json", "trail.json"}


def test_non_string_adapter_refused(capsys, tmp_path):
    path = _write_request(tmp_path, "num.json", {"adapter": 123})
    assert runner.main([path]) == 2
    assert "not allowlisted" in capsys.readouterr().err
    assert _files_under(tmp_path) == {"num.json"}


def test_refusal_creates_no_workdir_or_report(capsys, tmp_path):
    request_path = _write_request(tmp_path, "req.json", {"adapter": "nope"})
    workdir = tmp_path / "workdir"
    report = tmp_path / "should_not_exist.json"
    assert runner.main([request_path]) == 2
    assert "not allowlisted" in capsys.readouterr().err
    assert not workdir.exists()
    assert not report.exists()
    assert _files_under(tmp_path) == {"req.json"}
