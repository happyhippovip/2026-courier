"""P9 test hardening for courier_worker.adapter_runner (outcome-to-report pins).

Tests only; no behavior change. Pins the runner's outcome-to-report
contract for every non-hanging path of ``main()`` plus the ``__main__``
unexpected-error exit code:

- success writes exactly {"outcome", "reason", "retryable"} and exits 0;
- a transient synthetic failure still writes a report (outcome "failure")
  and exits 0;
- crash exits 3 with no report; bad requests exit 2 with no report;
- overlong reasons are truncated to 500 chars; the report dir is created
  and no ".tmp-" leftovers remain.

No network, no credentials. Everything runs in ``tmp_path``; the two
``__main__`` pins use one local interpreter subprocess each.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from courier_worker import adapter_runner as R

RUNNER_FILE = Path(R.__file__)


def _write_request(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _request(workdir: Path, report: Path, params: dict, attempt=1) -> dict:
    return {
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report),
        "attempt": attempt,
        "params": params,
    }


def _read_report(report: Path) -> dict:
    return json.loads(report.read_text(encoding="utf-8"))


def test_success_report_shape_and_exit(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "reports" / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(workdir, report, {"write": "out.txt", "content": "hi"}))
    assert R.main([str(req)]) == 0
    assert _read_report(report) == {"outcome": "success", "reason": "", "retryable": False}
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "hi"


def test_success_creates_missing_workdir_and_report_parents(tmp_path):
    workdir = tmp_path / "deep" / "nested" / "work"
    report = tmp_path / "deep" / "reports" / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(workdir, report, {}))
    assert R.main([str(req)]) == 0
    assert (workdir / "out.txt").exists()
    assert _read_report(report)["outcome"] == "success"


def test_success_leaves_no_tmp_leftovers(tmp_path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    report = report_dir / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", report, {}))
    assert R.main([str(req)]) == 0
    leftovers = [p for p in report_dir.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_transient_failure_still_writes_failure_report(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    params = {"fail_transient_n": 1, "fault_attempts": [1, 2]}
    _write_request(req, _request(workdir, report, params, attempt=1))
    assert R.main([str(req)]) == 0
    assert _read_report(report) == {
        "outcome": "failure",
        "reason": "synthetic transient fault",
        "retryable": True,
    }
    assert not (workdir / "out.txt").exists()


def test_crash_exits_3_without_report(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", report, {"crash_after_s": 0}))
    assert R.main([str(req)]) == 3
    assert not report.exists()
    assert "crashed" in capsys.readouterr().err


def test_bad_params_exit_2_without_report(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", report, {"write": "/absolute"}))
    assert R.main([str(req)]) == 2
    assert not report.exists()
    assert "params rejected" in capsys.readouterr().err


def test_bool_attempt_rejected_as_malformed(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", report, {}, attempt=True))
    assert R.main([str(req)]) == 2
    assert not report.exists()
    assert "malformed" in capsys.readouterr().err


def test_zero_attempt_rejected_via_params(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", report, {}, attempt=0))
    assert R.main([str(req)]) == 2
    assert not report.exists()
    assert "params rejected" in capsys.readouterr().err


def test_unknown_adapter_rejected(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    payload = _request(tmp_path / "work", report, {})
    payload["adapter"] = "local_shell"
    _write_request(req, payload)
    assert R.main([str(req)]) == 2
    assert not report.exists()
    assert "allowlist" in capsys.readouterr().err


def test_missing_adapter_key_rejected(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    payload = _request(tmp_path / "work", report, {})
    del payload["adapter"]
    _write_request(req, payload)
    assert R.main([str(req)]) == 2
    assert not report.exists()
    assert "allowlist" in capsys.readouterr().err


def test_non_dict_json_rejected(tmp_path, capsys):
    req = tmp_path / "request.json"
    _write_request(req, [{"adapter": "synthetic"}])
    assert R.main([str(req)]) == 2
    assert "allowlist" in capsys.readouterr().err


def test_invalid_json_rejected(tmp_path, capsys):
    req = tmp_path / "request.json"
    req.write_text("{not json", encoding="utf-8")
    assert R.main([str(req)]) == 2
    assert "unreadable request" in capsys.readouterr().err


def test_missing_request_file_rejected(tmp_path, capsys):
    assert R.main([str(tmp_path / "does-not-exist.json")]) == 2
    assert "unreadable request" in capsys.readouterr().err


def test_argv_count_not_one_rejected(tmp_path, capsys):
    assert R.main([]) == 2
    assert R.main(["a", "b"]) == 2
    assert "exactly one request path" in capsys.readouterr().err


def test_non_dict_params_rejected(tmp_path, capsys):
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    payload = _request(tmp_path / "work", report, {})
    payload["params"] = ["write"]
    _write_request(req, payload)
    assert R.main([str(req)]) == 2
    assert not report.exists()
    assert "malformed" in capsys.readouterr().err


def test_long_reason_truncated_to_500(tmp_path, monkeypatch):
    from adapters import synthetic as S

    def fake_run(params, workdir, attempt):
        return S.RunResult("success", [], "r" * 600, False)

    monkeypatch.setattr(S, "run", fake_run)
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", report, {}))
    assert R.main([str(req)]) == 0
    assert _read_report(report)["reason"] == "r" * 500


def test_main_subprocess_success_exit_0(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(workdir, report, {"content": "ok"}))
    proc = subprocess.run(
        [sys.executable, str(RUNNER_FILE), str(req)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert _read_report(report)["outcome"] == "success"


def test_main_subprocess_unexpected_error_exit_1(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("in the way", encoding="utf-8")
    report = blocker / "report.json"
    req = tmp_path / "request.json"
    _write_request(req, _request(tmp_path / "work", str(report), {}))
    proc = subprocess.run(
        [sys.executable, str(RUNNER_FILE), str(req)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 1
    assert "unexpected" in proc.stderr
