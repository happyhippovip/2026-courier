"""P9 hardening for courier_worker.adapter_runner: the CLI exit-code contract.

The runner is the only program the worker host spawns. Its contract is small
and fail-closed (exit 0 report written, 2 request rejected, 3 adapter
crashed, 1 unexpected) and had no dedicated test file in the base tree: the
only reference was an allowlist string in tests/test_l3_worker_host.py.

Scope: tests only, no behavior change. Every case runs locally with
temporary fixture files (no network, no credentials). The synthetic ``hang``
fault is deliberately not driven through ``main``: it waits by design until
an external timeout ends the process, so no test may invoke it.

Differentiation from open work: PR #316 adds tests/test_adapter_runner.py
(general hardening) and PR #355 adds
tests/test_courier_worker_adapter_runner.py (in-process paths). This file
uses a distinct filename and covers only the request-validation and
exit-code paths of ``main`` plus the atomic report writer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from courier_worker import adapter_runner as R


def _write_request(tmp_path: Path, payload) -> str:
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _request(tmp_path: Path, **overrides) -> str:
    payload = {
        "adapter": "synthetic",
        "workdir": str(tmp_path / "work"),
        "report": str(tmp_path / "report.json"),
        "attempt": 1,
        "params": {},
    }
    payload.update(overrides)
    return _write_request(tmp_path, payload)


def _read_report(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))


def test_rejects_wrong_argc() -> None:
    assert R.main([]) == 2
    assert R.main(["a", "b"]) == 2


def test_rejects_missing_request_file(tmp_path: Path) -> None:
    assert R.main([str(tmp_path / "does-not-exist.json")]) == 2


def test_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "request.json"
    path.write_text("{not json", encoding="utf-8")
    assert R.main([str(path)]) == 2


@pytest.mark.parametrize("payload", [[1, 2], "just-a-string", 42, None])
def test_rejects_non_dict_request(tmp_path: Path, payload) -> None:
    assert R.main([_write_request(tmp_path, payload)]) == 2


def test_rejects_unknown_adapter_and_writes_no_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = R.main([_request(tmp_path, adapter="real-gpu")])
    assert code == 2
    assert "not allowlisted" in capsys.readouterr().err
    assert not (tmp_path / "report.json").exists()


def test_rejects_missing_adapter(tmp_path: Path) -> None:
    payload = {
        "workdir": str(tmp_path / "work"),
        "report": str(tmp_path / "report.json"),
        "attempt": 1,
        "params": {},
    }
    assert R.main([_write_request(tmp_path, payload)]) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"workdir": None},
        {"report": None},
        {"params": None},
        {"params": []},
        {"attempt": None},
        {"attempt": "1"},
        {"attempt": True},
        {"attempt": 1.0},
    ],
)
def test_rejects_malformed_request_shapes(tmp_path: Path, overrides: dict) -> None:
    # ``attempt=True`` is the sharp edge: bool is an int subclass, and the
    # runner must still refuse it.
    assert R.main([_request(tmp_path, **overrides)]) == 2


def test_rejects_bad_params_without_report(tmp_path: Path) -> None:
    code = R.main([_request(tmp_path, params={"sleep_s": -1})])
    assert code == 2
    assert not (tmp_path / "report.json").exists()


def test_crash_reports_exit_3_without_report(tmp_path: Path) -> None:
    code = R.main([_request(tmp_path, params={"crash_after_s": 0})])
    assert code == 3
    assert not (tmp_path / "report.json").exists()


def test_success_writes_report_and_evidence(tmp_path: Path) -> None:
    code = R.main(
        [_request(tmp_path, params={"content": "hello", "write": "out.txt"})]
    )
    assert code == 0
    report = _read_report(tmp_path)
    assert report["outcome"] == "success"
    assert report["retryable"] is False
    assert isinstance(report["reason"], str)
    assert (tmp_path / "work" / "out.txt").read_text(encoding="utf-8") == "hello"


def test_retryable_failure_still_exits_zero(tmp_path: Path) -> None:
    code = R.main([_request(tmp_path, params={"fail_transient_n": 1})])
    assert code == 0
    report = _read_report(tmp_path)
    assert report["outcome"] == "failure"
    assert report["retryable"] is True


def test_fault_outside_attempt_scope_succeeds(tmp_path: Path) -> None:
    code = R.main(
        [_request(tmp_path, params={"crash_after_s": 0, "fault_attempts": [2]})]
    )
    assert code == 0
    assert _read_report(tmp_path)["outcome"] == "success"


def test_report_writer_creates_parents_and_overwrites(tmp_path: Path) -> None:
    nested = str(tmp_path / "sub" / "dir" / "report.json")
    R._write_report(nested, {"outcome": "success"})
    assert json.loads(Path(nested).read_text(encoding="utf-8")) == {
        "outcome": "success"
    }
    R._write_report(nested, {"outcome": "failure"})
    assert json.loads(Path(nested).read_text(encoding="utf-8")) == {
        "outcome": "failure"
    }
    leftovers = list((tmp_path / "sub" / "dir").glob(".tmp-*.json"))
    assert leftovers == []
