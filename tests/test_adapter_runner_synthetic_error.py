"""P9 hardening pins for courier_worker.adapter_runner: SyntheticError path.

When the allowlisted synthetic adapter rejects its params, the runner must
exit 2 (fail closed, same class as malformed requests), say "params rejected"
on stderr, and write no report. A pre-existing report at the report path is
left untouched (the runner never overwrites on this path).

Offline, in-process, no network, no subprocess, no sleeps: every params shape
below fails synthetic validation before any work happens.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from courier_worker import adapter_runner as R


def _write_request(tmp_path: Path, *, params, attempt=1) -> tuple[str, str]:
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps({
        "adapter": "synthetic",
        "workdir": str(workdir),
        "report": str(report),
        "attempt": attempt,
        "params": params,
    }), encoding="utf-8")
    return str(request_path), str(report)


@pytest.mark.parametrize("params", [
    {"sleep_s": -1},
    {"sleep_s": "fast"},
    {"write": "../escape.txt"},
    {"write": "/absolute.txt"},
    {"content": 123},
    {"hang": "yes"},
    {"fail_transient_n": -2},
    {"fault_attempts": []},
])
def test_synthetic_param_rejection_exits_2_with_no_report(tmp_path, capsys, params):
    request_path, report = _write_request(tmp_path, params=params)
    assert R.main([request_path]) == 2
    _, err = capsys.readouterr()
    assert "params rejected" in err
    assert not os.path.exists(report)


def test_runner_attempt_zero_reaches_adapter_validation(tmp_path, capsys):
    # attempt=0 passes the runner's own shape check (int, not bool) but the
    # synthetic adapter requires attempt >= 1: still exit 2, still no report.
    request_path, report = _write_request(tmp_path, params={}, attempt=0)
    assert R.main([request_path]) == 2
    _, err = capsys.readouterr()
    assert "params rejected" in err
    assert not os.path.exists(report)


def test_synthetic_rejection_leaves_existing_report_untouched(tmp_path, capsys):
    request_path, report = _write_request(tmp_path, params={"sleep_s": -1})
    sentinel = {"outcome": "success", "reason": "previous", "retryable": False}
    Path(report).write_text(json.dumps(sentinel), encoding="utf-8")
    assert R.main([request_path]) == 2
    assert json.loads(Path(report).read_text(encoding="utf-8")) == sentinel
