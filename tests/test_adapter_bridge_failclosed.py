"""Fail-closed contract tests for courier_worker.adapter_bridge.

Covers the allowlist boundary without running any adapter or touching the
network: malformed claim specs are refused before any process exists, paths
stay inside the host-owned layout, and reports are only trusted when they
have the exact structured shape.
"""

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker.adapter_bridge import (
    MAX_PARAMS_BYTES,
    REPORT_OUTCOMES,
    RUNNER_SCRIPT,
    _safe,
    cleanup,
    read_report,
    report_path,
    request_path,
    runner_argv,
    validate_request,
    write_request,
)
from courier_worker.host import SpecError


def _spec(**overrides):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "eff-1"}
    base.update(overrides)
    return base


# -- validate_request: structural refusal ------------------------------------


def test_rejects_non_dict_spec():
    for bad in (None, [], "synthetic", 42):
        with pytest.raises(SpecError):
            validate_request(bad)


def test_rejects_spec_carrying_argv():
    spec = _spec()
    spec["argv"] = ["anything"]
    with pytest.raises(SpecError):
        validate_request(spec)


def test_rejects_unknown_adapter():
    for bad_adapter in ("nope", "", "SYNTHETIC", "../synthetic", None, 7):
        with pytest.raises(SpecError):
            validate_request(_spec(adapter=bad_adapter))


def test_rejects_non_dict_params():
    for bad_params in (None, [], "x", 5):
        with pytest.raises(SpecError):
            validate_request(_spec(params=bad_params))


def test_rejects_non_json_params():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"v": float("nan")}))
    with pytest.raises(SpecError):
        validate_request(_spec(params={"v": object()}))


def test_rejects_oversize_params():
    assert MAX_PARAMS_BYTES == 64 * 1024
    with pytest.raises(SpecError):
        validate_request(_spec(params={"blob": "x" * (MAX_PARAMS_BYTES + 1)}))


def test_rejects_missing_or_malformed_effect_key():
    spec = _spec()
    del spec["effect_key"]
    with pytest.raises(SpecError):
        validate_request(spec)
    for bad_key in ("", "has space", "has/slash", "line\nbreak", "x" * 201, None, 9):
        with pytest.raises(SpecError):
            validate_request(_spec(effect_key=bad_key))


def test_rejects_params_refused_by_adapter_validator():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": -1}))
    with pytest.raises(SpecError):
        validate_request(_spec(params={"write": "../escape.txt"}))


def test_accepts_minimal_valid_spec():
    params = {"content": "hi"}
    adapter, out_params, effect_key = validate_request(_spec(params=params))
    assert adapter == "synthetic"
    assert out_params == params
    assert effect_key == "eff-1"


def test_accepts_dotted_effect_key():
    _, _, effect_key = validate_request(_spec(effect_key="job:1.attempt_2-ok"))
    assert effect_key == "job:1.attempt_2-ok"


# -- path layout: everything stays host-owned ---------------------------------


def test_safe_sanitizes_separators_and_empty():
    assert "/" not in _safe("../../etc/passwd")
    assert "\\" not in _safe("a\\b")
    assert _safe("") == "unnamed"
    assert _safe("ok-1_2.3") == "ok-1_2.3"


def test_request_and_report_paths_are_scoped(tmp_path):
    home = str(tmp_path)
    req = request_path(home, "d1")
    rep = report_path(home, "d1")
    assert req == os.path.join(home, "run", "requests", "d1.json")
    assert rep == os.path.join(home, "run", "reports", "d1.json")
    hostile = request_path(home, "../escape")
    assert os.path.dirname(hostile) == os.path.join(home, "run", "requests")


def test_runner_argv_uses_own_runner_and_request_path(tmp_path):
    home = str(tmp_path)
    argv = runner_argv(home, "d9")
    assert argv[0] == sys.executable
    assert argv[1] == RUNNER_SCRIPT
    assert os.path.basename(argv[1]) == "adapter_runner.py"
    assert os.path.isfile(argv[1])
    assert argv[2] == request_path(home, "d9")


# -- request/report round-trip -------------------------------------------------


def _claim(dispatch_id="d1"):
    return SimpleNamespace(
        adapter="synthetic",
        params={"content": "x"},
        attempt=1,
        task_id="t1",
        dispatch_id=dispatch_id,
        effect_key="eff-1",
        artifact_dir=os.path.join("artifacts", dispatch_id),
    )


def test_read_report_absent_is_none(tmp_path):
    assert read_report(str(tmp_path), "missing") is None


def test_read_report_rejects_malformed(tmp_path):
    home = str(tmp_path)
    rep = report_path(home, "d1")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    for bad in ("not json{", "[1, 2]", '{"outcome": "maybe"}',
                '{"outcome": "success", "retryable": "yes"}'):
        with open(rep, "w", encoding="utf-8") as fh:
            fh.write(bad)
        assert read_report(home, "d1") is None


def test_write_request_round_trip_and_report_shapes(tmp_path):
    home = str(tmp_path)
    path = write_request(home, _claim("d2"))
    assert path == request_path(home, "d2")
    with open(path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["adapter"] == "synthetic"
    assert stored["dispatch_id"] == "d2"
    assert stored["report"] == report_path(home, "d2")

    rep = report_path(home, "d2")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    good = {"outcome": "success", "retryable": False}
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump(good, fh)
    assert read_report(home, "d2") == good
    assert REPORT_OUTCOMES == frozenset({"success", "failure"})


def test_write_request_drops_stale_report(tmp_path):
    home = str(tmp_path)
    rep = report_path(home, "d3")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write('{"outcome": "success", "retryable": false}')
    write_request(home, _claim("d3"))
    assert read_report(home, "d3") is None


def test_write_request_leaves_no_temp_files(tmp_path):
    home = str(tmp_path)
    write_request(home, _claim("d4"))
    leftovers = [p for p in (tmp_path / "run" / "requests").iterdir()
                 if p.name.startswith(".tmp-")]
    assert leftovers == []


def test_cleanup_removes_both_files_and_is_idempotent(tmp_path):
    home = str(tmp_path)
    write_request(home, _claim("d5"))
    rep = report_path(home, "d5")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write('{"outcome": "failure", "retryable": true}')
    cleanup(home, "d5")
    assert not os.path.exists(request_path(home, "d5"))
    assert not os.path.exists(rep)
    cleanup(home, "d5")  # absent files are not an error
