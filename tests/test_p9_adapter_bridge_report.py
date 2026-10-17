"""P9 hardening pins for courier_worker.adapter_bridge report/paths surface.

Tests-only: no behavior change. Offline (tmp dirs only), no network,
no credentials, no local paths or hostnames.

Focus: read_report fail-closed edges, cleanup idempotency/scope,
_safe sanitization, request/report path layout, runner_argv shape.
"""

from __future__ import annotations

import json
import os

from courier_worker import adapter_bridge


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_read_report_missing_returns_none(tmp_path):
    home = str(tmp_path)
    assert adapter_bridge.read_report(home, "nope") is None


def test_read_report_malformed_json_returns_none(tmp_path):
    home = str(tmp_path)
    _write(adapter_bridge.report_path(home, "d1"), "{not-json")
    assert adapter_bridge.read_report(home, "d1") is None


def test_read_report_non_dict_returns_none(tmp_path):
    home = str(tmp_path)
    _write(adapter_bridge.report_path(home, "d1"), json.dumps(["success"]))
    assert adapter_bridge.read_report(home, "d1") is None


def test_read_report_missing_outcome_returns_none(tmp_path):
    home = str(tmp_path)
    _write(adapter_bridge.report_path(home, "d1"), json.dumps({"retryable": False}))
    assert adapter_bridge.read_report(home, "d1") is None


def test_read_report_bad_outcome_returns_none(tmp_path):
    home = str(tmp_path)
    _write(adapter_bridge.report_path(home, "d1"),
           json.dumps({"outcome": "weird", "retryable": False}))
    assert adapter_bridge.read_report(home, "d1") is None


def test_read_report_non_bool_retryable_returns_none(tmp_path):
    home = str(tmp_path)
    for bad in ("yes", 1, 0, None, [], {}):
        _write(adapter_bridge.report_path(home, "d1"),
               json.dumps({"outcome": "success", "retryable": bad}))
        assert adapter_bridge.read_report(home, "d1") is None, bad


def test_read_report_missing_retryable_defaults_false_ok(tmp_path):
    # retryable absent -> report.get("retryable", False) is False (a bool),
    # so the report is accepted.
    home = str(tmp_path)
    _write(adapter_bridge.report_path(home, "d1"), json.dumps({"outcome": "success"}))
    report = adapter_bridge.read_report(home, "d1")
    assert report == {"outcome": "success"}


def test_read_report_valid_success_round_trip(tmp_path):
    home = str(tmp_path)
    payload = {"outcome": "success", "retryable": True, "reason": "ok"}
    _write(adapter_bridge.report_path(home, "d1"), json.dumps(payload))
    assert adapter_bridge.read_report(home, "d1") == payload


def test_read_report_valid_failure_round_trip(tmp_path):
    home = str(tmp_path)
    payload = {"outcome": "failure", "retryable": False}
    _write(adapter_bridge.report_path(home, "d1"), json.dumps(payload))
    assert adapter_bridge.read_report(home, "d1") == payload


def test_report_outcomes_contains_only_success_failure():
    assert set(adapter_bridge.REPORT_OUTCOMES) == {"success", "failure"}


def test_cleanup_removes_request_and_report(tmp_path):
    home = str(tmp_path)
    req = adapter_bridge.request_path(home, "d1")
    rep = adapter_bridge.report_path(home, "d1")
    _write(req, "{}")
    _write(rep, json.dumps({"outcome": "success", "retryable": False}))
    adapter_bridge.cleanup(home, "d1")
    assert not os.path.exists(req)
    assert not os.path.exists(rep)


def test_cleanup_missing_files_is_idempotent(tmp_path):
    home = str(tmp_path)
    adapter_bridge.cleanup(home, "absent")
    adapter_bridge.cleanup(home, "absent")


def test_cleanup_does_not_remove_sibling_files(tmp_path):
    home = str(tmp_path)
    req = adapter_bridge.request_path(home, "d1")
    _write(req, "{}")
    sibling = os.path.join(home, "run", "requests", "other.json")
    _write(sibling, "{}")
    adapter_bridge.cleanup(home, "d1")
    assert not os.path.exists(req)
    assert os.path.exists(sibling)


def test_safe_sanitizes_unsafe_chars():
    assert adapter_bridge._safe("a/b\\c:d") == "a_b_c_d"
    assert adapter_bridge._safe("ok-1.2_3") == "ok-1.2_3"


def test_safe_empty_becomes_unnamed():
    assert adapter_bridge._safe("") == "unnamed"


def test_request_and_report_paths_use_safe_name_and_layout(tmp_path):
    home = str(tmp_path)
    req = adapter_bridge.request_path(home, "a/b")
    rep = adapter_bridge.report_path(home, "a/b")
    assert req == os.path.join(home, "run", "requests", "a_b.json")
    assert rep == os.path.join(home, "run", "reports", "a_b.json")


def test_runner_argv_shape(tmp_path):
    import sys

    home = str(tmp_path)
    argv = adapter_bridge.runner_argv(home, "d1")
    assert isinstance(argv, tuple) and len(argv) == 3
    assert argv[0] == sys.executable
    assert os.path.isabs(argv[1])
    assert argv[1].endswith("adapter_runner.py")
    assert argv[2] == adapter_bridge.request_path(home, "d1")
