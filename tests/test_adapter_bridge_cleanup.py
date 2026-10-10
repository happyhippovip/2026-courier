"""P9 hardening for courier_worker.adapter_bridge (cleanup + report edges).

Tests only; no behavior change. Offline: filesystem via tmp_path, no network,
no credentials.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from courier_worker import adapter_bridge
from courier_worker.host import SpecError


def _valid_spec(**overrides):
    base = {"adapter": "synthetic", "params": {}, "effect_key": "eff-1"}
    base.update(overrides)
    return base


# -- _safe + paths -----------------------------------------------------------

def test_safe_keeps_safe_chars():
    assert adapter_bridge._safe("abc-XYZ_019.") == "abc-XYZ_019."


def test_safe_replaces_unsafe_with_underscore():
    cleaned = adapter_bridge._safe("a/b c:d\\e")
    assert "/" not in cleaned and " " not in cleaned and ":" not in cleaned
    assert "\\" not in cleaned


def test_safe_empty_becomes_unnamed():
    assert adapter_bridge._safe("") == "unnamed"


def test_safe_traversal_has_no_separator():
    cleaned = adapter_bridge._safe("../../etc/passwd")
    assert "/" not in cleaned and "\\" not in cleaned


def test_request_and_report_paths_use_safe_dispatch(tmp_path):
    home = str(tmp_path)
    req = adapter_bridge.request_path(home, "a/b")
    rep = adapter_bridge.report_path(home, "a/b")
    assert req.endswith(".json") and rep.endswith(".json")
    assert os_sep_not_in_basename(req) and os_sep_not_in_basename(rep)
    assert "requests" in req and "reports" in rep


def os_sep_not_in_basename(path: str) -> bool:
    name = Path(path).name
    return "/" not in name and "\\" not in name


def test_runner_argv_shape(tmp_path):
    home = str(tmp_path)
    argv = adapter_bridge.runner_argv(home, "d1")
    assert len(argv) == 3
    assert argv[0] == sys.executable
    assert argv[1].endswith("adapter_runner.py")
    assert argv[2] == adapter_bridge.request_path(home, "d1")


def test_runner_script_points_at_existing_file():
    assert Path(adapter_bridge.RUNNER_SCRIPT).name == "adapter_runner.py"
    assert Path(adapter_bridge.RUNNER_SCRIPT).exists()


# -- validate_request fail-closed --------------------------------------------

def test_validate_rejects_non_dict():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(None)
    with pytest.raises(SpecError):
        adapter_bridge.validate_request([])


def test_validate_rejects_supplied_argv():
    spec = _valid_spec()
    spec["argv"] = ["anything"]
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(spec)


def test_validate_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(adapter="nope"))
    with pytest.raises(SpecError):
        adapter_bridge.validate_request({"params": {}, "effect_key": "a"})


def test_validate_rejects_bad_params_shape():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(params=[]))
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(params={"sleep_s": -1}))
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(params={"write": "../evil"}))


def test_validate_rejects_non_json_params():
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(params={"x": float("nan")}))
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(params={"x": {1, 2}}))


def test_validate_rejects_oversize_params():
    big = "x" * (adapter_bridge.MAX_PARAMS_BYTES + 1)
    with pytest.raises(SpecError):
        adapter_bridge.validate_request(_valid_spec(params={"content": big}))


def test_validate_rejects_bad_effect_key():
    for bad in ["", "a/b", "a b", "x" * 201, None, 123]:
        with pytest.raises(SpecError):
            adapter_bridge.validate_request(_valid_spec(effect_key=bad))


def test_validate_accepts_minimal_and_explicit():
    adapter, params, key = adapter_bridge.validate_request(_valid_spec())
    assert adapter == "synthetic" and key == "eff-1" and isinstance(params, dict)
    adapter2, _, _ = adapter_bridge.validate_request(
        _valid_spec(params={"write": "out.txt", "content": "hi"}, effect_key="A1-_.:9"))
    assert adapter2 == "synthetic"


def test_effect_key_bounds():
    assert adapter_bridge.EFFECT_KEY_RE.match("a")
    assert adapter_bridge.EFFECT_KEY_RE.match("A1-_.:z" * 10)
    assert not adapter_bridge.EFFECT_KEY_RE.match("")
    assert not adapter_bridge.EFFECT_KEY_RE.match("a/b")
    assert not adapter_bridge.EFFECT_KEY_RE.match("x" * 201)
    assert adapter_bridge.MAX_PARAMS_BYTES == 64 * 1024


# -- read_report edges --------------------------------------------------------

def _write_raw(path: str, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def test_read_report_missing_is_none(tmp_path):
    assert adapter_bridge.read_report(str(tmp_path), "nope") is None


def test_read_report_malformed_is_none(tmp_path):
    home = str(tmp_path)
    _write_raw(adapter_bridge.report_path(home, "d1"), "{not json")
    assert adapter_bridge.read_report(home, "d1") is None
    _write_raw(adapter_bridge.report_path(home, "d2"), json.dumps(["list"]))
    assert adapter_bridge.read_report(home, "d2") is None
    _write_raw(adapter_bridge.report_path(home, "d3"), json.dumps({"no": "outcome"}))
    assert adapter_bridge.read_report(home, "d3") is None
    _write_raw(adapter_bridge.report_path(home, "d4"), json.dumps({"outcome": "weird"}))
    assert adapter_bridge.read_report(home, "d4") is None


def test_read_report_rejects_non_bool_retryable(tmp_path):
    home = str(tmp_path)
    for bad in ["yes", 1, 0, None, []]:
        _write_raw(adapter_bridge.report_path(home, "d5"), json.dumps({"outcome": "success", "retryable": bad}))
        assert adapter_bridge.read_report(home, "d5") is None


def test_read_report_accepts_valid_success_and_failure(tmp_path):
    home = str(tmp_path)
    _write_raw(adapter_bridge.report_path(home, "ok"), json.dumps({"outcome": "success"}))
    got = adapter_bridge.read_report(home, "ok")
    assert got is not None and got["outcome"] == "success"
    _write_raw(adapter_bridge.report_path(home, "bad"),
               json.dumps({"outcome": "failure", "retryable": True, "reason": "x"}))
    got2 = adapter_bridge.read_report(home, "bad")
    assert got2 is not None and got2["outcome"] == "failure" and got2["retryable"] is True


# -- write_request + cleanup ---------------------------------------------------

class _Spec:
    def __init__(self, **kw):
        self.task_id = kw.get("task_id", "t1")
        self.attempt = kw.get("attempt", 1)
        self.dispatch_id = kw.get("dispatch_id", "d1")
        self.adapter = kw.get("adapter", "synthetic")
        self.params = kw.get("params", {})
        self.effect_key = kw.get("effect_key", "eff-1")
        self.artifact_dir = kw.get("artifact_dir", "artifacts/d1")


def test_write_request_creates_dirs_and_drops_stale_report(tmp_path):
    home = str(tmp_path)
    spec = _Spec(dispatch_id="d9")
    stale = adapter_bridge.report_path(home, "d9")
    _write_raw(stale, json.dumps({"outcome": "success"}))
    path = adapter_bridge.write_request(home, spec)
    assert path == adapter_bridge.request_path(home, "d9")
    assert Path(path).exists()
    assert adapter_bridge.read_report(home, "d9") is None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["adapter"] == "synthetic" and payload["dispatch_id"] == "d9"
    assert payload["report"] == adapter_bridge.report_path(home, "d9")


def test_cleanup_is_idempotent(tmp_path):
    home = str(tmp_path)
    spec = _Spec(dispatch_id="dx")
    adapter_bridge.write_request(home, spec)
    _write_raw(adapter_bridge.report_path(home, "dx"), json.dumps({"outcome": "success"}))
    adapter_bridge.cleanup(home, "dx")
    assert not Path(adapter_bridge.request_path(home, "dx")).exists()
    assert not Path(adapter_bridge.report_path(home, "dx")).exists()
    # second cleanup must not raise
    adapter_bridge.cleanup(home, "dx")
    adapter_bridge.cleanup(home, "missing-entirely")
