"""P9 fail-closed pins for courier_worker.adapter_runner (tests only).

Covers main() request-validation and exit-code contract without any
network, subprocess, or hang fixture:

- exit 2: wrong argv count, unreadable/malformed request, non-dict
  request, disallowed adapter, malformed shapes (missing keys, params
  not a dict, bool attempt), params rejected by the synthetic
  validator (SyntheticError);
- exit 3: deterministic synthetic crash (crash_after_s=0, no sleep);
- exit 0: minimal valid request writes a sorted JSON report with
  exactly {outcome, reason, retryable}.

No ``hang`` fixture is used: the runner intentionally blocks forever
on SyntheticHang, so no test may trigger it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from courier_worker.adapter_runner import main


def _write_request(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _valid_request(workdir: Path, report: Path, params=None, attempt=1) -> dict:
    return {
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report),
        "attempt": attempt,
        "params": {} if params is None else params,
    }


def test_argv_must_be_exactly_one_request_path():
    assert main([]) == 2
    assert main(["a.json", "b.json"]) == 2


def test_missing_request_file_returns_2(tmp_path):
    assert main([str(tmp_path / "does-not-exist.json")]) == 2


def test_malformed_json_returns_2(tmp_path):
    bad = tmp_path / "request.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([str(bad)]) == 2


def test_non_dict_request_returns_2(tmp_path):
    req = tmp_path / "request.json"
    _write_request(req, [1, 2, 3])
    assert main([str(req)]) == 2


def test_disallowed_adapter_returns_2(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "r1.json"
    req = tmp_path / "request.json"
    payload = _valid_request(workdir, report)
    payload["adapter"] = "local_shell"
    _write_request(req, payload)
    assert main([str(req)]) == 2
    assert not report.exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("workdir"),
        lambda p: p.pop("report"),
        lambda p: p.pop("params"),
        lambda p: p.pop("attempt"),
        lambda p: p.update(params=[]),
        lambda p: p.update(params="x"),
        lambda p: p.update(attempt=True),
        lambda p: p.update(attempt="1"),
        lambda p: p.update(workdir=123),
        lambda p: p.update(report=None),
    ],
    ids=[
        "missing-workdir",
        "missing-report",
        "missing-params",
        "missing-attempt",
        "params-list",
        "params-string",
        "attempt-bool",
        "attempt-string",
        "workdir-not-str",
        "report-not-str",
    ],
)
def test_malformed_request_shapes_return_2_without_report(tmp_path, mutate):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "r1.json"
    req = tmp_path / "request.json"
    payload = _valid_request(workdir, report)
    mutate(payload)
    _write_request(req, payload)
    assert main([str(req)]) == 2
    assert not report.exists()


def test_rejected_params_return_2_without_report(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "r1.json"
    req = tmp_path / "request.json"
    _write_request(req, _valid_request(workdir, report, params={"sleep_s": -1}))
    assert main([str(req)]) == 2
    assert not report.exists()


def test_deterministic_crash_returns_3_without_report(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "r1.json"
    req = tmp_path / "request.json"
    _write_request(
        req, _valid_request(workdir, report, params={"crash_after_s": 0})
    )
    assert main([str(req)]) == 3
    assert not report.exists()


def test_minimal_valid_request_writes_report_and_returns_0(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "r1.json"
    req = tmp_path / "request.json"
    _write_request(req, _valid_request(workdir, report))
    assert main([str(req)]) == 0
    assert report.is_file()
    loaded = json.loads(report.read_text(encoding="utf-8"))
    assert set(loaded) == {"outcome", "reason", "retryable"}
    assert loaded["outcome"] == "success"
    assert isinstance(loaded["retryable"], bool)
    assert (workdir / "out.txt").is_file()
