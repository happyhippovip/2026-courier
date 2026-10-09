"""In-process tests for courier_worker.adapter_runner (P9 test hardening).

Covers the contained-child entrypoint without spawning subprocesses: argv
handling, request validation (fail closed, exit 2), synthetic outcomes
(success / reported failure / bad params / crash), the 500-char reason
bound, and atomic report writes. No network, no subprocesses, no sleeps.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import adapters.synthetic as synthetic_mod
from courier_worker import adapter_bridge, adapter_runner


def _request(tmp_path: Path, **overrides):
    payload = {
        "adapter": "synthetic",
        "params": {"write": "out.txt", "content": "unit-test-data"},
        "attempt": 1,
        "workdir": str(tmp_path / "work"),
        "report": str(tmp_path / "reports" / "rep.json"),
    }
    payload.update(overrides)
    req = tmp_path / "req.json"
    req.write_text(json.dumps(payload), encoding="utf-8")
    return str(req), payload


def test_allowed_adapters_is_closed_synthetic_only():
    assert isinstance(adapter_runner.ALLOWED, frozenset)
    assert adapter_runner.ALLOWED == frozenset({"synthetic"})


def test_write_report_roundtrip_with_sorted_keys(tmp_path: Path):
    target = tmp_path / "nested" / "dir" / "report.json"
    data = {"retryable": False, "reason": "ok", "outcome": "success"}
    adapter_runner._write_report(str(target), data)
    raw = target.read_text(encoding="utf-8")
    assert json.loads(raw) == data
    assert raw.index('"outcome"') < raw.index('"reason"') < raw.index('"retryable"')
    assert list(tmp_path.rglob(".tmp-*.json")) == []


def test_write_report_failure_cleans_tmp_and_raises(tmp_path: Path, monkeypatch):
    target = tmp_path / "report.json"

    def _failing_dump(*args, **kwargs):
        raise RuntimeError("simulated disk error during dump")

    monkeypatch.setattr(json, "dump", _failing_dump)
    with pytest.raises(RuntimeError, match="simulated disk error"):
        adapter_runner._write_report(str(target), {"outcome": "success"})
    assert not target.exists()
    assert list(tmp_path.rglob(".tmp-*.json")) == []


def test_write_report_replace_failure_cleans_tmp_and_raises(tmp_path: Path, monkeypatch):
    target = tmp_path / "report.json"
    monkeypatch.setattr(
        "courier_worker.adapter_runner.os.replace",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("replace failed")),
    )
    with pytest.raises(OSError, match="replace failed"):
        adapter_runner._write_report(str(target), {"outcome": "success"})
    assert not target.exists()
    assert list(tmp_path.rglob(".tmp-*.json")) == []


@pytest.mark.parametrize("argv", [[], ["a.json", "b.json"]])
def test_main_rejects_bad_argv_count(argv, capsys):
    assert adapter_runner.main(argv) == 2
    assert "expected exactly one request path" in capsys.readouterr().err


def test_main_missing_request_file(tmp_path: Path, capsys):
    assert adapter_runner.main([str(tmp_path / "nope.json")]) == 2
    assert "unreadable request" in capsys.readouterr().err


def test_main_corrupt_request_json(tmp_path: Path, capsys):
    bad = tmp_path / "req.json"
    bad.write_text("{not json", encoding="utf-8")
    assert adapter_runner.main([str(bad)]) == 2
    assert "unreadable request" in capsys.readouterr().err


@pytest.mark.parametrize("raw", ["[1, 2]", "42", '"str"', "null"])
def test_main_non_dict_request_refused(tmp_path: Path, raw: str, capsys):
    req = tmp_path / "req.json"
    req.write_text(raw, encoding="utf-8")
    assert adapter_runner.main([str(req)]) == 2
    assert "not allowlisted" in capsys.readouterr().err


@pytest.mark.parametrize("adapter", ["shell", "", "SYNTHETIC", None, 123])
def test_main_disallowed_adapter_refused(tmp_path: Path, adapter, capsys):
    req, _ = _request(tmp_path, adapter=adapter)
    assert adapter_runner.main([req]) == 2
    assert "not allowlisted" in capsys.readouterr().err


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("workdir", None),
        ("workdir", 123),
        ("report", None),
        ("report", 123),
        ("params", None),
        ("params", []),
        ("params", "x"),
        ("attempt", None),
        ("attempt", "1"),
        ("attempt", True),
        ("attempt", 1.5),
    ],
)
def test_main_malformed_fields_refused(tmp_path: Path, field, bad_value, capsys):
    req, _ = _request(tmp_path, **{field: bad_value})
    assert adapter_runner.main([req]) == 2
    assert "malformed request" in capsys.readouterr().err


def test_main_attempt_zero_refused_by_adapter(tmp_path: Path, capsys):
    # attempt=0 passes the runner's shape check (int, not bool) but the
    # adapter rejects it; still fail-closed with exit 2 and no report.
    req, payload = _request(tmp_path, attempt=0)
    assert adapter_runner.main([req]) == 2
    assert "params rejected" in capsys.readouterr().err
    assert not Path(payload["report"]).exists()


def test_main_success_writes_report_and_artifact(tmp_path: Path):
    home = tmp_path / "home"
    report = adapter_bridge.report_path(str(home), "d1")
    req, payload = _request(
        tmp_path,
        workdir=str(home / "artifacts" / "d1"),
        report=report,
        params={"write": "out.txt", "content": "unit-test-data"},
    )
    assert adapter_runner.main([req]) == 0
    body = json.loads(Path(report).read_text(encoding="utf-8"))
    assert body["outcome"] == "success"
    assert isinstance(body["reason"], str)
    assert body["retryable"] is False
    assert (home / "artifacts" / "d1" / "out.txt").read_text(encoding="utf-8") == "unit-test-data"
    assert adapter_bridge.read_report(str(home), "d1") == body


def test_main_reported_failure_returns_zero_with_retryable(tmp_path: Path):
    req, payload = _request(
        tmp_path, params={"write": "o.txt", "content": "x", "fail_transient_n": 1}
    )
    assert adapter_runner.main([req]) == 0
    body = json.loads(Path(payload["report"]).read_text(encoding="utf-8"))
    assert body["outcome"] == "failure"
    assert body["retryable"] is True


def test_main_bad_params_exit_2_without_report(tmp_path: Path, capsys):
    req, payload = _request(tmp_path, params={"write": "../evil"})
    assert adapter_runner.main([req]) == 2
    assert "params rejected" in capsys.readouterr().err
    assert not Path(payload["report"]).exists()


def test_main_crash_exit_3_without_report(tmp_path: Path, capsys):
    req, payload = _request(tmp_path, params={"crash_after_s": 0})
    assert adapter_runner.main([req]) == 3
    assert not Path(payload["report"]).exists()


def test_main_reason_truncated_to_500_chars(tmp_path: Path, monkeypatch):
    req, payload = _request(tmp_path)
    monkeypatch.setattr(
        synthetic_mod,
        "run",
        lambda params, workdir, attempt=1: SimpleNamespace(
            outcome="success", reason="x" * 600, retryable=False
        ),
    )
    assert adapter_runner.main([req]) == 0
    body = json.loads(Path(payload["report"]).read_text(encoding="utf-8"))
    assert body["reason"] == "x" * 500
