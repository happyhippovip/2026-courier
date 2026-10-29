"""P9 hardening pins for courier_worker.adapter_bridge (empty + hostile dispatch edges).

Tests only: no behavior change. All cases are offline (tmp_path, no network,
no credentials). Focus: degenerate dispatch ids must never escape their
directories or produce empty filenames, and malformed reports/requests must
fail closed to None/SpecError.
"""

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as ab
from courier_worker.host import SpecError


def _valid_spec(**over):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "e-1"}
    base.update(over)
    return base


# -- _safe / paths -----------------------------------------------------------

def test_safe_empty_dispatch_gives_unnamed():
    assert ab._safe("") == "unnamed"


def test_safe_never_returns_empty():
    for raw in ["", "///", "...", "   "]:
        assert ab._safe(raw) != ""


def test_safe_hostile_chars_cannot_escape():
    assert "/" not in ab._safe("a/b")
    assert "\\" not in ab._safe("a\\b")
    assert ab._safe("../..") == ".._.."
    assert ab._safe("a b") == "a_b"


def test_request_and_report_paths_use_unnamed_for_empty(tmp_path):
    home = str(tmp_path)
    assert ab.request_path(home, "").endswith(os.path.join("run", "requests", "unnamed.json"))
    assert ab.report_path(home, "").endswith(os.path.join("run", "reports", "unnamed.json"))


def test_paths_stay_inside_home_dirs(tmp_path):
    home = str(tmp_path)
    req = ab.request_path(home, "../../evil")
    rep = ab.report_path(home, "../../evil")
    assert req.startswith(os.path.join(home, "run", "requests") + os.sep)
    assert rep.startswith(os.path.join(home, "run", "reports") + os.sep)


# -- validate_request fail-closed --------------------------------------------

def test_validate_request_rejects_non_dict():
    with pytest.raises(SpecError):
        ab.validate_request(None)
    with pytest.raises(SpecError):
        ab.validate_request([])


def test_validate_request_rejects_argv():
    spec = _valid_spec()
    spec["argv"] = ["anything"]
    with pytest.raises(SpecError):
        ab.validate_request(spec)


def test_validate_request_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(adapter="not-a-real-adapter"))


def test_validate_request_rejects_missing_or_bad_effect_key():
    bad = dict(_valid_spec())
    del bad["effect_key"]
    with pytest.raises(SpecError):
        ab.validate_request(bad)
    for key in ["", "has space", "a" * 201, "slash/no"]:
        with pytest.raises(SpecError):
            ab.validate_request(_valid_spec(effect_key=key))


def test_validate_request_rejects_non_plain_json_params():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"sleep_s": float("nan")}))
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"blob": {1, 2}}))


def test_validate_request_rejects_oversized_params():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"blob": "x" * (70 * 1024)}))


def test_validate_request_rejects_invalid_synthetic_params():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"sleep_s": -1}))


def test_validate_request_accepts_minimal_synthetic():
    adapter, params, key = ab.validate_request(_valid_spec())
    assert adapter == "synthetic"
    assert key == "e-1"


# -- read_report fail-closed ---------------------------------------------------

def test_read_report_missing_returns_none(tmp_path):
    assert ab.read_report(str(tmp_path), "nope") is None


def test_read_report_malformed_returns_none(tmp_path):
    home = str(tmp_path)
    path = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert ab.read_report(home, "d1") is None


def test_read_report_rejects_bad_outcome(tmp_path):
    home = str(tmp_path)
    path = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "weird", "retryable": False}, fh)
    assert ab.read_report(home, "d1") is None


def test_read_report_rejects_non_bool_retryable(tmp_path):
    home = str(tmp_path)
    path = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "failure", "retryable": "yes"}, fh)
    assert ab.read_report(home, "d1") is None


def test_read_report_accepts_valid(tmp_path):
    home = str(tmp_path)
    path = ab.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    assert ab.read_report(home, "d1") == {"outcome": "success", "retryable": False}


# -- cleanup / argv / write_request --------------------------------------------

def test_cleanup_is_idempotent(tmp_path):
    home = str(tmp_path)
    ab.cleanup(home, "ghost")
    ab.cleanup(home, "ghost")


def test_runner_argv_shape_carries_no_spec_text(tmp_path):
    home = str(tmp_path)
    argv = ab.runner_argv(home, "d1")
    assert argv[0] == sys.executable
    assert argv[1].endswith("adapter_runner.py")
    assert argv[2] == ab.request_path(home, "d1")


def test_write_request_removes_stale_report(tmp_path):
    home = str(tmp_path)
    stale = ab.report_path(home, "d9")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    spec = SimpleNamespace(adapter="synthetic", params={}, attempt=1,
                           task_id="t1", dispatch_id="d9", effect_key="e-9",
                           artifact_dir=os.path.join(home, "artifacts", "d9"))
    path = ab.write_request(home, spec)
    assert path == ab.request_path(home, "d9")
    assert os.path.exists(path)
    assert not os.path.exists(stale)
    with open(path, encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["adapter"] == "synthetic"
    assert stored["effect_key"] == "e-9"

