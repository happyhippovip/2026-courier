"""Pure-unit hardening for courier_worker.adapter_bridge (P9).

Covers the allowlisted bridge's side-effect-free surface without running any
adapter, subprocess, or network call: dispatch-id sanitizing, request/report
path layout, closed adapter allowlist, claim-spec refusal taxonomy, runner
argv shape, atomic JSON writes, report parsing, and cleanup. Filesystem use
is limited to pytest's tmp_path.
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
    SpecError,
    _atomic_json,
    _safe,
    cleanup,
    read_report,
    report_path,
    request_path,
    runner_argv,
    validate_request,
    write_request,
)


def _spec(**over):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "ok-key_1"}
    base.update(over)
    return base


# -- _safe -----------------------------------------------------------------

def test_safe_keeps_plain_ids():
    assert _safe("dispatch-1.2_3") == "dispatch-1.2_3"


def test_safe_replaces_separators_and_spaces():
    assert _safe("a/b c\\d") == "a_b_c_d"


def test_safe_empty_becomes_unnamed():
    assert _safe("") == "unnamed"


# -- paths -----------------------------------------------------------------

def test_request_and_report_paths_live_under_home():
    home = os.path.join("home", "root")
    assert request_path(home, "d1") == os.path.join(home, "run", "requests", "d1.json")
    assert report_path(home, "d1") == os.path.join(home, "run", "reports", "d1.json")


def test_paths_sanitize_unsafe_dispatch_ids():
    home = "/home"
    assert request_path(home, "a/b").endswith(os.path.join("requests", "a_b.json"))
    assert report_path(home, "a/b").endswith(os.path.join("reports", "a_b.json"))


# -- module constants -------------------------------------------------------

def test_params_size_bound_is_64kib():
    assert MAX_PARAMS_BYTES == 64 * 1024


def test_report_outcomes_are_success_and_failure_only():
    assert REPORT_OUTCOMES == frozenset({"success", "failure"})


def test_runner_script_points_at_adapter_runner():
    assert RUNNER_SCRIPT.endswith("adapter_runner.py")


def test_adapters_registry_is_closed_but_lists_synthetic():
    assert set(ADAPTERS) == {"synthetic"}


# -- validate_request: structural refusals ----------------------------------

@pytest.mark.parametrize("bad", [None, [], "spec", 42])
def test_validate_request_refuses_non_dict_spec(bad):
    with pytest.raises(SpecError):
        validate_request(bad)


def test_validate_request_refuses_supplied_argv():
    spec = _spec()
    spec["argv"] = ["anything"]
    with pytest.raises(SpecError):
        validate_request(spec)


@pytest.mark.parametrize("bad", [None, 42, ["synthetic"], "unknown-adapter"])
def test_validate_request_refuses_non_allowlisted_adapter(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(adapter=bad))


@pytest.mark.parametrize("bad", [None, [], "params"])
def test_validate_request_refuses_non_dict_params(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(params=bad))


def test_validate_request_refuses_nan_params():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": float("nan")}))


def test_validate_request_refuses_non_serializable_params():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": {1, 2}}))


def test_validate_request_refuses_oversize_params():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"content": "x" * (MAX_PARAMS_BYTES + 1)}))


def test_validate_request_accepts_near_bound_params():
    adapter, params, effect_key = validate_request(
        _spec(params={"content": "x" * (MAX_PARAMS_BYTES // 2)}))
    assert adapter == "synthetic"
    assert effect_key == "ok-key_1"


def test_validate_request_wraps_adapter_rejection_as_spec_error():
    with pytest.raises(SpecError):
        validate_request(_spec(params={"sleep_s": -1}))


# -- validate_request: effect_key -------------------------------------------

@pytest.mark.parametrize("bad", [None, "", 42, "has space", "semi;colon", "slash/x"])
def test_validate_request_refuses_bad_effect_key(bad):
    with pytest.raises(SpecError):
        validate_request(_spec(effect_key=bad))


def test_validate_request_refuses_overlong_effect_key():
    with pytest.raises(SpecError):
        validate_request(_spec(effect_key="k" * 201))


def test_validate_request_accepts_effect_key_boundaries():
    assert EFFECT_KEY_RE.match("a:b-c.d_e") is not None
    adapter, _, effect_key = validate_request(_spec(effect_key="k" * 200))
    assert effect_key == "k" * 200


def test_validate_request_happy_path_returns_triple():
    assert validate_request(_spec()) == ("synthetic", {}, "ok-key_1")


# -- runner_argv -------------------------------------------------------------

def test_runner_argv_uses_current_interpreter_and_request_path():
    home = "/home"
    argv = runner_argv(home, "d 1")
    assert argv[0] == sys.executable
    assert argv[1] == RUNNER_SCRIPT
    assert argv[2] == request_path(home, "d 1")


# -- read_report --------------------------------------------------------------

def test_read_report_missing_file_is_none(tmp_path):
    assert read_report(str(tmp_path), "nope") is None


def test_read_report_malformed_json_is_none(tmp_path):
    target = report_path(str(tmp_path), "d")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert read_report(str(tmp_path), "d") is None


@pytest.mark.parametrize("body", [
    ["not", "a", "dict"],
    {"outcome": "weird", "retryable": False},
    {"outcome": "success", "retryable": "yes"},
    {"outcome": "success", "retryable": None},
])
def test_read_report_rejects_bad_envelopes(tmp_path, body):
    target = report_path(str(tmp_path), "d")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    assert read_report(str(tmp_path), "d") is None


def test_read_report_round_trips_success_and_failure(tmp_path):
    for outcome in ("success", "failure"):
        target = report_path(str(tmp_path), "d-" + outcome)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump({"outcome": outcome, "retryable": True}, fh)
        report = read_report(str(tmp_path), "d-" + outcome)
        assert report == {"outcome": outcome, "retryable": True}


def test_read_report_defaults_missing_retryable_to_false(tmp_path):
    target = report_path(str(tmp_path), "d")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success"}, fh)
    assert read_report(str(tmp_path), "d") == {"outcome": "success"}


# -- _atomic_json / write_request / cleanup ------------------------------------

def test_atomic_json_writes_sorted_keys_and_creates_parents(tmp_path):
    target = str(tmp_path / "sub" / "dir" / "req.json")
    _atomic_json(target, {"b": 1, "a": 2})
    with open(target, encoding="utf-8") as fh:
        assert json.load(fh) == {"a": 2, "b": 1}


def test_atomic_json_cleans_tmp_on_failure(tmp_path, monkeypatch):
    target = str(tmp_path / "req.json")
    os.makedirs(os.path.dirname(target), exist_ok=True)

    def _boom(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(json, "dump", _boom)
    with pytest.raises(RuntimeError):
        _atomic_json(target, {"a": 1})
    leftovers = [p for p in os.listdir(tmp_path) if p.startswith(".tmp-")]
    assert leftovers == []
    assert not os.path.exists(target)


def _claim(dispatch_id="d 1"):
    return SimpleNamespace(
        dispatch_id=dispatch_id, adapter="synthetic", params={},
        attempt=2, task_id="t-9", effect_key="k-9",
        artifact_dir=os.path.join("artifacts", dispatch_id),
    )


def test_write_request_persists_envelope_and_returns_path(tmp_path):
    home = str(tmp_path)
    path = write_request(home, _claim())
    assert path == request_path(home, "d 1")
    with open(path, encoding="utf-8") as fh:
        envelope = json.load(fh)
    assert envelope == {
        "adapter": "synthetic", "params": {}, "attempt": 2,
        "task_id": "t-9", "dispatch_id": "d 1", "effect_key": "k-9",
        "workdir": os.path.join("artifacts", "d 1"),
        "report": report_path(home, "d 1"),
    }


def test_write_request_removes_stale_report(tmp_path):
    home = str(tmp_path)
    stale = report_path(home, "d 1")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    write_request(home, _claim())
    assert not os.path.exists(stale)


def test_cleanup_removes_request_and_report_and_tolerates_absence(tmp_path):
    home = str(tmp_path)
    write_request(home, _claim())
    assert os.path.exists(request_path(home, "d 1"))
    cleanup(home, "d 1")
    assert not os.path.exists(request_path(home, "d 1"))
    assert not os.path.exists(report_path(home, "d 1"))
    cleanup(home, "d 1")  # idempotent


def test_spec_error_is_fail_closed_value_error():
    assert issubclass(SpecError, ValueError)
    assert adapter_bridge.SpecError is SpecError