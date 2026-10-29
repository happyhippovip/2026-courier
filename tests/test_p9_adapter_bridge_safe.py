"""P9 hardening for courier_worker.adapter_bridge (safe paths + report edges).

Tests only, no behavior change. Offline, no network, no credentials.
Covers pure helpers that have no tracked dedicated test file on base:
_safe, request_path, report_path, runner_argv, read_report, cleanup,
and the fail-closed edges of validate_request.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from courier_worker import adapter_bridge
from courier_worker.host import SpecError


def _write_report_file(home: Path, dispatch: str, content: str) -> Path:
    path = Path(adapter_bridge.report_path(str(home), dispatch))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_safe_empty_becomes_unnamed():
    assert adapter_bridge._safe("") == "unnamed"


def test_safe_preserves_allowed_chars():
    assert adapter_bridge._safe("abc-123_.X") == "abc-123_.X"


def test_safe_replaces_separators():
    cleaned = adapter_bridge._safe("../etc/passwd")
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert cleaned != ""
    # dots and alnum survive, slashes become underscores
    assert cleaned == ".._etc_passwd"


def test_safe_never_emits_path_separator():
    for raw in ["a/b", "a\\b", "a:b", "a b", "a*b?a", ""]:
        cleaned = adapter_bridge._safe(raw)
        assert os.sep not in cleaned
        assert "/" not in cleaned
        assert cleaned != ""


def test_request_path_layout_and_sanitized(tmp_path):
    home = str(tmp_path)
    path = adapter_bridge.request_path(home, "d1")
    assert path == os.path.join(home, "run", "requests", "d1.json")
    tricky = adapter_bridge.request_path(home, "../evil")
    parent = os.path.dirname(tricky)
    assert parent == os.path.join(home, "run", "requests")
    assert os.path.basename(tricky) == ".._evil.json"


def test_report_path_layout(tmp_path):
    home = str(tmp_path)
    path = adapter_bridge.report_path(home, "d1")
    assert path == os.path.join(home, "run", "reports", "d1.json")


def test_request_path_empty_dispatch(tmp_path):
    path = adapter_bridge.request_path(str(tmp_path), "")
    assert os.path.basename(path) == "unnamed.json"


def test_runner_argv_shape(tmp_path):
    home = str(tmp_path)
    argv = adapter_bridge.runner_argv(home, "d9")
    assert isinstance(argv, tuple) and len(argv) == 3
    assert argv[0] == sys.executable
    assert os.path.isabs(argv[1])
    assert os.path.basename(argv[1]) == "adapter_runner.py"
    assert argv[2] == adapter_bridge.request_path(home, "d9")


def test_read_report_missing_is_none(tmp_path):
    assert adapter_bridge.read_report(str(tmp_path), "nope") is None


def test_read_report_malformed_json_is_none(tmp_path):
    _write_report_file(tmp_path, "d1", "{not json")
    assert adapter_bridge.read_report(str(tmp_path), "d1") is None


def test_read_report_non_dict_is_none(tmp_path):
    _write_report_file(tmp_path, "d1", json.dumps(["x"]))
    assert adapter_bridge.read_report(str(tmp_path), "d1") is None


def test_read_report_bad_outcome_is_none(tmp_path):
    _write_report_file(tmp_path, "d1", json.dumps({"outcome": "weird"}))
    assert adapter_bridge.read_report(str(tmp_path), "d1") is None


def test_read_report_non_bool_retryable_is_none(tmp_path):
    _write_report_file(tmp_path, "d1", json.dumps({"outcome": "success", "retryable": "yes"}))
    assert adapter_bridge.read_report(str(tmp_path), "d1") is None


def test_read_report_valid_success(tmp_path):
    _write_report_file(tmp_path, "d1", json.dumps({"outcome": "success"}))
    report = adapter_bridge.read_report(str(tmp_path), "d1")
    assert isinstance(report, dict)
    assert report["outcome"] == "success"


def test_read_report_valid_failure_retryable(tmp_path):
    payload = {"outcome": "failure", "retryable": True, "reason": "boom"}
    _write_report_file(tmp_path, "d1", json.dumps(payload))
    report = adapter_bridge.read_report(str(tmp_path), "d1")
    assert report is not None
    assert report["outcome"] == "failure"
    assert report["retryable"] is True


def test_cleanup_removes_both_files(tmp_path):
    home = str(tmp_path)
    req = Path(adapter_bridge.request_path(home, "d1"))
    rep = Path(adapter_bridge.report_path(home, "d1"))
    req.parent.mkdir(parents=True, exist_ok=True)
    rep.parent.mkdir(parents=True, exist_ok=True)
    req.write_text("{}", encoding="utf-8")
    rep.write_text(json.dumps({"outcome": "success"}), encoding="utf-8")
    adapter_bridge.cleanup(home, "d1")
    assert not req.exists()
    assert not rep.exists()


def test_cleanup_missing_is_idempotent(tmp_path):
    adapter_bridge.cleanup(str(tmp_path), "absent")
    adapter_bridge.cleanup(str(tmp_path), "absent")


def test_cleanup_leaves_siblings(tmp_path):
    home = str(tmp_path)
    sibling = Path(adapter_bridge.request_path(home, "other"))
    sibling.parent.mkdir(parents=True, exist_ok=True)
    sibling.write_text("{}", encoding="utf-8")
    adapter_bridge.cleanup(home, "d1")
    assert sibling.exists()


def test_validate_request_rejects_non_dict():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(None)
    with pytest.raises(SpecError):
        adapter_bridge.validate_request([])


def test_validate_request_rejects_argv():
    spec = {"adapter": "synthetic", "params": {}, "effect_key": "a1", "argv": ["x"]}
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(spec)


def test_validate_request_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request({"adapter": "nope", "params": {}, "effect_key": "a1"})


def test_validate_request_rejects_bad_params_object():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request({"adapter": "synthetic", "params": [], "effect_key": "a1"})


def test_validate_request_rejects_non_json_params():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request({"adapter": "synthetic", "params": {"w": {"a", "b"}}, "effect_key": "a1"})
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(
            {"adapter": "synthetic", "params": {"sleep_s": float("nan")}, "effect_key": "a1"}
        )


def test_validate_request_rejects_oversized_params():
    big = {"content": "x" * 70000}
    with pytest.raises(SpecError):
        adapter_bridge.validate_request({"adapter": "synthetic", "params": big, "effect_key": "a1"})


def test_validate_request_rejects_bad_synthetic_params():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(
            {"adapter": "synthetic", "params": {"sleep_s": -1}, "effect_key": "a1"}
        )


@pytest.mark.parametrize("bad", ["", "has space", "has/slash", "x" * 201, None, 123])
def test_validate_request_rejects_bad_effect_key(bad):
    with pytest.raises(SpecError):
        adapter_bridge.validate_request({"adapter": "synthetic", "params": {}, "effect_key": bad})


def test_validate_request_accepts_minimal_valid():
    adapter, params, key = adapter_bridge.validate_request(
        {"adapter": "synthetic", "params": {}, "effect_key": "key-1.2:3_4"}
    )
    assert adapter == "synthetic"
    assert isinstance(params, dict)
    assert key == "key-1.2:3_4"
