"""P9 request-shape pins for courier_worker.adapter_runner (tests only).

Covers main(argv) fail-closed request handling: exit 2 for unusable
requests, exit 3 for a deterministic synthetic crash, exit 0 plus a
structured report for a valid synthetic request. No network, no
subprocesses, no credentials; all file I/O stays under tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

from courier_worker import adapter_runner


def _write_request(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _valid_request(workdir: Path, report: Path, **overrides) -> dict:
    request = {
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report),
        "attempt": 2,
        "params": {"write": "out.txt", "content": "hello"},
    }
    request.update(overrides)
    return request


def test_no_args_returns_2(tmp_path):
    assert adapter_runner.main([]) == 2


def test_too_many_args_returns_2(tmp_path):
    request = tmp_path / "request.json"
    request.write_text("{}", encoding="utf-8")
    assert adapter_runner.main([str(request), "extra"]) == 2


def test_missing_request_file_returns_2(tmp_path):
    assert adapter_runner.main([str(tmp_path / "nope.json")]) == 2


def test_invalid_json_returns_2(tmp_path):
    request = tmp_path / "request.json"
    request.write_text("{oops", encoding="utf-8")
    assert adapter_runner.main([str(request)]) == 2


def test_non_dict_json_returns_2_without_report(tmp_path):
    request = tmp_path / "request.json"
    report = tmp_path / "reports" / "report.json"
    request.write_text("[1, 2]", encoding="utf-8")
    assert adapter_runner.main([str(request)]) == 2
    assert not report.exists()


def test_missing_adapter_returns_2(tmp_path):
    request = tmp_path / "request.json"
    report = tmp_path / "reports" / "report.json"
    payload = _valid_request(tmp_path / "work", report)
    del payload["adapter"]
    _write_request(request, payload)
    assert adapter_runner.main([str(request)]) == 2
    assert not report.exists()


def test_disallowed_adapter_returns_2_without_report(tmp_path):
    request = tmp_path / "request.json"
    report = tmp_path / "reports" / "report.json"
    payload = _valid_request(tmp_path / "work", report, adapter="local_shell")
    _write_request(request, payload)
    assert adapter_runner.main([str(request)]) == 2
    assert not report.exists()


def test_malformed_fields_return_2_without_report(tmp_path):
    cases = [
        {"workdir": None},
        {"report": None},
        {"params": ["not", "a", "dict"]},
        {"params": True},
        {"attempt": True},
        {"attempt": "2"},
        {"workdir": 123},
    ]
    for index, override in enumerate(cases):
        report = tmp_path / f"report-{index}.json"
        payload = _valid_request(tmp_path / f"work-{index}", report)
        payload.update(override)
        request = tmp_path / f"request-{index}.json"
        _write_request(request, payload)
        assert adapter_runner.main([str(request)]) == 2, override
        assert not report.exists(), override


def test_rejected_params_return_2_without_report(tmp_path):
    request = tmp_path / "request.json"
    report = tmp_path / "reports" / "report.json"
    payload = _valid_request(
        tmp_path / "work", report, params={"write": "/abs/path.txt"}
    )
    _write_request(request, payload)
    assert adapter_runner.main([str(request)]) == 2
    assert not report.exists()


def test_attempt_zero_returns_2_without_report(tmp_path):
    request = tmp_path / "request.json"
    report = tmp_path / "reports" / "report.json"
    payload = _valid_request(tmp_path / "work", report, attempt=0)
    _write_request(request, payload)
    assert adapter_runner.main([str(request)]) == 2
    assert not report.exists()


def test_deterministic_crash_returns_3_without_report(tmp_path):
    request = tmp_path / "request.json"
    report = tmp_path / "reports" / "report.json"
    payload = _valid_request(
        tmp_path / "work", report, attempt=1, params={"crash_after_s": 0}
    )
    _write_request(request, payload)
    assert adapter_runner.main([str(request)]) == 3
    assert not report.exists()


def test_valid_request_returns_0_and_writes_report(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "report.json"
    request = tmp_path / "request.json"
    _write_request(request, _valid_request(workdir, report))
    assert adapter_runner.main([str(request)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["outcome"] == "success"
    assert isinstance(payload["reason"], str)
    assert payload["retryable"] is False
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "hello"


def test_extra_request_keys_are_ignored(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "report.json"
    request = tmp_path / "request.json"
    payload = _valid_request(workdir, report)
    payload["extra_key"] = "ignored"
    _write_request(request, payload)
    assert adapter_runner.main([str(request)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["outcome"] == "success"
