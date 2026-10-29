"""Spawned-process contract pins for courier_worker.adapter_runner (P9, tests only).

The runner is started by path (``python courier_worker/adapter_runner.py
<request.json>``), not by module name: it derives the package root from its
own file location. These tests pin that contract through a real process
boundary with a foreign cwd and no PYTHONPATH inheritance:

- usage errors exit 2 with a usage hint on stderr and write no report;
- unreadable / non-JSON / non-allowlisted / malformed requests exit 2 and
  write no report;
- rejected synthetic params exit 2, a synthetic crash exits 3, both with no
  report;
- a valid synthetic request exits 0 and writes a report with exactly the
  keys {outcome, reason, retryable} plus the artifact into the workdir.

No network, no credentials, no behaviour change to the module under test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "courier_worker" / "adapter_runner.py"

TIMEOUT_S = 60


def _clean_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _spawn(argv: list, cwd: Path):
    return subprocess.run(
        [sys.executable, str(RUNNER), *argv],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        cwd=str(cwd),
        env=_clean_env(),
    )


def _write_request(path: Path, payload) -> str:
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        path.write_text(payload, encoding="utf-8")
    return str(path)


def _valid_request(workdir: Path, report: Path, params: dict | None = None) -> dict:
    return {
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report),
        "attempt": 1,
        "params": {} if params is None else params,
    }


def test_no_argv_exits_2_with_usage_and_no_report(tmp_path: Path):
    proc = _spawn([], cwd=tmp_path)
    assert proc.returncode == 2
    assert "expected exactly one request path" in proc.stderr
    assert list(tmp_path.iterdir()) == []


def test_extra_argv_exits_2(tmp_path: Path):
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    proc = _spawn([str(first), str(second)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "expected exactly one request path" in proc.stderr


def test_missing_request_file_exits_2(tmp_path: Path):
    proc = _spawn([str(tmp_path / "does-not-exist.json")], cwd=tmp_path)
    assert proc.returncode == 2
    assert "unreadable request" in proc.stderr


def test_invalid_json_request_exits_2(tmp_path: Path):
    request = tmp_path / "request.json"
    _write_request(request, "{not valid json")
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "unreadable request" in proc.stderr


def test_non_allowlisted_adapter_exits_2_and_writes_no_report(tmp_path: Path):
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    payload = _valid_request(tmp_path / "work", report)
    payload["adapter"] = "real"
    _write_request(request, payload)
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "not allowlisted" in proc.stderr
    assert not report.exists()


def test_malformed_request_exits_2_and_writes_no_report(tmp_path: Path):
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    payload = _valid_request(tmp_path / "work", report)
    del payload["report"]
    _write_request(request, payload)
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "malformed request" in proc.stderr
    assert not report.exists()


def test_bool_attempt_is_malformed_exits_2(tmp_path: Path):
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    payload = _valid_request(tmp_path / "work", report)
    payload["attempt"] = True
    _write_request(request, payload)
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "malformed request" in proc.stderr
    assert not report.exists()


def test_rejected_params_exit_2_and_write_no_report(tmp_path: Path):
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    payload = _valid_request(tmp_path / "work", report, params={"write": "../escape.txt"})
    _write_request(request, payload)
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "params rejected" in proc.stderr
    assert not report.exists()


def test_synthetic_crash_exits_3_and_writes_no_report(tmp_path: Path):
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    payload = _valid_request(tmp_path / "work", report, params={"crash_after_s": 0})
    _write_request(request, payload)
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 3
    assert not report.exists()


def test_success_round_trip_exits_0_with_report_and_artifact(tmp_path: Path):
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    _write_request(request, _valid_request(workdir, report))
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 0
    body = json.loads(report.read_text(encoding="utf-8"))
    assert set(body.keys()) == {"outcome", "reason", "retryable"}
    assert body["outcome"] == "success"
    assert isinstance(body["reason"], str)
    assert isinstance(body["retryable"], bool)
    assert (workdir / "out.txt").is_file()


def test_started_by_path_with_foreign_cwd_and_clean_env(tmp_path: Path):
    """The runner must work when spawned outside the repo with no PYTHONPATH."""
    foreign = tmp_path / "foreign-cwd"
    foreign.mkdir()
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    _write_request(request, _valid_request(workdir, report))
    env = _clean_env()
    assert "PYTHONPATH" not in env
    proc = subprocess.run(
        [sys.executable, str(RUNNER), str(request)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        cwd=str(foreign),
        env=env,
    )
    assert proc.returncode == 0
    assert json.loads(report.read_text(encoding="utf-8"))["outcome"] == "success"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only stderr wording probe")
def test_stderr_is_text_on_success(tmp_path: Path):
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    _write_request(request, _valid_request(workdir, report))
    proc = _spawn([str(request)], cwd=tmp_path)
    assert proc.returncode == 0
    assert isinstance(proc.stderr, str)
