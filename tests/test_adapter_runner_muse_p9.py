"""P9 test hardening for courier_worker.adapter_runner (offline pins).

Tests only; no behavior change. Pins the fail-closed request contract,
allowlist, exit codes, and atomic report writes. No network, no credentials,
no subprocess hangs (the synthetic hang path is intentionally not exercised).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from courier_worker import adapter_runner as R


def _write_request(tmp_path: Path, payload) -> str:
    path = tmp_path / "request.json"
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        path.write_text(payload, encoding="utf-8")
    return str(path)


def _valid_request(workdir: str, report: str, params: dict | None = None, attempt: int = 1) -> dict:
    return {
        "adapter": "synthetic",
        "workdir": workdir,
        "report": report,
        "params": {} if params is None else params,
        "attempt": attempt,
    }


def test_argv_requires_exactly_one_request_path():
    assert R.main([]) == 2
    assert R.main(["a", "b"]) == 2


def test_missing_request_file_returns_2(tmp_path):
    assert R.main([str(tmp_path / "does-not-exist.json")]) == 2


def test_invalid_json_returns_2(tmp_path):
    path = _write_request(tmp_path, "{not json")
    assert R.main([path]) == 2


def test_non_dict_request_returns_2(tmp_path):
    path = _write_request(tmp_path, [1, 2, 3])
    assert R.main([path]) == 2


def test_unknown_adapter_returns_2(tmp_path):
    workdir = str(tmp_path / "work")
    report = str(tmp_path / "report.json")
    path = _write_request(tmp_path, _valid_request(workdir, report))
    # rewrite with unknown adapter
    payload = _valid_request(workdir, report)
    payload["adapter"] = "nope"
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 2
    assert not os.path.exists(report)


def test_missing_adapter_returns_2(tmp_path):
    workdir = str(tmp_path / "work")
    report = str(tmp_path / "report.json")
    payload = _valid_request(workdir, report)
    del payload["adapter"]
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 2


def test_malformed_fields_return_2(tmp_path):
    workdir = str(tmp_path / "work")
    report = str(tmp_path / "report.json")
    base = _valid_request(workdir, report)
    cases = []
    for key in ("workdir", "report", "params", "attempt"):
        bad = dict(base)
        del bad[key]
        cases.append(bad)
    bad_types = [
        {**base, "workdir": 123},
        {**base, "report": None},
        {**base, "params": []},
        {**base, "attempt": "1"},
        {**base, "attempt": True},
        {**base, "attempt": 1.5},
    ]
    for payload in cases + bad_types:
        path = _write_request(tmp_path, payload)
        assert R.main([path]) == 2, payload


def test_synthetic_params_rejected_returns_2(tmp_path):
    workdir = str(tmp_path / "work")
    report = str(tmp_path / "report.json")
    payload = _valid_request(workdir, report, params={"sleep_s": "forever"})
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 2
    assert not os.path.exists(report)


def test_success_writes_report_and_returns_0(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "nested" / "dir" / "report.json"
    payload = _valid_request(str(workdir), str(report), params={"content": "hi"})
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["outcome"] == "success"
    assert data["retryable"] is False
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "hi"


def test_transient_failure_writes_failure_report(tmp_path):
    workdir = str(tmp_path / "work")
    report = tmp_path / "report.json"
    payload = _valid_request(workdir, str(report), params={"fail_transient_n": 1}, attempt=1)
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["outcome"] == "failure"
    assert data["retryable"] is True


def test_crash_returns_3_without_report(tmp_path):
    workdir = str(tmp_path / "work")
    report = tmp_path / "report.json"
    payload = _valid_request(workdir, str(report), params={"crash_after_s": 0}, attempt=1)
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 3
    assert not report.exists()


def test_write_report_creates_dirs_and_sorts_keys(tmp_path):
    target = tmp_path / "a" / "b" / "report.json"
    R._write_report(str(target), {"z": 1, "a": 2})
    raw = target.read_text(encoding="utf-8")
    assert raw.index('"a"') < raw.index('"z"')
    leftovers = [p for p in target.parent.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_write_report_overwrites_and_leaves_no_tmp(tmp_path):
    target = tmp_path / "report.json"
    target.write_text("stale", encoding="utf-8")
    R._write_report(str(target), {"outcome": "success"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"outcome": "success"}
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_allowed_is_closed_to_synthetic():
    assert "synthetic" in R.ALLOWED
    assert "local_shell" not in R.ALLOWED
    assert isinstance(R.ALLOWED, frozenset)


def test_reason_truncated_to_500_and_retryable_coerced(tmp_path, monkeypatch):
    from adapters import synthetic as S

    class FakeResult:
        outcome = "success"
        reason = "x" * 900
        retryable = 1

    monkeypatch.setattr(S, "run", lambda params, workdir, attempt: FakeResult())
    workdir = str(tmp_path / "work")
    report = tmp_path / "report.json"
    payload = _valid_request(workdir, str(report), params={})
    path = _write_request(tmp_path, payload)
    assert R.main([path]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert len(data["reason"]) == 500
    assert data["retryable"] is True
