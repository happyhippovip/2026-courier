"""Offline pins for courier_worker.adapter_runner synthetic-crash path (exit 3).

Tests only; no behavior change. Covers the exit-3 branch that has no
P9-<suffix> in any open PR title (surveyed 327 open PRs; no title or branch
contains "crash_exit3" or an adapter_runner crash pin):

- SyntheticCrash (crash_after_s=0) -> return 3, no report written.
- A pre-existing stale report is left untouched on crash (the runner only
  writes on success/failure; stale-report cleanup belongs to adapter_bridge).
- SyntheticError (bad params) -> return 2 via the params-rejected branch.
- Missing / malformed / non-allowlisted requests -> return 2 (fail closed).
- _write_report writes sorted-keys JSON and creates parent dirs.

No network, no credentials, no subprocesses. The synthetic "hang" fault is
intentionally NOT exercised here: it blocks forever by design and is
terminated by the host's timeout machinery instead.
"""

from __future__ import annotations

import json
import os

from courier_worker import adapter_runner


def _write_request(tmp_path, *, adapter="synthetic", params=None, attempt=1,
                   name="request.json"):
    workdir = tmp_path / "work"
    workdir.mkdir(exist_ok=True)
    report = tmp_path / "reports" / "d1.json"
    request_path = tmp_path / name
    payload = {
        "adapter": adapter,
        "params": params if params is not None else {},
        "attempt": attempt,
        "workdir": str(workdir),
        "report": str(report),
    }
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    return str(request_path), str(report)


def test_crash_returns_3_and_writes_no_report(tmp_path, capsys):
    request_path, report = _write_request(
        tmp_path, params={"crash_after_s": 0})
    assert not os.path.exists(report)
    rc = adapter_runner.main([request_path])
    assert rc == 3
    assert not os.path.exists(report)
    err = capsys.readouterr().err.lower()
    assert "adapter_runner" in err


def test_crash_leaves_stale_report_untouched(tmp_path, capsys):
    request_path, report = _write_request(
        tmp_path, params={"crash_after_s": 0})
    os.makedirs(os.path.dirname(report), exist_ok=True)
    stale = {"outcome": "success", "reason": "", "retryable": False}
    with open(report, "w", encoding="utf-8") as fh:
        json.dump(stale, fh)
    rc = adapter_runner.main([request_path])
    assert rc == 3
    with open(report, encoding="utf-8") as fh:
        assert json.load(fh) == stale
    capsys.readouterr()


def test_params_error_returns_2_and_writes_no_report(tmp_path, capsys):
    request_path, report = _write_request(
        tmp_path, params={"sleep_s": -1})
    rc = adapter_runner.main([request_path])
    assert rc == 2
    assert not os.path.exists(report)
    err = capsys.readouterr().err.lower()
    assert "params rejected" in err


def test_missing_request_file_returns_2(tmp_path, capsys):
    missing = str(tmp_path / "does-not-exist.json")
    rc = adapter_runner.main([missing])
    assert rc == 2
    err = capsys.readouterr().err.lower()
    assert "unreadable request" in err


def test_malformed_json_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = adapter_runner.main([str(bad)])
    assert rc == 2
    capsys.readouterr()


def test_non_allowlisted_adapter_returns_2(tmp_path, capsys):
    request_path, _report = _write_request(tmp_path, adapter="evil")
    rc = adapter_runner.main([request_path])
    assert rc == 2
    err = capsys.readouterr().err.lower()
    assert "allowlist" in err


def test_write_report_sorts_keys_and_creates_parents(tmp_path):
    path = tmp_path / "deep" / "nested" / "report.json"
    adapter_runner._write_report(str(path), {"b": 1, "a": 2})
    raw = path.read_text(encoding="utf-8")
    assert raw.index('"a"') < raw.index('"b"')
    assert json.loads(raw) == {"a": 2, "b": 1}
