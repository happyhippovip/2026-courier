"""P9 pins for courier_worker.adapter_runner: unexpected-error paths.

Sibling P9 suites pin the fail-closed refusals (exit 2), the crash path
(exit 3) and the happy path. These pins cover what they leave open:

- a workdir blocked by a regular file: ``os.makedirs`` fails before any
  adapter runs, the error propagates out of ``main`` with no report, and
  the documented "1 = any other unexpected error" contract holds end to
  end through a real child process;
- exact reason-length boundaries (500 kept whole, 501 cut to 500);
- subprocess exit codes for refused requests (exit 2, no report).

Tests only: no behaviour change. Offline, deterministic, stdlib only.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import adapters.synthetic as synthetic_mod
from courier_worker import adapter_runner


def _write_request(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _valid_request(workdir: Path, report: Path, **overrides) -> dict:
    payload = {
        "adapter": "synthetic",
        "params": {},
        "attempt": 1,
        "workdir": str(workdir),
        "report": str(report),
    }
    payload.update(overrides)
    return payload


def _run_subprocess(request_path: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(Path(adapter_runner.__file__).resolve()), request_path],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_workdir_blocked_by_file_raises_without_report(tmp_path: Path) -> None:
    blocker = tmp_path / "workdir"
    blocker.write_text("not a directory", encoding="utf-8")
    report = tmp_path / "report.json"
    request_path = _write_request(
        tmp_path / "request.json", _valid_request(blocker, report)
    )
    with pytest.raises(OSError):
        adapter_runner.main([request_path])
    assert not report.exists()


def test_workdir_blocked_by_file_subprocess_exits_1(tmp_path: Path) -> None:
    blocker = tmp_path / "workdir"
    blocker.write_text("not a directory", encoding="utf-8")
    report = tmp_path / "report.json"
    request_path = _write_request(
        tmp_path / "request.json", _valid_request(blocker, report)
    )
    proc = _run_subprocess(request_path)
    assert proc.returncode == 1
    assert "unexpected" in proc.stderr
    assert not report.exists()


def test_reason_exactly_500_chars_kept_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reason = "r" * 500
    monkeypatch.setattr(
        synthetic_mod,
        "run",
        lambda params, workdir, attempt=1: synthetic_mod.RunResult(
            "success", [], reason, False
        ),
    )
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request_path = _write_request(
        tmp_path / "request.json", _valid_request(workdir, report)
    )
    assert adapter_runner.main([request_path]) == 0
    stored = json.loads(report.read_text(encoding="utf-8"))
    assert stored["reason"] == reason


def test_reason_501_chars_truncated_to_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        synthetic_mod,
        "run",
        lambda params, workdir, attempt=1: synthetic_mod.RunResult(
            "success", [], "r" * 501, False
        ),
    )
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request_path = _write_request(
        tmp_path / "request.json", _valid_request(workdir, report)
    )
    assert adapter_runner.main([request_path]) == 0
    stored = json.loads(report.read_text(encoding="utf-8"))
    assert stored["reason"] == "r" * 500


def test_subprocess_disallowed_adapter_exits_2_without_report(
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.json"
    request_path = _write_request(
        tmp_path / "request.json",
        _valid_request(tmp_path / "work", report, adapter="shell"),
    )
    proc = _run_subprocess(request_path)
    assert proc.returncode == 2
    assert not report.exists()


def test_subprocess_malformed_request_exits_2_without_workdir(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "work"
    payload = _valid_request(workdir, tmp_path / "report.json")
    del payload["report"]
    request_path = _write_request(tmp_path / "request.json", payload)
    proc = _run_subprocess(request_path)
    assert proc.returncode == 2
    assert not workdir.exists()
