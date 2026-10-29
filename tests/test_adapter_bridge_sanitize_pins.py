"""P9 hardening pins: dispatch-id sanitization + path containment for adapter_bridge.

Tests only; no behavior change. All offline (tmp_path, no network).
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge
from courier_worker.adapter_bridge import (
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


def test_safe_keeps_plain_ids():
    assert _safe("abc-123_X.y") == "abc-123_X.y"


def test_safe_replaces_separators_and_spaces():
    assert _safe("a/b\\c d:e") == "a_b_c_d_e"


def test_safe_empty_becomes_unnamed():
    assert _safe("") == "unnamed"


def test_safe_dots_only_stay_but_contained():
    # ".." is kept char-wise; containment is enforced by the fixed parent dir.
    assert _safe("..") == ".."
    home = "/tmp/home-probe"
    assert os.path.dirname(request_path(home, "..")) == os.path.join(home, "run", "requests")


def test_safe_traversal_becomes_flat():
    assert "/" not in _safe("../../etc/passwd")
    assert "\\" not in _safe("..\\..\\etc")


def test_request_path_layout():
    home = os.path.join("h", "ome")
    path = request_path(home, "d1")
    assert path == os.path.join(home, "run", "requests", "d1.json")


def test_report_path_layout():
    home = os.path.join("h", "ome")
    path = report_path(home, "d1")
    assert path == os.path.join(home, "run", "reports", "d1.json")


def test_request_path_never_escapes_home(tmp_path):
    home = str(tmp_path)
    for dispatch in ["../../etc/passwd", "..\\..\\x", "/abs", "", "a/b", "a b"]:
        path = request_path(home, dispatch)
        assert os.path.abspath(path).startswith(os.path.abspath(home) + os.sep)
        assert os.path.dirname(path) == os.path.join(home, "run", "requests")


def test_report_path_never_escapes_home(tmp_path):
    home = str(tmp_path)
    for dispatch in ["../../etc/passwd", "/abs", "", "a/b"]:
        path = report_path(home, dispatch)
        assert os.path.abspath(path).startswith(os.path.abspath(home) + os.sep)
        assert os.path.dirname(path) == os.path.join(home, "run", "reports")


def test_runner_argv_shape(tmp_path):
    home = str(tmp_path)
    argv = runner_argv(home, "d9")
    assert argv[0] == sys.executable
    assert os.path.isabs(argv[1])
    assert argv[1].endswith("adapter_runner.py")
    assert argv[2] == request_path(home, "d9")


def test_read_report_missing_is_none(tmp_path):
    assert read_report(str(tmp_path), "nope") is None


def test_read_report_malformed_json_is_none(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "run", "reports"), exist_ok=True)
    with open(report_path(home, "d1"), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert read_report(home, "d1") is None


def test_read_report_non_dict_is_none(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "run", "reports"), exist_ok=True)
    with open(report_path(home, "d1"), "w", encoding="utf-8") as fh:
        json.dump(["success"], fh)
    assert read_report(home, "d1") is None


def test_read_report_bad_outcome_is_none(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "run", "reports"), exist_ok=True)
    with open(report_path(home, "d1"), "w", encoding="utf-8") as fh:
        json.dump({"outcome": "maybe", "retryable": False}, fh)
    assert read_report(home, "d1") is None


def test_read_report_non_bool_retryable_is_none(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "run", "reports"), exist_ok=True)
    with open(report_path(home, "d1"), "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": "yes"}, fh)
    assert read_report(home, "d1") is None


def test_read_report_valid_round_trip(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "run", "reports"), exist_ok=True)
    with open(report_path(home, "d1"), "w", encoding="utf-8") as fh:
        json.dump({"outcome": "failure", "retryable": True, "reason": "x"}, fh)
    report = read_report(home, "d1")
    assert report is not None and report["outcome"] == "failure" and report["retryable"] is True


def _spec(dispatch="d1", **over):
    base = {
        "task_id": "t1",
        "dispatch_id": dispatch,
        "attempt": 1,
        "adapter": "synthetic",
        "params": {},
        "effect_key": "eff-1",
        "artifact_dir": os.path.join("artifacts", dispatch),
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_write_request_writes_expected_keys(tmp_path):
    home = str(tmp_path)
    spec = _spec()
    path = write_request(home, spec)
    assert path == request_path(home, "d1")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["adapter"] == "synthetic"
    assert data["dispatch_id"] == "d1"
    assert data["report"] == report_path(home, "d1")
    assert "workdir" in data and "params" in data


def test_write_request_removes_stale_report(tmp_path):
    home = str(tmp_path)
    os.makedirs(os.path.join(home, "run", "reports"), exist_ok=True)
    with open(report_path(home, "d1"), "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    write_request(home, _spec())
    assert not os.path.exists(report_path(home, "d1"))


def test_cleanup_is_idempotent_and_scoped(tmp_path):
    home = str(tmp_path)
    write_request(home, _spec(dispatch="d7"))
    keeper = os.path.join(home, "run", "requests", "keep.json")
    with open(keeper, "w", encoding="utf-8") as fh:
        fh.write("{}")
    cleanup(home, "d7")
    assert not os.path.exists(request_path(home, "d7"))
    assert not os.path.exists(report_path(home, "d7"))
    assert os.path.exists(keeper)
    cleanup(home, "d7")  # second call is a no-op


def test_validate_request_rejects_non_dict():
    with pytest.raises(SpecError):
        validate_request(None)
    with pytest.raises(SpecError):
        validate_request(["spec"])


def test_validate_request_rejects_argv():
    with pytest.raises(SpecError):
        validate_request({"adapter": "synthetic", "params": {}, "effect_key": "e1", "argv": ["x"]})


def test_validate_request_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        validate_request({"adapter": "nope", "params": {}, "effect_key": "e1"})


def test_validate_request_rejects_non_dict_params():
    with pytest.raises(SpecError):
        validate_request({"adapter": "synthetic", "params": [], "effect_key": "e1"})


def test_validate_request_accepts_minimal_valid():
    adapter, params, effect_key = validate_request(
        {"adapter": "synthetic", "params": {}, "effect_key": "eff-1.0:x"})
    assert adapter == "synthetic"
    assert effect_key == "eff-1.0:x"


def test_validate_request_rejects_bad_effect_key():
    with pytest.raises(SpecError):
        validate_request({"adapter": "synthetic", "params": {}, "effect_key": ""})
    with pytest.raises(SpecError):
        validate_request({"adapter": "synthetic", "params": {}, "effect_key": "has space"})
    with pytest.raises(SpecError):
        validate_request({"adapter": "synthetic", "params": {}})
