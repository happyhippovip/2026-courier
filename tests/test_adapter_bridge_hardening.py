"""P9 hardening for courier_worker.adapter_bridge (lane L4).

Tests only; no behavior change. Covers the allowlist bridge that maps a
declarative claim spec to the trusted runner: spec validation (fail closed),
host-owned path layout, request/report round trip, and cleanup. No network.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge
from courier_worker.adapter_bridge import (
    ADAPTERS,
    EFFECT_KEY_RE,
    MAX_PARAMS_BYTES,
    REPORT_OUTCOMES,
    RUNNER_SCRIPT,
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
    base = {"adapter": "synthetic", "params": {}, "effect_key": "key-1"}
    base.update(overrides)
    return base


def _ns(dispatch_id="d1"):
    return SimpleNamespace(
        adapter="synthetic",
        params={},
        attempt=1,
        task_id="t1",
        dispatch_id=dispatch_id,
        effect_key="key-1",
        artifact_dir=os.path.join("artifacts", dispatch_id),
    )


# -- closed allowlist -------------------------------------------------------


def test_adapters_is_closed_to_synthetic_only():
    assert set(ADAPTERS) == {"synthetic"}


def test_runner_script_points_at_adapter_runner_file():
    assert os.path.basename(RUNNER_SCRIPT) == "adapter_runner.py"
    assert os.path.isfile(RUNNER_SCRIPT)


# -- path layout ------------------------------------------------------------


def test_request_and_report_paths_use_host_owned_layout():
    assert request_path("HOME", "d1") == os.path.join("HOME", "run", "requests", "d1.json")
    assert report_path("HOME", "d1") == os.path.join("HOME", "run", "reports", "d1.json")


def test_unsafe_dispatch_chars_are_neutralized():
    path = request_path("HOME", "a/b\\c:d")
    name = os.path.basename(path)
    assert "/" not in name and "\\" not in name and ":" not in name
    assert name.endswith(".json")


def test_empty_dispatch_id_falls_back_to_unnamed():
    assert os.path.basename(request_path("H", "")) == "unnamed.json"
    assert os.path.basename(report_path("H", "")) == "unnamed.json"


def test_runner_argv_uses_current_interpreter_and_request_path():
    argv = runner_argv("HOME", "d9")
    assert argv[0] == sys.executable
    assert argv[1] == RUNNER_SCRIPT
    assert argv[2] == request_path("HOME", "d9")


# -- validate_request: happy path -------------------------------------------


def test_valid_spec_returns_adapter_params_effect_key():
    adapter, params, key = validate_request(_spec())
    assert adapter == "synthetic"
    assert params == {}
    assert key == "key-1"


def test_valid_spec_accepts_effect_key_shapes():
    for key in ("a", "A-1_b.c:d", "x" * 200):
        assert validate_request(_spec(effect_key=key))[2] == key
    assert EFFECT_KEY_RE.match("a-b_c.d:e")


# -- validate_request: fail closed ------------------------------------------


@pytest.mark.parametrize("bad", [None, [], "spec", 42])
def test_non_dict_spec_is_refused(bad):
    with pytest.raises(SpecError):
        validate_request(bad)


def test_argv_in_spec_is_refused():
    spec = _spec()
    spec["argv"] = ["anything"]
    with pytest.raises(SpecError):
        validate_request(spec)


@pytest.mark.parametrize("bad", [None, "", "rm -rf", "SYNTHETIC", "local_shell", 42])
def test_unknown_or_non_string_adapter_is_refused(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(adapter=bad))


@pytest.mark.parametrize("bad", [None, [], "params", 42])
def test_non_dict_params_are_refused(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(params=bad))


def test_non_json_params_are_refused():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"v": float("nan")}))
    with pytest.raises(SpecError):
        validate_request(_spec(params={"v": {"nested"}}))


def test_oversized_params_are_refused():
    big = {"blob": "x" * (MAX_PARAMS_BYTES + 1024)}
    with pytest.raises(SpecError):
        validate_request(_spec(params=big))


def test_params_rejected_by_adapter_validator_are_refused():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"write": "../escape.txt"}))
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": -1}))


@pytest.mark.parametrize("bad", [None, "", "has space", "has/slash", "x" * 201, 42])
def test_missing_or_malformed_effect_key_is_refused(bad):
    spec = _spec()
    if bad is None:
        del spec["effect_key"]
    else:
        spec["effect_key"] = bad
    with pytest.raises(SpecError):
        validate_request(spec)


# -- request / report round trip --------------------------------------------


def test_write_request_persists_expected_keys(tmp_path):
    home = str(tmp_path)
    path = write_request(home, _ns("d2"))
    assert path == request_path(home, "d2")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["adapter"] == "synthetic"
    assert data["params"] == {}
    assert data["attempt"] == 1
    assert data["task_id"] == "t1"
    assert data["dispatch_id"] == "d2"
    assert data["effect_key"] == "key-1"
    assert data["report"] == report_path(home, "d2")


def test_write_request_removes_stale_report(tmp_path):
    home = str(tmp_path)
    stale = report_path(home, "d3")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        fh.write('{"outcome": "success"}')
    write_request(home, _ns("d3"))
    assert not os.path.exists(stale)


def test_write_request_leaves_no_temp_files(tmp_path):
    home = str(tmp_path)
    write_request(home, _ns("d4"))
    leftovers = [
        name
        for root, _, files in os.walk(home)
        for name in files
        if name.startswith(".tmp-")
    ]
    assert leftovers == []


@pytest.mark.parametrize("outcome", sorted(REPORT_OUTCOMES))
def test_read_report_returns_well_formed_outcomes(tmp_path, outcome):
    home = str(tmp_path)
    path = report_path(home, "d5")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": outcome, "retryable": outcome == "failure"}, fh)
    report = read_report(home, "d5")
    assert report is not None
    assert report["outcome"] == outcome


def test_read_report_returns_none_when_missing(tmp_path):
    assert read_report(str(tmp_path), "nope") is None


def test_read_report_returns_none_for_malformed_content(tmp_path):
    home = str(tmp_path)
    path = report_path(home, "d6")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not json {")
    assert read_report(home, "d6") is None


@pytest.mark.parametrize(
    "payload",
    ["[1, 2]", '{"outcome": "weird"}', '{"outcome": "success", "retryable": "yes"}'],
)
def test_read_report_returns_none_for_bad_shape(tmp_path, payload):
    home = str(tmp_path)
    path = report_path(home, "d7")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload)
    assert read_report(home, "d7") is None


def test_cleanup_removes_request_and_report_and_is_idempotent(tmp_path):
    home = str(tmp_path)
    write_request(home, _ns("d8"))
    os.makedirs(os.path.dirname(report_path(home, "d8")), exist_ok=True)
    with open(report_path(home, "d8"), "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    cleanup(home, "d8")
    assert not os.path.exists(request_path(home, "d8"))
    assert not os.path.exists(report_path(home, "d8"))
    cleanup(home, "d8")  # missing files are fine
