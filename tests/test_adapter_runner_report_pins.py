"""P9 hardening for courier_worker.adapter_runner: report-content + fail-closed pins.

Tests only; no behavior change. Exercises ``main()`` in-process (no
subprocesses, no network):

- argv arity and unreadable / malformed requests fail closed (exit 2,
  no report written);
- the allowlist is closed to ``synthetic`` (exit 2 otherwise);
- a minimal success writes a shaped report (exit 0);
- report ``reason`` is truncated to 500 chars and ``retryable`` is
  coerced to bool (pinned via a stubbed ``synthetic.run``);
- ``SyntheticError`` maps to exit 2 with no report;
  ``SyntheticCrash`` maps to exit 3.

The ``SyntheticHang`` path is intentionally never exercised here: it
sleeps until the host kills the process tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import courier_worker.adapter_runner as AR
from adapters.synthetic import RunResult


def _request(tmp_path: Path, name: str, payload: dict) -> tuple[str, str, str]:
    workdir = str(tmp_path / f"{name}-work")
    report = str(tmp_path / f"{name}-reports" / "nested" / "report.json")
    request_path = tmp_path / f"{name}-request.json"
    body = {"adapter": "synthetic", "params": {}, "attempt": 1,
            "workdir": workdir, "report": report}
    body.update(payload)
    request_path.write_text(json.dumps(body), encoding="utf-8")
    return str(request_path), workdir, report


def _read_report(report: str) -> dict:
    with open(report, encoding="utf-8") as handle:
        return json.load(handle)


def test_argv_arity_is_exactly_one():
    assert AR.main([]) == 2
    assert AR.main(["a", "b"]) == 2


def test_missing_request_file_fails_closed(tmp_path):
    missing = str(tmp_path / "nope.json")
    report = str(tmp_path / "r.json")
    assert AR.main([missing]) == 2
    assert not Path(report).exists()


def test_malformed_json_fails_closed(tmp_path):
    request_path = tmp_path / "bad.json"
    request_path.write_text("{not json", encoding="utf-8")
    assert AR.main([str(request_path)]) == 2


def test_non_dict_json_fails_closed(tmp_path):
    request_path = tmp_path / "list.json"
    request_path.write_text("[1, 2]", encoding="utf-8")
    assert AR.main([str(request_path)]) == 2


def test_unknown_adapter_refused(tmp_path):
    request_path, _workdir, report = _request(tmp_path, "unknown", {"adapter": "shell"})
    assert AR.main([request_path]) == 2
    assert not Path(report).exists()


@pytest.mark.parametrize("override", [
    {"workdir": None},
    {"report": None},
    {"params": []},
    {"params": None},
    {"attempt": "1"},
    {"attempt": True},
    {"attempt": 1.5},
    {"workdir": 123},
])
def test_malformed_request_shapes_fail_closed(tmp_path, override):
    request_path, _workdir, report = _request(tmp_path, "shapes", override)
    assert AR.main([request_path]) == 2
    assert not Path(report).exists()


def test_allowlist_is_closed_to_synthetic():
    assert AR.ALLOWED == frozenset({"synthetic"})


def test_minimal_success_writes_shaped_report(tmp_path):
    request_path, workdir, report = _request(tmp_path, "ok", {})
    assert AR.main([request_path]) == 0
    payload = _read_report(report)
    assert set(payload) == {"outcome", "reason", "retryable"}
    assert payload["outcome"] == "success"
    assert isinstance(payload["reason"], str)
    assert payload["retryable"] is False
    assert (Path(workdir) / "out.txt").exists()


def test_reason_truncated_to_500(monkeypatch, tmp_path):
    from adapters import synthetic

    def fake_run(params, workdir, attempt):
        return RunResult("success", [], "x" * 600, True)

    monkeypatch.setattr(synthetic, "run", fake_run)
    request_path, _workdir, report = _request(tmp_path, "trunc", {})
    assert AR.main([request_path]) == 0
    payload = _read_report(report)
    assert payload["reason"] == "x" * 500


@pytest.mark.parametrize("given, expected", [(1, True), (0, False), ("yes", True), ("", False)])
def test_retryable_coerced_to_bool(monkeypatch, tmp_path, given, expected):
    from adapters import synthetic

    def fake_run(params, workdir, attempt):
        return RunResult("success", [], "ok", given)

    monkeypatch.setattr(synthetic, "run", fake_run)
    request_path, _workdir, report = _request(tmp_path, f"coerce-{given!r}", {})
    assert AR.main([request_path]) == 0
    payload = _read_report(report)
    assert payload["retryable"] is expected


def test_synthetic_error_maps_to_exit2_without_report(tmp_path):
    request_path, _workdir, report = _request(tmp_path, "badparams", {"params": {"sleep_s": -1}})
    assert AR.main([request_path]) == 2
    assert not Path(report).exists()


def test_synthetic_crash_maps_to_exit3(tmp_path):
    request_path, _workdir, _report = _request(
        tmp_path, "crash", {"params": {"crash_after_s": 0}})
    assert AR.main([request_path]) == 3


def test_write_report_creates_parents_and_sorts_keys(tmp_path):
    target = str(tmp_path / "deep" / "inner" / "report.json")
    AR._write_report(target, {"b": 1, "a": 2})
    raw = Path(target).read_text(encoding="utf-8")
    assert raw.index('"a"') < raw.index('"b"')
    assert json.loads(raw) == {"a": 2, "b": 1}
