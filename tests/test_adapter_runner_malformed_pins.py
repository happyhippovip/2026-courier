"""P9 test hardening for courier_worker.adapter_runner (malformed-request pins).

Covers only fail-closed request handling in courier_worker/adapter_runner.py:
exit code 2 for malformed or disallowed requests (no report written), the
synthetic allowlist, fast crash/failure/success anchors through main(), and
the atomic report write. No behavior change, no network, no credentials.
"""

from __future__ import annotations

import json
from pathlib import Path

from courier_worker import adapter_runner as R


def _write_request(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _request(workdir: Path, report: Path, **overrides) -> dict:
    base = {"adapter": "synthetic", "workdir": str(workdir),
            "report": str(report), "attempt": 1, "params": {}}
    base.update(overrides)
    return base


def test_no_argv_returns_2_and_writes_no_report(tmp_path, capsys):
    assert R.main([]) == 2
    assert capsys.readouterr().err != ""
    assert list(tmp_path.iterdir()) == []


def test_two_argv_returns_2(tmp_path):
    assert R.main(["a", "b"]) == 2


def test_missing_request_file_returns_2(tmp_path, capsys):
    assert R.main([str(tmp_path / "absent.json")]) == 2
    assert "unreadable" in capsys.readouterr().err


def test_invalid_json_returns_2(tmp_path, capsys):
    bad = tmp_path / "req.json"
    bad.write_text("{not json", encoding="utf-8")
    assert R.main([str(bad)]) == 2
    assert "unreadable" in capsys.readouterr().err


def test_non_dict_request_returns_2(tmp_path, capsys):
    req = tmp_path / "req.json"
    _write_request(req, ["synthetic"])
    assert R.main([str(req)]) == 2
    assert "allowlisted" in capsys.readouterr().err


def test_disallowed_adapter_returns_2_and_writes_no_report(tmp_path, capsys):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    _write_request(req, _request(tmp_path / "work", report, adapter="local_shell"))
    assert R.main([str(req)]) == 2
    assert "allowlisted" in capsys.readouterr().err
    assert not report.exists()


def test_missing_adapter_returns_2(tmp_path):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    payload = _request(tmp_path / "work", report)
    del payload["adapter"]
    _write_request(req, payload)
    assert R.main([str(req)]) == 2
    assert not report.exists()


def test_missing_keys_return_2(tmp_path):
    for missing in ("workdir", "report", "attempt", "params"):
        req = tmp_path / f"req_{missing}.json"
        payload = _request(tmp_path / "work", tmp_path / f"rep_{missing}.json")
        del payload[missing]
        _write_request(req, payload)
        assert R.main([str(req)]) == 2, missing


def test_bool_attempt_returns_2(tmp_path):
    req = tmp_path / "req.json"
    _write_request(req, _request(tmp_path / "work", tmp_path / "rep.json", attempt=True))
    assert R.main([str(req)]) == 2


def test_string_attempt_returns_2(tmp_path):
    req = tmp_path / "req.json"
    _write_request(req, _request(tmp_path / "work", tmp_path / "rep.json", attempt="1"))
    assert R.main([str(req)]) == 2


def test_non_dict_params_returns_2(tmp_path):
    req = tmp_path / "req.json"
    _write_request(req, _request(tmp_path / "work", tmp_path / "rep.json", params=["x"]))
    assert R.main([str(req)]) == 2


def test_rejected_params_return_2_with_no_report(tmp_path, capsys):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    _write_request(req, _request(tmp_path / "work", report, params={"sleep_s": -1}))
    assert R.main([str(req)]) == 2
    assert "rejected" in capsys.readouterr().err
    assert not report.exists()


def test_zero_attempt_returns_2_with_no_report(tmp_path):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    _write_request(req, _request(tmp_path / "work", report, attempt=0))
    assert R.main([str(req)]) == 2
    assert not report.exists()


def test_crash_returns_3_with_no_report(tmp_path, capsys):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    _write_request(req, _request(tmp_path / "work", report,
                                 params={"crash_after_s": 0}))
    assert R.main([str(req)]) == 3
    assert "crashed" in capsys.readouterr().err
    assert not report.exists()


def test_transient_failure_returns_0_with_failure_report(tmp_path):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    _write_request(req, _request(tmp_path / "work", report,
                                 params={"fail_transient_n": 1}))
    assert R.main([str(req)]) == 0
    body = json.loads(report.read_text(encoding="utf-8"))
    assert body["outcome"] == "failure"
    assert body["retryable"] is True


def test_success_returns_0_with_report_and_artifact(tmp_path):
    req = tmp_path / "req.json"
    report = tmp_path / "sub" / "dir" / "report.json"
    workdir = tmp_path / "work"
    _write_request(req, _request(workdir, report,
                                 params={"write": "out.txt", "content": "hi"}))
    assert R.main([str(req)]) == 0
    body = json.loads(report.read_text(encoding="utf-8"))
    assert body["outcome"] == "success"
    assert body["retryable"] is False
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "hi"


def test_extra_request_keys_are_tolerated(tmp_path):
    req = tmp_path / "req.json"
    report = tmp_path / "report.json"
    payload = _request(tmp_path / "work", report)
    payload["note"] = "extra"
    _write_request(req, payload)
    assert R.main([str(req)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["outcome"] == "success"


def test_write_report_replaces_existing_and_leaves_no_tmp(tmp_path):
    target = tmp_path / "nested" / "report.json"
    R._write_report(str(target), {"b": 1, "a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2, "b": 1}
    R._write_report(str(target), {"c": 3})
    assert json.loads(target.read_text(encoding="utf-8")) == {"c": 3}
    leftovers = [p for p in target.parent.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_allowed_set_is_synthetic_only():
    assert R.ALLOWED == frozenset({"synthetic"})
