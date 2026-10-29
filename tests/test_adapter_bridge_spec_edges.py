"""P9 test hardening for courier_worker.adapter_bridge (spec/report edges).

Tests only; no behavior change. Covers the pure offline surface at the
base commit: dispatch-id sanitizing, request/report paths, claim-spec
validation (fail-closed), runner argv, report reading, and cleanup.
No network, no subprocesses, no credentials.
"""

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


def valid_spec(**overrides):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "eff-1"}
    base.update(overrides)
    return base


# --- _safe / paths -----------------------------------------------------------

def test_safe_keeps_plain_ids():
    assert adapter_bridge._safe("abc-123_X.y") == "abc-123_X.y"


def test_safe_neutralizes_separators_and_traversal():
    cleaned = adapter_bridge._safe("../../etc/passwd")
    assert "/" not in cleaned and "\\" not in cleaned
    assert cleaned != "../../etc/passwd"
    # without a separator the remainder cannot escape its directory
    assert os.path.basename(os.path.join("/home/w", cleaned)) == cleaned


def test_safe_empty_becomes_unnamed():
    assert adapter_bridge._safe("") == "unnamed"


def test_request_and_report_paths_nest_under_home():
    req = request_path("/home/w", "d1")
    rep = report_path("/home/w", "d1")
    assert req == os.path.join("/home/w", "run", "requests", "d1.json")
    assert rep == os.path.join("/home/w", "run", "reports", "d1.json")


def test_paths_sanitize_hostile_dispatch():
    req = request_path("/home/w", "a/b")
    assert "/home/w" in req and "a/b.json" not in req


# --- validate_request: fail-closed ------------------------------------------

@pytest.mark.parametrize("spec", [
    [],
    "adapter",
    None,
    42,
])
def test_rejects_non_dict_spec(spec):
    with pytest.raises(SpecError):
        validate_request(spec)


def test_rejects_argv_carrying_spec():
    with pytest.raises(SpecError):
        validate_request(valid_spec(argv=["evil"]))


@pytest.mark.parametrize("adapter", [None, 42, "", "unknown-adapter", "SYNTHETIC"])
def test_rejects_non_allowlisted_adapter(adapter):
    with pytest.raises(SpecError):
        validate_request(valid_spec(adapter=adapter))


@pytest.mark.parametrize("params", [None, [], "x", 42])
def test_rejects_non_object_params(params):
    with pytest.raises(SpecError):
        validate_request(valid_spec(params=params))


def test_rejects_non_json_params():
    with pytest.raises(SpecError):
        validate_request(valid_spec(params={"v": float("nan")}))


def test_rejects_oversize_params():
    assert MAX_PARAMS_BYTES == 64 * 1024
    with pytest.raises(SpecError):
        validate_request(valid_spec(params={"blob": "x" * (MAX_PARAMS_BYTES + 1)}))


def test_rejects_params_failed_by_adapter_validator():
    with pytest.raises(SpecError):
        validate_request(valid_spec(params={"sleep_s": -1}))


@pytest.mark.parametrize("key", [None, "", 42, "has space", "x" * 201, "semi;colon?"])
def test_rejects_missing_or_malformed_effect_key(key):
    spec = {"adapter": "synthetic", "params": {}}
    if key is not None or "effect_key" in spec:
        spec["effect_key"] = key
    with pytest.raises(SpecError):
        validate_request(spec)


def test_accepts_max_length_effect_key():
    adapter, params, key = validate_request(valid_spec(effect_key="k" * 200))
    assert (adapter, key) == ("synthetic", "k" * 200)


def test_success_returns_adapter_params_and_key():
    params = {"sleep_s": 0}
    adapter, out_params, key = validate_request(valid_spec(params=params))
    assert adapter == "synthetic"
    assert out_params == params
    assert key == "eff-1"


def test_adapters_registry_is_closed_synthetic_only():
    assert set(ADAPTERS) == {"synthetic"}
    assert EFFECT_KEY_RE.match("A9_.-:x")
    assert not EFFECT_KEY_RE.match("")


# --- runner argv -------------------------------------------------------------

def test_runner_argv_uses_worker_runner_and_request_path():
    argv = runner_argv("/home/w", "d9")
    assert argv == (sys.executable, RUNNER_SCRIPT, request_path("/home/w", "d9"))
    assert RUNNER_SCRIPT.endswith("adapter_runner.py")


# --- reports -----------------------------------------------------------------

def _write_report(home, dispatch_id, payload, raw=False):
    path = report_path(home, dispatch_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload if raw else json.dumps(payload))


def test_read_report_none_when_absent(tmp_path):
    assert read_report(str(tmp_path), "missing") is None


def test_read_report_none_when_malformed(tmp_path):
    _write_report(str(tmp_path), "d", "{not json", raw=True)
    assert read_report(str(tmp_path), "d") is None


@pytest.mark.parametrize("payload", [
    {"outcome": "bogus", "retryable": False},
    {"outcome": "success", "retryable": "yes"},
    {"outcome": "success", "retryable": 1},
    ["success"],
    {"no_outcome": True},
])
def test_read_report_none_for_bad_shape(tmp_path, payload):
    _write_report(str(tmp_path), "d", payload)
    assert read_report(str(tmp_path), "d") is None


@pytest.mark.parametrize("outcome", sorted(REPORT_OUTCOMES))
def test_read_report_returns_valid_outcomes(tmp_path, outcome):
    payload = {"outcome": outcome, "retryable": False}
    _write_report(str(tmp_path), "d", payload)
    assert read_report(str(tmp_path), "d") == payload


def test_write_request_persists_envelope_and_drops_stale_report(tmp_path):
    home = str(tmp_path)
    spec = SimpleNamespace(
        adapter="synthetic", params={}, attempt=1, task_id="t1",
        dispatch_id="d2", effect_key="k", artifact_dir="art/d2",
    )
    _write_report(home, "d2", {"outcome": "success", "retryable": False})
    path = write_request(home, spec)
    assert path == request_path(home, "d2")
    assert read_report(home, "d2") is None  # stale report removed
    with open(path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["adapter"] == "synthetic"
    assert stored["dispatch_id"] == "d2"
    assert stored["report"] == report_path(home, "d2")


def test_cleanup_removes_request_and_report_without_error(tmp_path):
    home = str(tmp_path)
    spec = SimpleNamespace(
        adapter="synthetic", params={}, attempt=1, task_id="t1",
        dispatch_id="d3", effect_key="k", artifact_dir="art/d3",
    )
    write_request(home, spec)
    _write_report(home, "d3", {"outcome": "failure", "retryable": True})
    cleanup(home, "d3")
    assert not os.path.exists(request_path(home, "d3"))
    assert not os.path.exists(report_path(home, "d3"))
    cleanup(home, "d3")  # absent files are fine
