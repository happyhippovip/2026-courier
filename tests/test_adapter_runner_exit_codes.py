"""P9 hardening for courier_worker.adapter_runner: fault scoping and report lifecycle.

The runner is the only program the worker host spawns. Its request-validation
and exit-code paths already have dedicated coverage in the base tree's open
work (PR #316 adds tests/test_adapter_runner.py; PR #355 adds
tests/test_courier_worker_adapter_runner.py), so this file deliberately
covers only the gaps neither file exercises:

- fault scoping: a crash/hang fault listed for a different attempt must not
  fire (the adapter faults only when ``attempt`` is in ``fault_attempts``);
- forward tolerance: unknown extra request keys must not break a run;
- report lifecycle: a second run overwrites the first report, the report
  carries exactly the documented keys, and no temporary files are left
  behind.

Scope: tests only, no behavior change. Every case runs locally with
temporary fixture files (no network, no credentials). The synthetic ``hang``
fault is never driven through ``main`` with a matching attempt: it waits by
design until an external timeout ends the process.
"""

from __future__ import annotations

import json
from pathlib import Path

from courier_worker import adapter_runner as R


def _write_request(tmp_path: Path, payload: dict) -> str:
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


def test_fault_for_another_attempt_does_not_fire(tmp_path: Path) -> None:
    # crash_after_s is set, but attempt 1 is outside fault_attempts, so the
    # fault must stay dormant and the run must succeed.
    code = R.main(
        [_request(tmp_path, params={"crash_after_s": 0, "fault_attempts": [2]})]
    )
    assert code == 0
    body = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert body["outcome"] == "success"


def test_hang_flag_for_another_attempt_does_not_hang(tmp_path: Path) -> None:
    # Same scoping rule for the hang fault. Safe to drive through main here
    # only because the faulted branch is not taken; a matching attempt would
    # wait by design and must never be exercised by a test.
    code = R.main(
        [_request(tmp_path, params={"hang": True, "fault_attempts": [2]})]
    )
    assert code == 0
    body = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert body["outcome"] == "success"


def test_extra_request_keys_are_tolerated(tmp_path: Path) -> None:
    payload = {
        "adapter": "synthetic",
        "workdir": str(tmp_path / "work"),
        "report": str(tmp_path / "report.json"),
        "attempt": 1,
        "params": {"content": "tolerant", "write": "out.txt"},
        "future_flag": True,
        "extra": {"nested": [1, 2, 3]},
    }
    assert R.main([_write_request(tmp_path, payload)]) == 0
    body = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert body["outcome"] == "success"
    assert (tmp_path / "work" / "out.txt").read_text(encoding="utf-8") == "tolerant"


def test_second_run_overwrites_report_without_leftovers(tmp_path: Path) -> None:
    assert R.main([_request(tmp_path, params={"content": "first"})]) == 0
    first = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert first["outcome"] == "success"

    assert (
        R.main(
            [
                _request(
                    tmp_path,
                    params={
                        "content": "second",
                        "fail_transient_n": 1,
                    },
                )
            ]
        )
        == 0
    )
    second = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert second["outcome"] == "failure"
    assert second["retryable"] is True
    # The report carries exactly the documented keys.
    assert set(second) == {"outcome", "reason", "retryable"}
    # Atomic replace leaves no staging files behind.
    assert list(tmp_path.glob(".tmp-*.json")) == []
