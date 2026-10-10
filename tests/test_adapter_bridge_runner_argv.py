"""P9 pins for courier_worker.adapter_bridge runner argv + envelope bounds.

Tests only; no behavior change. Pins the pure composition surface that the
other adapter_bridge P9 aspects do not cover: runner_argv, RUNNER_SCRIPT,
EFFECT_KEY_RE, REPORT_OUTCOMES, MAX_PARAMS_BYTES, and read_report
fail-closed (absent/malformed -> None). Offline; no network calls.
"""

import json
import os
import sys

from courier_worker.adapter_bridge import (
    EFFECT_KEY_RE,
    MAX_PARAMS_BYTES,
    REPORT_OUTCOMES,
    RUNNER_SCRIPT,
    read_report,
    report_path,
    request_path,
    runner_argv,
)


def test_runner_argv_shape_uses_current_executable_and_runner_script():
    argv = runner_argv("/home", "d1")
    assert isinstance(argv, tuple) and len(argv) == 3
    assert argv[0] == sys.executable
    assert argv[1] == RUNNER_SCRIPT


def test_runner_script_is_absolute_adapter_runner():
    assert os.path.isabs(RUNNER_SCRIPT)
    assert os.path.basename(RUNNER_SCRIPT) == "adapter_runner.py"
    assert os.path.isfile(RUNNER_SCRIPT)


def test_runner_argv_request_path_matches_request_path_helper():
    home, dispatch = "/home", "dispatch-7"
    assert runner_argv(home, dispatch)[2] == request_path(home, dispatch)


def test_runner_argv_sanitizes_unsafe_dispatch_id(tmp_path):
    home = str(tmp_path)
    argv = runner_argv(home, "a/b c")
    assert argv[2] == request_path(home, "a/b c")
    assert argv[2].endswith("a_b_c.json")
    assert os.path.dirname(argv[2]).endswith(os.path.join("run", "requests"))


def test_effect_key_re_accepts_valid_keys():
    assert EFFECT_KEY_RE.match("a")
    assert EFFECT_KEY_RE.match("A-1_.:x")
    assert EFFECT_KEY_RE.match("x" * 200)


def test_effect_key_re_rejects_malformed_keys():
    assert not EFFECT_KEY_RE.match("")
    assert not EFFECT_KEY_RE.match("x" * 201)
    for bad in ["a/b", "a b", "a*b", "caf\u00e9"]:
        assert not EFFECT_KEY_RE.match(bad)


def test_report_outcomes_and_params_bound_constants():
    assert REPORT_OUTCOMES == frozenset({"success", "failure"})
    assert MAX_PARAMS_BYTES == 64 * 1024


def test_read_report_absent_returns_none(tmp_path):
    assert read_report(str(tmp_path), "missing") is None


def _write_report_raw(home, dispatch, raw: str):
    path = report_path(home, dispatch)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(raw)


def test_read_report_malformed_json_returns_none(tmp_path):
    home = str(tmp_path)
    _write_report_raw(home, "d1", "{not json")
    assert read_report(home, "d1") is None


def test_read_report_bad_outcome_returns_none(tmp_path):
    home = str(tmp_path)
    _write_report_raw(home, "d1", json.dumps({"outcome": "maybe", "retryable": False}))
    assert read_report(home, "d1") is None


def test_read_report_non_bool_retryable_returns_none(tmp_path):
    home = str(tmp_path)
    _write_report_raw(home, "d1", json.dumps({"outcome": "success", "retryable": "yes"}))
    assert read_report(home, "d1") is None


def test_read_report_success_roundtrip(tmp_path):
    home = str(tmp_path)
    _write_report_raw(home, "d1", json.dumps({"outcome": "success", "retryable": True}))
    assert read_report(home, "d1") == {"outcome": "success", "retryable": True}
