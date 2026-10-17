"""Report-lifecycle pins for courier_worker.adapter_bridge (P9, tests only).

Covers the offline report lifecycle that needs no network, no credentials
and no subprocess: request/report path layout, fail-closed report reads,
idempotent cleanup, stale-report eviction on write, runner argv shape and
the closed bridge constants. No behavior change.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as bridge


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


# -- path layout ------------------------------------------------------------


def test_request_and_report_paths_nest_under_home(tmp_path):
    home = str(tmp_path)
    request = bridge.request_path(home, "d-1")
    report = bridge.report_path(home, "d-1")
    assert request == os.path.join(home, "run", "requests", "d-1.json")
    assert report == os.path.join(home, "run", "reports", "d-1.json")


def test_safe_sanitizes_separators_and_empty():
    assert bridge._safe("a/b\\c:d") == "a_b_c_d"
    assert bridge._safe("") == "unnamed"
    assert bridge._safe("ok-Name.1_2") == "ok-Name.1_2"


def test_paths_use_sanitized_dispatch(tmp_path):
    home = str(tmp_path)
    assert bridge.request_path(home, "a/b").endswith("a_b.json")
    assert bridge.report_path(home, "a/b").endswith("a_b.json")


# -- read_report fail-closed edges ------------------------------------------


def test_read_report_missing_returns_none(tmp_path):
    assert bridge.read_report(str(tmp_path), "nope") is None


@pytest.mark.parametrize(
    "content",
    ["{not json", "[1, 2]", "42", '"just a string"', "null"],
    ids=["truncated", "list", "number", "string", "null"],
)
def test_read_report_malformed_or_non_dict_returns_none(tmp_path, content):
    home = str(tmp_path)
    _write(bridge.report_path(home, "d"), content)
    assert bridge.read_report(home, "d") is None


def test_read_report_bad_outcome_returns_none(tmp_path):
    home = str(tmp_path)
    _write(bridge.report_path(home, "d"), json.dumps({"outcome": "weird"}))
    assert bridge.read_report(home, "d") is None


def test_read_report_non_bool_retryable_returns_none(tmp_path):
    home = str(tmp_path)
    _write(
        bridge.report_path(home, "d"),
        json.dumps({"outcome": "success", "retryable": "yes"}),
    )
    assert bridge.read_report(home, "d") is None


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_read_report_accepts_known_outcomes(tmp_path, outcome):
    home = str(tmp_path)
    payload = {"outcome": outcome, "retryable": False, "reason": "r"}
    _write(bridge.report_path(home, "d"), json.dumps(payload))
    assert bridge.read_report(home, "d") == payload


def test_read_report_missing_retryable_defaults_and_passes(tmp_path):
    home = str(tmp_path)
    payload = {"outcome": "success"}
    _write(bridge.report_path(home, "d"), json.dumps(payload))
    assert bridge.read_report(home, "d") == payload


# -- cleanup ----------------------------------------------------------------


def test_cleanup_removes_both_files_and_is_idempotent(tmp_path):
    home = str(tmp_path)
    request = bridge.request_path(home, "d")
    report = bridge.report_path(home, "d")
    _write(request, "{}")
    _write(report, json.dumps({"outcome": "success"}))
    bridge.cleanup(home, "d")
    assert not os.path.exists(request)
    assert not os.path.exists(report)
    # Second call with nothing on disk must not raise.
    bridge.cleanup(home, "d")


# -- write_request ----------------------------------------------------------


def _spec(dispatch_id: str = "d-7"):
    return SimpleNamespace(
        dispatch_id=dispatch_id,
        adapter="synthetic",
        params={"mode": "ok"},
        attempt=2,
        task_id="t-1",
        effect_key="eff.key-1:2",
        artifact_dir=os.path.join("artifacts", dispatch_id),
    )


def test_write_request_evicts_stale_report_and_writes_envelope(tmp_path):
    home = str(tmp_path)
    spec = _spec()
    stale = bridge.report_path(home, spec.dispatch_id)
    _write(stale, json.dumps({"outcome": "success"}))
    path = bridge.write_request(home, spec)
    assert path == bridge.request_path(home, spec.dispatch_id)
    assert not os.path.exists(stale)
    with open(path, encoding="utf-8") as handle:
        envelope = json.load(handle)
    assert envelope["adapter"] == "synthetic"
    assert envelope["params"] == {"mode": "ok"}
    assert envelope["attempt"] == 2
    assert envelope["task_id"] == "t-1"
    assert envelope["dispatch_id"] == spec.dispatch_id
    assert envelope["effect_key"] == "eff.key-1:2"
    assert envelope["workdir"] == spec.artifact_dir
    assert envelope["report"] == bridge.report_path(home, spec.dispatch_id)


# -- runner argv ------------------------------------------------------------


def test_runner_argv_shape(tmp_path):
    home = str(tmp_path)
    argv = bridge.runner_argv(home, "d-3")
    assert argv[0] == sys.executable
    assert argv[1] == bridge.RUNNER_SCRIPT
    assert argv[1].endswith("adapter_runner.py")
    assert argv[2] == bridge.request_path(home, "d-3")


# -- closed constants -------------------------------------------------------


def test_bridge_constants_stay_closed():
    assert set(bridge.ADAPTERS) == {"synthetic"}
    assert bridge.REPORT_OUTCOMES == frozenset({"success", "failure"})
    assert bridge.MAX_PARAMS_BYTES == 64 * 1024
    assert bridge.EFFECT_KEY_RE.match("aB-9_.:x")
    assert not bridge.EFFECT_KEY_RE.match("")
