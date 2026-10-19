"""P9 hardening for courier_worker.adapter_runner (argv + request validation).

Tests only; no behavior change. Offline: tmp_path only, no network,
no credentials. Pins the documented exit-code contract:

- 0  a report was written (success or adapter-reported failure)
- 2  request/adapter not acceptable (fail closed, no report)
- 3  adapter crashed (synthetic crash_after_s)
"""

from __future__ import annotations

import json
from pathlib import Path

from courier_worker import adapter_runner


def _write_request(tmp_path: Path, payload) -> str:
    req = tmp_path / "req.json"
    if isinstance(payload, (dict, list)):
        req.write_text(json.dumps(payload), encoding="utf-8")
    else:
        req.write_text(str(payload), encoding="utf-8")
    return str(req)


def _valid_request(tmp_path: Path, **overrides) -> dict:
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    base = {
        "adapter": "synthetic",
        "params": {},
        "attempt": 1,
        "workdir": str(workdir),
        "report": str(report),
    }
    base.update(overrides)
    return base


def test_argv_empty_returns_2():
    assert adapter_runner.main([]) == 2


def test_argv_two_paths_returns_2(tmp_path):
    req = _write_request(tmp_path, _valid_request(tmp_path))
    assert adapter_runner.main([req, req]) == 2


def test_missing_request_file_returns_2(tmp_path):
    assert adapter_runner.main([str(tmp_path / "nope.json")]) == 2


def test_malformed_json_returns_2(tmp_path):
    req = tmp_path / "bad.json"
    req.write_text("{not json", encoding="utf-8")
    assert adapter_runner.main([str(req)]) == 2


def test_non_dict_request_returns_2(tmp_path):
    req = _write_request(tmp_path, [1, 2, 3])
    assert adapter_runner.main([req]) == 2


def test_unknown_adapter_returns_2(tmp_path):
    req = _write_request(tmp_path, _valid_request(tmp_path, adapter="nope"))
    assert adapter_runner.main([req]) == 2
    # fail closed: no report written
    assert not (tmp_path / "report.json").exists()


def test_missing_workdir_returns_2(tmp_path):
    payload = _valid_request(tmp_path)
    del payload["workdir"]
    assert adapter_runner.main([_write_request(tmp_path, payload)]) == 2


def test_missing_report_returns_2(tmp_path):
    payload = _valid_request(tmp_path)
    del payload["report"]
    assert adapter_runner.main([_write_request(tmp_path, payload)]) == 2


def test_missing_params_returns_2(tmp_path):
    payload = _valid_request(tmp_path)
    del payload["params"]
    assert adapter_runner.main([_write_request(tmp_path, payload)]) == 2


def test_missing_attempt_returns_2(tmp_path):
    payload = _valid_request(tmp_path)
    del payload["attempt"]
    assert adapter_runner.main([_write_request(tmp_path, payload)]) == 2


def test_attempt_bool_returns_2(tmp_path):
    # bool is a subclass of int; the runner explicitly refuses it
    req = _write_request(tmp_path, _valid_request(tmp_path, attempt=True))
    assert adapter_runner.main([req]) == 2


def test_attempt_zero_returns_2(tmp_path):
    req = _write_request(tmp_path, _valid_request(tmp_path, attempt=0))
    # adapter_runner checks shape (int, not bool) -> passes shape, then
    # synthetic.run raises SyntheticError (attempt < 1) -> exit 2
    assert adapter_runner.main([req]) == 2


def test_params_not_dict_returns_2(tmp_path):
    req = _write_request(tmp_path, _valid_request(tmp_path, params=[1]))
    assert adapter_runner.main([req]) == 2


def test_synthetic_params_rejected_returns_2(tmp_path):
    req = _write_request(
        tmp_path, _valid_request(tmp_path, params={"sleep_s": -1})
    )
    assert adapter_runner.main([req]) == 2
    assert not (tmp_path / "report.json").exists()


def test_synthetic_crash_returns_3(tmp_path):
    req = _write_request(
        tmp_path, _valid_request(tmp_path, params={"crash_after_s": 0})
    )
    assert adapter_runner.main([req]) == 3
    assert not (tmp_path / "report.json").exists()


def test_success_writes_report_returns_0(tmp_path):
    payload = _valid_request(tmp_path)
    req = _write_request(tmp_path, payload)
    assert adapter_runner.main([req]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["outcome"] == "success"
    assert isinstance(report["retryable"], bool)
    assert isinstance(report["reason"], str)
    # synthetic wrote its artifact inside workdir only
    assert (tmp_path / "work" / "out.txt").exists()


def test_adapter_failure_still_writes_report_returns_0(tmp_path):
    payload = _valid_request(
        tmp_path, params={"fail_transient_n": 5, "fault_attempts": [99]}
    )
    # attempt 1 <= fail_transient_n 5 -> adapter-reported failure, exit 0
    req = _write_request(tmp_path, payload)
    assert adapter_runner.main([req]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["outcome"] == "failure"
    assert report["retryable"] is True


def test_allowed_is_synthetic_only():
    assert adapter_runner.ALLOWED == frozenset({"synthetic"})


def test_write_report_round_trip(tmp_path):
    path = str(tmp_path / "sub" / "r.json")
    adapter_runner._write_report(path, {"outcome": "success", "reason": "", "retryable": False})
    assert json.loads(Path(path).read_text(encoding="utf-8"))["outcome"] == "success"
