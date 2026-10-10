"""Offline pins for courier_worker.adapter_bridge (lane L3, P9 test hardening).

The bridge maps a declarative claim spec to the worker's own runner using
only path math, closed allowlists, and atomic file writes. Everything here
runs without a controller, without subprocesses, and without the network:
path helpers, fail-closed spec validation, and request/report round-trips
under a temporary home directory.

No behavior change; this file only pins the existing contract.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as A
from courier_worker.host import SpecError


def _good_spec(**overrides):
    base = {
        "adapter": "synthetic",
        "params": {},
        "effect_key": "unit.1:attempt-1",
    }
    base.update(overrides)
    return base


def test_safe_replaces_separators_and_traversal():
    assert A._safe("a/b\\c") == "a_b_c"
    assert A._safe("../x") == ".._x"


def test_safe_empty_becomes_unnamed():
    assert A._safe("") == "unnamed"


def test_request_and_report_paths_share_layout(tmp_path):
    home = str(tmp_path)
    req = A.request_path(home, "d1")
    rep = A.report_path(home, "d1")
    assert req == os.path.join(home, "run", "requests", "d1.json")
    assert rep == os.path.join(home, "run", "reports", "d1.json")
    # Dispatch ids are sanitized so they cannot escape the run directories.
    evil = A.request_path(home, "../evil")
    assert os.path.dirname(evil) == os.path.join(home, "run", "requests")


def test_runner_argv_points_at_bundled_runner(tmp_path):
    home = str(tmp_path)
    argv = A.runner_argv(home, "d1")
    assert argv[0] == sys.executable
    assert argv[1] == A.RUNNER_SCRIPT
    assert os.path.basename(argv[1]) == "adapter_runner.py"
    assert os.path.isfile(argv[1])
    assert argv[2] == A.request_path(home, "d1")


def test_synthetic_adapter_is_allowlisted():
    assert "synthetic" in A.ADAPTERS


@pytest.mark.parametrize("spec", [
    None,
    [],
    "synthetic",
    42,
])
def test_validate_request_rejects_non_dict_spec(spec):
    with pytest.raises(SpecError):
        A.validate_request(spec)


def test_validate_request_rejects_argv_carrying_spec():
    spec = _good_spec(argv=["anything"])
    with pytest.raises(SpecError):
        A.validate_request(spec)


@pytest.mark.parametrize("adapter", ["unknown", "", None, 42])
def test_validate_request_rejects_non_allowlisted_adapter(adapter):
    with pytest.raises(SpecError):
        A.validate_request(_good_spec(adapter=adapter))


@pytest.mark.parametrize("params", [None, [], "x", 42])
def test_validate_request_rejects_non_object_params(params):
    with pytest.raises(SpecError):
        A.validate_request(_good_spec(params=params))


def test_validate_request_rejects_non_json_params():
    with pytest.raises(SpecError):
        A.validate_request(_good_spec(params={"v": float("nan")}))  # allow_nan=False


def test_validate_request_rejects_oversized_params():
    big = {"blob": "x" * (A.MAX_PARAMS_BYTES + 1)}
    with pytest.raises(SpecError):
        A.validate_request(_good_spec(params=big))


@pytest.mark.parametrize("effect_key", [
    None,
    42,
    "",
    "has space",
    "semi;colon",
    "x" * 201,
])
def test_validate_request_rejects_missing_or_malformed_effect_key(effect_key):
    spec = _good_spec()
    if effect_key is None:
        del spec["effect_key"]
    else:
        spec["effect_key"] = effect_key
    with pytest.raises(SpecError):
        A.validate_request(spec)


def test_validate_request_accepts_minimal_synthetic_spec():
    adapter, params, effect_key = A.validate_request(_good_spec())
    assert adapter == "synthetic"
    assert isinstance(params, dict)
    assert effect_key == "unit.1:attempt-1"


def test_validate_request_rejects_bad_synthetic_params():
    with pytest.raises(SpecError):
        A.validate_request(_good_spec(params={"write": "../escape.txt"}))


def test_read_report_absent_is_none(tmp_path):
    assert A.read_report(str(tmp_path), "missing") is None


def test_read_report_malformed_is_none(tmp_path):
    home = str(tmp_path)
    path = A.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert A.read_report(home, "d1") is None


@pytest.mark.parametrize("report", [
    {"outcome": "bogus", "retryable": False},
    {"outcome": "success"},  # retryable defaults to False, which is a bool: valid
    {"outcome": "success", "retryable": "yes"},
    {"outcome": "failure", "retryable": 1},
    ["success"],
])
def test_read_report_rejects_bad_shapes(tmp_path, report):
    home = str(tmp_path)
    path = A.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh)
    if report == {"outcome": "success"}:
        assert A.read_report(home, "d1") == report
    else:
        assert A.read_report(home, "d1") is None


@pytest.mark.parametrize("report", [
    {"outcome": "success", "retryable": False},
    {"outcome": "failure", "retryable": True, "detail": "boom"},
])
def test_read_report_returns_valid_report(tmp_path, report):
    home = str(tmp_path)
    path = A.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh)
    assert A.read_report(home, "d1") == report


def _stub_execution_spec(dispatch_id="d1"):
    return SimpleNamespace(
        adapter="synthetic",
        params={},
        attempt=1,
        task_id="t1",
        dispatch_id=dispatch_id,
        effect_key="unit.1:attempt-1",
        artifact_dir="artifacts/d1",
    )


def test_write_request_round_trip_and_cleanup(tmp_path):
    home = str(tmp_path)
    spec = _stub_execution_spec()
    path = A.write_request(home, spec)
    assert path == A.request_path(home, "d1")
    with open(path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["adapter"] == "synthetic"
    assert stored["dispatch_id"] == "d1"
    assert stored["effect_key"] == "unit.1:attempt-1"
    assert stored["report"] == A.report_path(home, "d1")
    A.cleanup(home, "d1")
    assert not os.path.exists(A.request_path(home, "d1"))
    assert not os.path.exists(A.report_path(home, "d1"))
    # Cleanup is idempotent.
    A.cleanup(home, "d1")


def test_write_request_drops_stale_report(tmp_path):
    home = str(tmp_path)
    stale = A.report_path(home, "d1")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    A.write_request(home, _stub_execution_spec())
    assert not os.path.exists(stale)


def test_atomic_json_creates_dirs_and_leaves_no_tmp(tmp_path):
    home = str(tmp_path)
    target = os.path.join(home, "nested", "dir", "req.json")
    A._atomic_json(target, {"b": 1, "a": 2})
    with open(target, encoding="utf-8") as fh:
        raw = fh.read()
    assert json.loads(raw) == {"a": 2, "b": 1}
    leftovers = [n for n in os.listdir(os.path.dirname(target)) if n.startswith(".tmp-")]
    assert leftovers == []
