"""P9 hardening for courier_worker.adapter_bridge: path helpers + report/cleanup pins.

Tests only; no behavior change. Focused slice on the host-owned path layout
and the side-effect-light report/cleanup surface, independent of the other
open P9 adapter_bridge PRs (which use separate filenames):

- ``_safe`` sanitizing + ``request_path``/``report_path`` layout
- ``runner_argv`` shape + ``RUNNER_SCRIPT`` identity
- ``read_report`` malformed handling (no network, no subprocess)
- ``cleanup`` idempotency + ``_atomic_json``/``write_request`` basics
- ``validate_request`` fail-closed taxonomy (synthetic happy path is offline)

Filesystem use is limited to pytest's ``tmp_path``. No network calls,
no credentials, no subprocesses.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

from courier_worker import adapter_bridge
from courier_worker.adapter_bridge import (
    ADAPTERS,
    MAX_PARAMS_BYTES,
    REPORT_OUTCOMES,
    RUNNER_SCRIPT,
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
from courier_worker.host import SpecError


def _ns(dispatch_id="d1", **over):
    base = {
        "adapter": "synthetic",
        "params": {},
        "attempt": 1,
        "task_id": "t1",
        "dispatch_id": dispatch_id,
        "effect_key": "key-1",
        "artifact_dir": os.path.join("artifacts", dispatch_id),
    }
    base.update(over)
    return SimpleNamespace(**base)


# -- _safe + paths -----------------------------------------------------------


def test_safe_keeps_plain_dispatch_ids():
    assert _safe("dispatch-1.2_3") == "dispatch-1.2_3"


def test_safe_neutralizes_separators():
    assert _safe("a/b c\\d:e") == "a_b_c_d_e"


def test_safe_empty_falls_back_to_unnamed():
    assert _safe("") == "unnamed"


def test_request_and_report_paths_use_host_owned_layout():
    home = os.path.join("home", "root")
    assert request_path(home, "d1") == os.path.join(home, "run", "requests", "d1.json")
    assert report_path(home, "d1") == os.path.join(home, "run", "reports", "d1.json")


def test_paths_sanitize_unsafe_dispatch_ids():
    home = "HOME"
    assert request_path(home, "a/b").endswith(os.path.join("requests", "a_b.json"))
    assert report_path(home, "a/b").endswith(os.path.join("reports", "a_b.json"))


def test_paths_empty_dispatch_id_uses_unnamed():
    home = "HOME"
    assert os.path.basename(request_path(home, "")) == "unnamed.json"
    assert os.path.basename(report_path(home, "")) == "unnamed.json"


# -- runner argv + constants -------------------------------------------------


def test_runner_script_points_at_adapter_runner_file():
    assert os.path.basename(RUNNER_SCRIPT) == "adapter_runner.py"
    assert os.path.isfile(RUNNER_SCRIPT)


def test_runner_argv_shape():
    home, dispatch = "HOME", "dsp-7"
    argv = runner_argv(home, dispatch)
    assert isinstance(argv, tuple) and len(argv) == 3
    assert argv[0] == sys.executable
    assert argv[1] == RUNNER_SCRIPT
    assert argv[2] == request_path(home, dispatch)


def test_adapters_allowlist_is_closed_to_synthetic():
    assert set(ADAPTERS) == {"synthetic"}


def test_params_size_bound_and_report_outcomes():
    assert MAX_PARAMS_BYTES == 64 * 1024
    assert REPORT_OUTCOMES == frozenset({"success", "failure"})


# -- read_report malformed handling ------------------------------------------


def test_read_report_none_when_missing(tmp_path):
    assert read_report(str(tmp_path), "nope") is None


def test_read_report_none_when_invalid_json(tmp_path):
    path = report_path(str(tmp_path), "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert read_report(str(tmp_path), "d1") is None


def test_read_report_none_when_not_a_dict(tmp_path):
    path = report_path(str(tmp_path), "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(["success"], fh)
    assert read_report(str(tmp_path), "d1") is None


def test_read_report_none_when_outcome_unknown(tmp_path):
    path = report_path(str(tmp_path), "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "maybe", "retryable": False}, fh)
    assert read_report(str(tmp_path), "d1") is None


def test_read_report_none_when_retryable_not_bool(tmp_path):
    path = report_path(str(tmp_path), "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": "yes"}, fh)
    assert read_report(str(tmp_path), "d1") is None


def test_read_report_returns_valid_success_and_failure(tmp_path):
    home = str(tmp_path)
    for outcome in ("success", "failure"):
        path = report_path(home, f"d-{outcome}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"outcome": outcome, "retryable": False, "reason": "r"}, fh)
        got = read_report(home, f"d-{outcome}")
        assert got is not None and got["outcome"] == outcome
        assert got["retryable"] is False


# -- cleanup idempotency -----------------------------------------------------


def test_cleanup_removes_request_and_report(tmp_path):
    home = str(tmp_path)
    spec = _ns("d-clean")
    write_request(home, spec)
    assert os.path.isfile(request_path(home, "d-clean"))
    cleanup(home, "d-clean")
    assert not os.path.exists(request_path(home, "d-clean"))
    assert not os.path.exists(report_path(home, "d-clean"))


def test_cleanup_idempotent_when_missing(tmp_path):
    home = str(tmp_path)
    cleanup(home, "missing")
    cleanup(home, "missing")


def test_cleanup_preserves_unrelated_files(tmp_path):
    home = str(tmp_path)
    other = os.path.join(home, "run", "requests", "other.json")
    os.makedirs(os.path.dirname(other), exist_ok=True)
    with open(other, "w", encoding="utf-8") as fh:
        fh.write("{}")
    cleanup(home, "d1")
    assert os.path.isfile(other)


# -- write_request + _atomic_json basics -------------------------------------


def test_write_request_returns_path_and_expected_keys(tmp_path):
    home = str(tmp_path)
    spec = _ns("d-wr")
    path = write_request(home, spec)
    assert path == request_path(home, "d-wr")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["adapter"] == "synthetic"
    assert data["dispatch_id"] == "d-wr"
    assert data["report"] == report_path(home, "d-wr")
    assert data["attempt"] == 1


def test_write_request_removes_stale_report(tmp_path):
    home = str(tmp_path)
    stale = report_path(home, "d-stale")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    write_request(home, _ns("d-stale"))
    assert not os.path.exists(stale)


def test_atomic_json_creates_parent_dirs_and_roundtrips(tmp_path):
    path = os.path.join(str(tmp_path), "sub", "dir", "data.json")
    _atomic_json(path, {"b": 2, "a": 1})
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh) == {"a": 1, "b": 2}


# -- validate_request fail-closed taxonomy -----------------------------------


def test_validate_request_rejects_non_dict_spec():
    for bad in (None, [], "x", 42):
        try:
            validate_request(bad)
        except SpecError:
            pass
        else:
            raise AssertionError(f"expected SpecError for {bad!r}")


def test_validate_request_rejects_supplied_argv():
    with_str = {"adapter": "synthetic", "params": {}, "effect_key": "k-1", "argv": ["x"]}
    try:
        validate_request(with_str)
    except SpecError as exc:
        assert "argv" in str(exc).lower()
    else:
        raise AssertionError("expected SpecError for supplied argv")


def test_validate_request_rejects_unknown_adapter():
    try:
        validate_request({"adapter": "nope", "params": {}, "effect_key": "k-1"})
    except SpecError as exc:
        assert "allowlist" in str(exc).lower()
    else:
        raise AssertionError("expected SpecError for unknown adapter")


def test_validate_request_rejects_bad_effect_key():
    for bad_key in (None, "", "has space", 42):
        try:
            validate_request({"adapter": "synthetic", "params": {}, "effect_key": bad_key})
        except SpecError:
            pass
        else:
            raise AssertionError(f"expected SpecError for effect_key={bad_key!r}")


def test_validate_request_accepts_minimal_synthetic_offline():
    adapter, params, effect_key = validate_request(
        {"adapter": "synthetic", "params": {}, "effect_key": "ok-key_1"}
    )
    assert adapter == "synthetic"
    assert params == {}
    assert effect_key == "ok-key_1"


def test_bridge_module_exposes_spec_error():
    assert adapter_bridge.SpecError is SpecError
