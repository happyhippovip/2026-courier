"""P9 hardening pins for courier_worker.adapter_runner (tests only).

Focused on two gaps with no dedicated test file on the base branch:
``main(argv)`` fail-closed argv/request validation and ``_write_report``
atomic JSON persistence. No network, no credentials, offline only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from courier_worker import adapter_runner as runner


def _write_request(tmp_path: Path, payload, name: str = "request.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _minimal_spec(workdir: str, report: str, attempt: int = 1, params: dict | None = None) -> dict:
    return {
        "adapter": "synthetic",
        "workdir": workdir,
        "report": report,
        "attempt": attempt,
        "params": params if params is not None else {"fault_attempts": [999]},
    }


def test_main_rejects_empty_argv(capsys):
    assert runner.main([]) == 2
    assert "exactly one" in capsys.readouterr().err


def test_main_rejects_extra_argv(tmp_path, capsys):
    req = _write_request(tmp_path, _minimal_spec(str(tmp_path / "w"), str(tmp_path / "r.json")))
    assert runner.main([req, "extra"]) == 2
    assert "exactly one" in capsys.readouterr().err


def test_main_missing_request_file_returns_2(tmp_path, capsys):
    assert runner.main([str(tmp_path / "does-not-exist.json")]) == 2
    assert "unreadable" in capsys.readouterr().err


def test_main_invalid_json_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert runner.main([str(bad)]) == 2
    assert "unreadable" in capsys.readouterr().err


def test_main_non_dict_request_returns_2(tmp_path, capsys):
    req = _write_request(tmp_path, ["not", "a", "dict"])
    assert runner.main([req]) == 2
    assert "allowlisted" in capsys.readouterr().err


def test_main_disallowlisted_adapter_returns_2(tmp_path, capsys):
    spec = _minimal_spec(str(tmp_path / "w"), str(tmp_path / "r.json"))
    spec["adapter"] = "local_shell"
    assert runner.main([_write_request(tmp_path, spec)]) == 2
    assert "allowlisted" in capsys.readouterr().err


def test_main_malformed_fields_return_2(tmp_path):
    good_workdir = str(tmp_path / "w")
    good_report = str(tmp_path / "r.json")
    cases = [
        {  # workdir must be str
            "adapter": "synthetic", "workdir": 123, "report": good_report,
            "attempt": 1, "params": {},
        },
        {  # report must be str
            "adapter": "synthetic", "workdir": good_workdir, "report": None,
            "attempt": 1, "params": {},
        },
        {  # params must be dict
            "adapter": "synthetic", "workdir": good_workdir, "report": good_report,
            "attempt": 1, "params": [],
        },
        {  # attempt bool is rejected (bool is subclass of int)
            "adapter": "synthetic", "workdir": good_workdir, "report": good_report,
            "attempt": True, "params": {},
        },
        {  # attempt str is rejected
            "adapter": "synthetic", "workdir": good_workdir, "report": good_report,
            "attempt": "1", "params": {},
        },
        {  # missing params entirely
            "adapter": "synthetic", "workdir": good_workdir, "report": good_report,
            "attempt": 1,
        },
    ]
    for i, payload in enumerate(cases):
        req = _write_request(tmp_path, payload, name=f"malformed-{i}.json")
        assert runner.main([req]) == 2, f"case {i} should be malformed"


def test_main_rejects_bad_synthetic_params(tmp_path, capsys):
    spec = _minimal_spec(str(tmp_path / "w"), str(tmp_path / "r.json"),
                         params={"write": "/absolute-not-allowed", "fault_attempts": [1]})
    assert runner.main([_write_request(tmp_path, spec)]) == 2
    assert "params rejected" in capsys.readouterr().err


def test_main_success_writes_structured_report(tmp_path):
    workdir = tmp_path / "work"
    report = tmp_path / "nested" / "dir" / "report.json"
    spec = _minimal_spec(str(workdir), str(report),
                         params={"write": "out.txt", "content": "hi", "fault_attempts": [999]})
    assert runner.main([_write_request(tmp_path, spec)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["outcome"] == "success"
    assert payload["retryable"] is False
    assert (workdir / "out.txt").read_text(encoding="utf-8") == "hi"


def test_main_transient_failure_report_is_failure_retryable(tmp_path):
    report = tmp_path / "report.json"
    spec = _minimal_spec(str(tmp_path / "w"), str(report),
                         params={"fail_transient_n": 1, "fault_attempts": [999]})
    assert runner.main([_write_request(tmp_path, spec)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is True


def test_main_crash_returns_3(tmp_path, capsys):
    report = tmp_path / "report.json"
    spec = _minimal_spec(str(tmp_path / "w"), str(report),
                         params={"crash_after_s": 0, "fault_attempts": [1]})
    assert runner.main([_write_request(tmp_path, spec)]) == 3
    assert not report.exists()


def test_main_reason_truncated_to_500(tmp_path, monkeypatch):
    from adapters import synthetic

    report = tmp_path / "report.json"

    def _fake_run(params, workdir, attempt):
        return synthetic.RunResult("success", [], "x" * 600, False)

    monkeypatch.setattr(synthetic, "run", _fake_run)
    spec = _minimal_spec(str(tmp_path / "w"), str(report))
    assert runner.main([_write_request(tmp_path, spec)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["reason"] == "x" * 500


def test_write_report_creates_parents_and_sorts_keys(tmp_path):
    target = tmp_path / "a" / "b" / "report.json"
    runner._write_report(str(target), {"z": 1, "a": 2})
    raw = target.read_text(encoding="utf-8")
    assert raw.index('"a"') < raw.index('"z"')
    assert json.loads(raw) == {"z": 1, "a": 2}


def test_write_report_overwrites_atomically_without_tmp_leftovers(tmp_path):
    target = tmp_path / "report.json"
    target.write_text(json.dumps({"old": True}), encoding="utf-8")
    runner._write_report(str(target), {"outcome": "success", "reason": "", "retryable": False})
    assert json.loads(target.read_text(encoding="utf-8"))["outcome"] == "success"
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
    assert leftovers == []
    assert not os.path.exists(str(target) + ".tmp")
