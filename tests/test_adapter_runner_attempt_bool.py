"""P9 hardening for courier_worker.adapter_runner: attempt-bool + request edges.

Tests only, no behavior change. Offline, no network, no credentials.
Pins the runner's fail-closed request validation, with focus on the
``attempt`` bool trap (``bool`` is a subclass of ``int`` but must be
rejected) and the exact exit-code contract:

- 0  report written (success or adapter-reported failure)
- 2  request/adapter not acceptable (no report)
- 3  adapter crashed (no report)

The synthetic ``hang`` path is intentionally not exercised: it loops
forever until the host kills the tree.
"""

from __future__ import annotations

import json
import os

import pytest

from courier_worker import adapter_runner as R


def _write_json(path, payload, raw=None):
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _valid_payload(workdir, report, **overrides):
    payload = {
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report),
        "attempt": 1,
        "params": {"sleep_s": 0, "write": "out.txt", "content": "hi"},
    }
    payload.update(overrides)
    return payload


def _run_main_with_payload(tmp_path, payload, raw=None, name="req.json"):
    req = tmp_path / name
    _write_json(req, payload, raw=raw)
    report_path = payload.get("report") if isinstance(payload, dict) else None
    rc = R.main([str(req)])
    return rc, report_path


def test_allowed_is_closed_to_synthetic():
    assert R.ALLOWED == frozenset({"synthetic"})


@pytest.mark.parametrize("argv", [[], ["a", "b"], ["a", "b", "c"]])
def test_argv_must_be_exactly_one_path(argv):
    assert R.main(argv) == 2


def test_missing_request_file_returns_2(tmp_path):
    missing = str(tmp_path / "nope.json")
    assert R.main([missing]) == 2


def test_invalid_json_returns_2(tmp_path):
    req = tmp_path / "bad.json"
    req.write_text("{not json", encoding="utf-8")
    assert R.main([str(req)]) == 2


@pytest.mark.parametrize("payload", [[1, 2], ["x"], [None], "str", 42, None])
def test_non_dict_json_returns_2(tmp_path, payload):
    req = tmp_path / "req.json"
    req.write_text(json.dumps(payload), encoding="utf-8")
    assert R.main([str(req)]) == 2


@pytest.mark.parametrize("adapter", ["other", "", "Synthetic", "SYNTHETIC", None, 42])
def test_non_allowlisted_adapter_returns_2_no_report(tmp_path, adapter):
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(workdir, report, adapter=adapter)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 2
    assert not report.exists()


@pytest.mark.parametrize("missing", ["workdir", "report", "attempt", "params", "adapter"])
def test_missing_keys_return_2_no_report(tmp_path, missing):
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(workdir, report)
    del payload[missing]
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 2
    assert not report.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("workdir", 42),
        ("workdir", None),
        ("report", 42),
        ("report", None),
        ("params", []),
        ("params", "x"),
        ("params", None),
        ("attempt", "1"),
        ("attempt", 1.0),
        ("attempt", None),
        ("attempt", [1]),
    ],
)
def test_wrong_field_types_return_2_no_report(tmp_path, field, value):
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(tmp_path / "wd", report)
    payload[field] = value
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 2
    assert not report.exists()


@pytest.mark.parametrize("attempt", [True, False])
def test_attempt_bool_rejected_as_malformed(tmp_path, attempt):
    """Bool is an int subclass but must not pass as an attempt number."""
    assert isinstance(attempt, int)
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(workdir, report, attempt=attempt)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 2
    assert not report.exists()


@pytest.mark.parametrize("attempt", [0, -1, -100])
def test_nonpositive_attempt_returns_2_via_synthetic_error(tmp_path, attempt):
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(workdir, report, attempt=attempt)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 2
    assert not report.exists()


def test_success_writes_report_returns_0(tmp_path):
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(workdir, report)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 0
    assert report.exists()
    body = json.loads(report.read_text(encoding="utf-8"))
    assert set(body.keys()) == {"outcome", "reason", "retryable"}
    assert body["outcome"] == "success"
    assert isinstance(body["reason"], str)
    assert isinstance(body["retryable"], bool)


def test_transient_failure_still_returns_0_with_report(tmp_path):
    """An adapter-reported failure is a written report (exit 0), not a refusal."""
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    params = {"sleep_s": 0, "write": "out.txt", "content": "hi", "fail_transient_n": 1}
    payload = _valid_payload(workdir, report, params=params, attempt=1)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 0
    body = json.loads(report.read_text(encoding="utf-8"))
    assert body["outcome"] == "failure"
    assert body["retryable"] is True


def test_bad_params_return_2_no_report(tmp_path):
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    params = {"sleep_s": 0, "write": "/absolute-not-allowed", "content": "hi"}
    payload = _valid_payload(workdir, report, params=params)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 2
    assert not report.exists()


def test_crash_returns_3_no_report(tmp_path):
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    params = {"sleep_s": 0, "write": "out.txt", "content": "hi", "crash_after_s": 0}
    payload = _valid_payload(workdir, report, params=params)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 3
    assert not report.exists()


def test_write_report_creates_parent_dirs(tmp_path):
    target = tmp_path / "deep" / "nested" / "report.json"
    R._write_report(str(target), {"outcome": "success", "reason": "", "retryable": False})
    assert target.exists()
    body = json.loads(target.read_text(encoding="utf-8"))
    assert body == {"outcome": "success", "reason": "", "retryable": False}


def test_report_reason_truncated_to_500(tmp_path, monkeypatch):
    from adapters import synthetic as S

    long_reason = "r" * 600

    class FakeResult:
        outcome = "success"
        reason = long_reason
        retryable = 1

    monkeypatch.setattr(S, "run", lambda params, workdir, attempt: FakeResult())
    workdir = tmp_path / "wd"
    report = tmp_path / "rep" / "report.json"
    payload = _valid_payload(workdir, report)
    rc, _ = _run_main_with_payload(tmp_path, payload)
    assert rc == 0
    body = json.loads(report.read_text(encoding="utf-8"))
    assert len(body["reason"]) == 500
    assert body["reason"] == long_reason[:500]
    assert body["retryable"] is True
    assert isinstance(body["retryable"], bool)


def test_no_tmp_files_left_after_write(tmp_path):
    target = tmp_path / "rep" / "report.json"
    R._write_report(str(target), {"outcome": "success", "reason": "ok", "retryable": False})
    leftovers = [p for p in target.parent.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []
    assert target.exists()
