"""Dedicated tests for courier_worker.adapter_runner (P9 test hardening).

Covers the contained child process entrypoint executed by the worker host.
Validates argument handling, allowlist gating, request validation, report
serialization, synthetic execution outcomes (success, failure, crash, hang,
error), exit codes (0, 1, 2, 3), and integration with adapter_bridge.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from adapters import synthetic
from courier_worker import adapter_bridge, adapter_runner

RUNNER_SCRIPT = Path(adapter_runner.__file__).resolve()


def _make_request(
    tmp_path: Path,
    adapter: Any = "synthetic",
    params: Any = None,
    attempt: Any = 1,
    workdir: Any = None,
    report: Any = None,
) -> Path:
    if params is None:
        params = {"write": "out.txt", "content": "unit-test-data"}
    if workdir is None:
        workdir = str(tmp_path / "work")
    if report is None:
        report = str(tmp_path / "reports" / "rep.json")

    payload = {
        "adapter": adapter,
        "params": params,
        "attempt": attempt,
        "workdir": workdir,
        "report": report,
    }
    req_file = tmp_path / "req.json"
    req_file.write_text(json.dumps(payload), encoding="utf-8")
    return req_file


# -- Unit: Module and Allowlist Constants ------------------------------------


def test_allowed_adapters_frozen():
    assert isinstance(adapter_runner.ALLOWED, frozenset)
    assert adapter_runner.ALLOWED == frozenset({"synthetic"})


# -- Unit: _write_report -----------------------------------------------------


def test_write_report_creates_parent_and_valid_json(tmp_path: Path):
    target = tmp_path / "nested" / "dir" / "report.json"
    data = {"outcome": "success", "reason": "ok", "retryable": False}
    adapter_runner._write_report(str(target), data)

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == data


def test_write_report_cleans_up_tmp_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "report.json"

    def _failing_dump(*args, **kwargs):
        raise RuntimeError("simulated disk error during dump")

    monkeypatch.setattr(json, "dump", _failing_dump)

    with pytest.raises(RuntimeError, match="simulated disk error"):
        adapter_runner._write_report(str(target), {"outcome": "success"})

    assert not target.exists()
    leftover_tmps = list(tmp_path.glob(".tmp-*.json"))
    assert leftover_tmps == []


# -- Unit: main() Argument & Input Parsing -----------------------------------


@pytest.mark.parametrize("argv", [
    [],
    ["a", "b"],
    ["a", "b", "c"],
])
def test_main_rejects_invalid_argv_count(argv, capsys: pytest.CaptureFixture):
    code = adapter_runner.main(argv)
    assert code == 2
    err = capsys.readouterr().err
    assert "expected exactly one request path" in err


def test_main_rejects_missing_request_file(tmp_path: Path, capsys: pytest.CaptureFixture):
    nonexistent = str(tmp_path / "no_such_file.json")
    code = adapter_runner.main([nonexistent])
    assert code == 2
    err = capsys.readouterr().err
    assert "unreadable request" in err


def test_main_rejects_corrupted_json(tmp_path: Path, capsys: pytest.CaptureFixture):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{broken json...", encoding="utf-8")
    code = adapter_runner.main([str(bad_json)])
    assert code == 2
    err = capsys.readouterr().err
    assert "unreadable request" in err


@pytest.mark.parametrize("raw_payload", [
    [1, 2, 3],
    "string-not-dict",
    42,
    None,
])
def test_main_rejects_non_dict_json(tmp_path: Path, raw_payload, capsys: pytest.CaptureFixture):
    req_file = tmp_path / "payload.json"
    req_file.write_text(json.dumps(raw_payload), encoding="utf-8")
    code = adapter_runner.main([str(req_file)])
    assert code == 2
    err = capsys.readouterr().err
    assert "not allowlisted" in err


# -- Unit: main() Allowlist and Schema Validation ----------------------------


@pytest.mark.parametrize("bad_adapter", [
    "shell",
    "bash",
    "local_shell",
    "unknown",
    "",
    123,
    None,
])
def test_main_rejects_disallowed_adapter(tmp_path: Path, bad_adapter, capsys: pytest.CaptureFixture):
    req = _make_request(tmp_path, adapter=bad_adapter)
    code = adapter_runner.main([str(req)])
    assert code == 2
    err = capsys.readouterr().err
    assert "not allowlisted" in err


@pytest.mark.parametrize("field,bad_value", [
    ("workdir", 123),
    ("workdir", None),
    ("workdir", ["list"]),
    ("report", 123),
    ("report", None),
    ("params", "string-not-dict"),
    ("params", None),
    ("params", [1, 2]),
    ("attempt", "1"),
    ("attempt", 1.5),
    ("attempt", None),
    ("attempt", True),   # bool is subclass of int, but explicitly rejected
    ("attempt", False),  # bool is subclass of int, but explicitly rejected
])
def test_main_rejects_malformed_fields(tmp_path: Path, field, bad_value, capsys: pytest.CaptureFixture):
    base: Dict[str, Any] = {
        "adapter": "synthetic",
        "params": {"write": "out.txt"},
        "attempt": 1,
        "workdir": str(tmp_path / "w"),
        "report": str(tmp_path / "rep.json"),
    }
    base[field] = bad_value
    req = tmp_path / "req.json"
    req.write_text(json.dumps(base), encoding="utf-8")

    code = adapter_runner.main([str(req)])
    assert code == 2
    err = capsys.readouterr().err
    assert "malformed request" in err
    if isinstance(base["report"], str):
        assert not Path(base["report"]).exists()


# -- Unit: Synthetic Execution and Reporting ---------------------------------


def test_main_synthetic_success(tmp_path: Path):
    workdir = tmp_path / "sandbox"
    report_file = tmp_path / "reports" / "report.json"
    req = _make_request(
        tmp_path,
        params={"write": "data.bin", "content": "hello synthetic"},
        workdir=str(workdir),
        report=str(report_file),
    )

    code = adapter_runner.main([str(req)])
    assert code == 0

    # workdir was created and file was written
    assert workdir.exists()
    assert (workdir / "data.bin").read_text(encoding="utf-8") == "hello synthetic"

    # report file was written with expected keys and values
    assert report_file.exists()
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["outcome"] == "success"
    assert report["retryable"] is False
    assert isinstance(report["reason"], str)


def test_main_synthetic_reported_failure(tmp_path: Path):
    workdir = tmp_path / "sandbox"
    report_file = tmp_path / "report.json"
    req = _make_request(
        tmp_path,
        params={"write": "out.txt", "fail_transient_n": 1, "fault_attempts": [1]},
        attempt=1,
        workdir=str(workdir),
        report=str(report_file),
    )

    code = adapter_runner.main([str(req)])
    assert code == 0  # 0 indicates report was written for adapter-reported failure

    assert report_file.exists()
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["outcome"] == "failure"
    assert report["retryable"] is True
    assert "transient" in report["reason"]


def test_main_truncates_long_reason_to_500_chars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    long_reason = "E" * 1000
    mock_result = SimpleNamespace(outcome="failure", reason=long_reason, retryable=False)

    monkeypatch.setattr(synthetic, "run", lambda *args, **kwargs: mock_result)

    report_file = tmp_path / "report.json"
    req = _make_request(tmp_path, report=str(report_file))

    code = adapter_runner.main([str(req)])
    assert code == 0

    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert len(report["reason"]) == 500
    assert report["reason"] == "E" * 500


def test_main_synthetic_error_bad_params(tmp_path: Path, capsys: pytest.CaptureFixture):
    report_file = tmp_path / "report.json"
    req = _make_request(
        tmp_path,
        params={"write": "../escape.txt"},
        report=str(report_file),
    )

    code = adapter_runner.main([str(req)])
    assert code == 2
    assert not report_file.exists()
    err = capsys.readouterr().err
    assert "params rejected" in err


def test_main_synthetic_crash(tmp_path: Path, capsys: pytest.CaptureFixture):
    report_file = tmp_path / "report.json"
    req = _make_request(
        tmp_path,
        params={"crash_after_s": 0, "fault_attempts": [1]},
        attempt=1,
        report=str(report_file),
    )

    code = adapter_runner.main([str(req)])
    assert code == 3
    assert not report_file.exists()
    err = capsys.readouterr().err
    assert "crashed" in err


def test_main_synthetic_hang_enters_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    class InterruptedSleep(Exception):
        pass

    def _sleep_interrupt(seconds):
        assert seconds == 3600
        raise InterruptedSleep("halt sleep loop")

    monkeypatch.setattr("time.sleep", _sleep_interrupt)

    req = _make_request(
        tmp_path,
        params={"hang": True, "fault_attempts": [1]},
        attempt=1,
    )

    with pytest.raises(InterruptedSleep):
        adapter_runner.main([str(req)])

    err = capsys.readouterr().err
    assert "synthetic hang (waiting to be terminated)" in err


# -- End-to-End: Subprocess CLI Invocations ----------------------------------


def test_subprocess_cli_success(tmp_path: Path):
    req = _make_request(tmp_path, params={"write": "e2e.txt", "content": "from cli"})
    proc = subprocess.run(
        [sys.executable, str(RUNNER_SCRIPT), str(req)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    rep_path = tmp_path / "reports" / "rep.json"
    assert rep_path.exists()
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    assert rep["outcome"] == "success"


def test_subprocess_cli_crash_returns_code_3(tmp_path: Path):
    req = _make_request(tmp_path, params={"crash_after_s": 0, "fault_attempts": [1]}, attempt=1)
    proc = subprocess.run(
        [sys.executable, str(RUNNER_SCRIPT), str(req)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3
    assert "crashed" in proc.stderr
    assert not (tmp_path / "reports" / "rep.json").exists()


def test_subprocess_cli_bad_params_returns_code_2(tmp_path: Path):
    req = _make_request(tmp_path, params={"write": "../bad_path"})
    proc = subprocess.run(
        [sys.executable, str(RUNNER_SCRIPT), str(req)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "params rejected" in proc.stderr


def test_subprocess_cli_unexpected_error_returns_code_1(tmp_path: Path):
    # Create a file where report's directory needs to be, so _write_report fails
    # with NotADirectoryError when attempting os.makedirs
    blocking_file = tmp_path / "conflict_file"
    blocking_file.write_text("not a directory", encoding="utf-8")
    bad_report_path = str(blocking_file / "report.json")

    req = _make_request(tmp_path, report=bad_report_path)
    proc = subprocess.run(
        [sys.executable, str(RUNNER_SCRIPT), str(req)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "unexpected" in proc.stderr


# -- Integration: adapter_bridge.read_report Compatibility -------------------


def test_adapter_bridge_read_report_compatible(tmp_path: Path):
    home = str(tmp_path)
    dispatch_id = "test-disp-001"
    req_p = adapter_bridge.request_path(home, dispatch_id)
    rep_p = adapter_bridge.report_path(home, dispatch_id)
    workdir = str(tmp_path / "work")

    req_data = {
        "adapter": "synthetic",
        "params": {"write": "bridge_out.txt", "content": "bridge content"},
        "attempt": 1,
        "workdir": workdir,
        "report": rep_p,
    }
    os.makedirs(os.path.dirname(req_p), exist_ok=True)
    with open(req_p, "w", encoding="utf-8") as fh:
        json.dump(req_data, fh)

    # Run the runner
    code = adapter_runner.main([req_p])
    assert code == 0

    # Read back via adapter_bridge
    report = adapter_bridge.read_report(home, dispatch_id)
    assert report is not None
    assert report["outcome"] == "success"
    assert report["retryable"] is False
