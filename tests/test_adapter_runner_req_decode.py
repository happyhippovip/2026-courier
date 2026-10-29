"""P9 test hardening for courier_worker.adapter_runner (request-decode edges).

Tests only; no behavior change. Covers how ``main()`` decodes the
host-written request file and how it handles workdir/report paths, all
offline via the deterministic ``synthetic`` adapter (``sleep_s=0``):

- missing / unreadable / invalid-JSON / non-dict request  -> exit 2, no report
- non-allowlisted adapter                               -> exit 2, no report
- non-dict params                                       -> exit 2, no report
- missing workdir / missing report parent dirs          -> created, exit 0
- success report shape (outcome / reason / retryable)
"""

from __future__ import annotations

import json
from pathlib import Path

from courier_worker import adapter_runner as runner


def _request_path(tmp_path: Path, name: str = "request.json") -> str:
    return str(tmp_path / name)


def _write_text(path: str, text: str) -> str:
    Path(path).write_text(text, encoding="utf-8")
    return path


def _write_json(path: str, obj) -> str:
    return _write_text(path, json.dumps(obj))


def _good_request(tmp_path: Path, **overrides) -> str:
    request = {
        "adapter": "synthetic",
        "workdir": str(tmp_path / "work"),
        "report": str(tmp_path / "reports" / "report.json"),
        "attempt": 1,
        "params": {"sleep_s": 0, "write": "out.txt", "content": "hello"},
    }
    request.update(overrides)
    return _write_json(_request_path(tmp_path), request)


def test_missing_request_file_returns_2_and_writes_no_report(tmp_path):
    missing = _request_path(tmp_path, "does-not-exist.json")
    report = str(tmp_path / "report.json")
    # A missing file cannot be a valid request; fail closed without a report.
    assert runner.main([missing]) == 2
    assert not Path(report).exists()


def test_request_path_is_directory_returns_2(tmp_path):
    assert runner.main([str(tmp_path)]) == 2


def test_invalid_json_request_returns_2_and_writes_no_report(tmp_path):
    path = _write_text(_request_path(tmp_path), "{not valid json,,,")
    assert runner.main([path]) == 2
    assert not Path(str(tmp_path / "report.json")).exists()


def test_non_dict_json_requests_return_2(tmp_path):
    for bad in ("[1, 2, 3]", '"just a string"', "42", "null", "true"):
        path = _write_text(_request_path(tmp_path), bad)
        assert runner.main([path]) == 2, bad


def test_non_allowlisted_adapter_returns_2_and_writes_no_report(tmp_path):
    path = _good_request(tmp_path, adapter="evil")
    assert runner.main([path]) == 2
    assert not Path(str(tmp_path / "reports" / "report.json")).exists()


def test_non_dict_params_returns_2_and_writes_no_report(tmp_path):
    path = _good_request(tmp_path, params=["sleep_s", 0])
    assert runner.main([path]) == 2
    assert not Path(str(tmp_path / "reports" / "report.json")).exists()


def test_missing_workdir_is_created_on_success(tmp_path):
    workdir = tmp_path / "nested" / "work"
    report = tmp_path / "report.json"
    path = _good_request(tmp_path, workdir=str(workdir), report=str(report))
    assert not workdir.exists()
    assert runner.main([path]) == 0
    assert workdir.is_dir()
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "hello"


def test_missing_report_parent_is_created_on_success(tmp_path):
    report = tmp_path / "deep" / "nested" / "report.json"
    path = _good_request(tmp_path, report=str(report))
    assert not report.parent.exists()
    assert runner.main([path]) == 0
    assert report.is_file()


def test_success_report_shape(tmp_path):
    report = tmp_path / "report.json"
    path = _good_request(tmp_path, report=str(report))
    assert runner.main([path]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["outcome"] == "success"
    assert isinstance(payload["reason"], str)
    assert isinstance(payload["retryable"], bool)
