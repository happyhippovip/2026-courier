"""Write-report + request-validation pins for courier_worker.adapter_runner.

P9-adapter_runner_write_report (tests only, no behavior change).

Covers the parts of courier_worker/adapter_runner.py that have no dedicated
test file in the base tree:

- ``_write_report`` atomic JSON write (sorted keys, parent-dir creation,
  overwrite, no leftover tmp files).
- ``ALLOWED`` closed allowlist.
- ``main`` fail-closed request validation (argv shape, unreadable/invalid
  request, allowlist, malformed fields) and the success/crash/error report
  paths via the local ``synthetic`` adapter (no network, no subprocess).

No network, no credentials, no hang fault (``hang`` would block forever).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from courier_worker.adapter_runner import ALLOWED, _write_report, main


def _request(tmp_path: Path, **overrides) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    workdir = str(tmp_path / "work")
    report = str(tmp_path / "run" / "reports" / "d1.json")
    base: dict = {
        "adapter": "synthetic",
        "params": {},
        "attempt": 2,
        "workdir": workdir,
        "report": report,
    }
    base.update(overrides)
    path = tmp_path / "req.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return str(path)


# -- _write_report ------------------------------------------------------------

def test_write_report_writes_sorted_json(tmp_path: Path):
    target = str(tmp_path / "r.json")
    _write_report(target, {"b": 1, "a": 2})
    assert json.loads(Path(target).read_text(encoding="utf-8")) == {"a": 2, "b": 1}


def test_write_report_creates_parent_dirs(tmp_path: Path):
    target = str(tmp_path / "a" / "b" / "r.json")
    _write_report(target, {"outcome": "success"})
    assert Path(target).is_file()


def test_write_report_overwrites_existing(tmp_path: Path):
    target = tmp_path / "r.json"
    target.write_text(json.dumps({"old": True}), encoding="utf-8")
    _write_report(str(target), {"outcome": "success"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"outcome": "success"}


def test_write_report_leaves_no_tmp_files(tmp_path: Path):
    target = str(tmp_path / "sub" / "r.json")
    _write_report(target, {"outcome": "success"})
    leftovers = list((tmp_path / "sub").glob(".tmp-*.json"))
    assert leftovers == []


def test_write_report_round_trips_unicode(tmp_path: Path):
    target = str(tmp_path / "r.json")
    _write_report(target, {"reason": "héllo ✓"})
    assert json.loads(Path(target).read_text(encoding="utf-8"))["reason"] == "héllo ✓"


# -- ALLOWED ------------------------------------------------------------------

def test_allowed_is_closed_synthetic_only():
    assert ALLOWED == frozenset({"synthetic"})
    assert isinstance(ALLOWED, frozenset)


# -- main: argv and request file ----------------------------------------------

def test_main_rejects_missing_arg(capsys):
    assert main([]) == 2
    assert main(["a", "b"]) == 2


def test_main_rejects_missing_file(tmp_path: Path, capsys):
    assert main([str(tmp_path / "nope.json")]) == 2


def test_main_rejects_invalid_json(tmp_path: Path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([str(bad)]) == 2


def test_main_rejects_non_dict_request(tmp_path: Path, capsys):
    bad = tmp_path / "list.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert main([str(bad)]) == 2


def test_main_rejects_unknown_adapter(tmp_path: Path, capsys):
    assert main([_request(tmp_path, adapter="shell")]) == 2
    assert main([_request(tmp_path, adapter=None)]) == 2
    assert main([_request(tmp_path, adapter=123)]) == 2


def test_main_rejects_missing_fields(tmp_path: Path, capsys):
    full = {"adapter": "synthetic", "params": {}, "attempt": 1,
            "workdir": str(tmp_path / "w"), "report": str(tmp_path / "r.json")}
    for key in ("workdir", "report", "params", "attempt"):
        partial = {k: v for k, v in full.items() if k != key}
        path = tmp_path / f"missing_{key}.json"
        path.write_text(json.dumps(partial), encoding="utf-8")
        assert main([str(path)]) == 2


def test_main_rejects_malformed_types(tmp_path: Path, capsys):
    cases = [
        {"workdir": 123},
        {"report": 123},
        {"params": []},
        {"params": "x"},
        {"attempt": "1"},
        {"attempt": True},
        {"attempt": 1.5},
        {"attempt": None},
    ]
    for i, override in enumerate(cases):
        assert main([_request(tmp_path / f"case{i}", **override)]) == 2


def test_main_rejects_bad_synthetic_params(tmp_path: Path, capsys):
    # Valid request shape, but the adapter's own validator refuses it.
    assert main([_request(tmp_path, params={"sleep_s": -1})]) == 2


# -- main: execution paths ----------------------------------------------------

def test_main_success_writes_structured_report(tmp_path: Path):
    home = tmp_path / "home"
    req = _request(home, params={}, attempt=2)
    assert main([req]) == 0
    report_path = home / "run" / "reports" / "d1.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "success"
    assert isinstance(report["retryable"], bool)
    assert isinstance(report["reason"], str)
    assert set(report) == {"outcome", "reason", "retryable"}
    assert Path(home / "work").is_dir()


def test_main_crash_returns_3_without_report(tmp_path: Path, capsys):
    home = tmp_path / "home"
    req = _request(home, params={"crash_after_s": 0}, attempt=1)
    assert main([req]) == 3
    assert not (home / "run" / "reports" / "d1.json").exists()


def test_main_transient_failure_still_writes_report(tmp_path: Path):
    home = tmp_path / "home"
    req = _request(home, params={"fail_transient_n": 1}, attempt=1)
    assert main([req]) == 0
    report = json.loads((home / "run" / "reports" / "d1.json").read_text(encoding="utf-8"))
    assert report["outcome"] == "failure"
    assert report["retryable"] is True


def test_main_report_parent_dirs_created(tmp_path: Path):
    home = tmp_path / "deep" / "home"
    req = _request(home, params={}, attempt=2)
    assert main([req]) == 0
    assert (home / "run" / "reports" / "d1.json").is_file()
    leftovers = list((home / "run" / "reports").glob(".tmp-*.json"))
    assert leftovers == []
    assert os.path.isdir(home / "work")
