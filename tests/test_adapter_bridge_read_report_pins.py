"""P9 hardening pins for courier_worker.adapter_bridge (read_report + paths).

Tests only; no behaviour change. Offline: tmp_path filesystem only,
no network, no credentials.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as bridge
from courier_worker.host import SpecError


def _valid_spec(effect_key="run-1.0_ok:abc"):
    return {"adapter": "synthetic", "params": {}, "effect_key": effect_key}


def test_safe_keeps_plain():
    assert bridge._safe("abc-123_.x") == "abc-123_.x"


def test_safe_replaces_unsafe():
    assert bridge._safe("a/b c:d") == "a_b_c_d"


def test_safe_empty_becomes_unnamed():
    assert bridge._safe("") == "unnamed"


def test_safe_unicode_replaced():
    # str.isalnum() is unicode-aware: accented alphanumerics are kept,
    # symbols outside alnum are replaced.
    assert bridge._safe("héllo") == "héllo"
    assert bridge._safe("hi\u2603") == "hi_"


def test_request_path_layout(tmp_path):
    home = str(tmp_path)
    got = bridge.request_path(home, "d1")
    assert got == os.path.join(home, "run", "requests", "d1.json")


def test_report_path_layout(tmp_path):
    home = str(tmp_path)
    got = bridge.report_path(home, "d1")
    assert got == os.path.join(home, "run", "reports", "d1.json")


def test_request_and_report_paths_sanitize(tmp_path):
    home = str(tmp_path)
    assert bridge.request_path(home, "a/b").endswith("a_b.json")
    assert bridge.report_path(home, "a/b").endswith("a_b.json")


def test_validate_request_success_real_synthetic():
    adapter, params, key = bridge.validate_request(_valid_spec())
    assert adapter == "synthetic"
    assert params == {}
    assert key == "run-1.0_ok:abc"


def test_validate_request_success_stubbed(monkeypatch):
    seen = {}

    def fake_validator(params):
        seen["params"] = params
        return params

    monkeypatch.setitem(bridge.ADAPTERS, "synthetic", fake_validator)
    adapter, params, key = bridge.validate_request(
        {"adapter": "synthetic", "params": {"a": 1}, "effect_key": "k1"}
    )
    assert adapter == "synthetic"
    assert seen["params"] == {"a": 1}
    assert key == "k1"


def test_validate_request_rejects_non_dict():
    with pytest.raises(SpecError):
        bridge.validate_request(None)
    with pytest.raises(SpecError):
        bridge.validate_request([])


def test_validate_request_rejects_argv():
    spec = _valid_spec()
    spec["argv"] = ["evil"]
    with pytest.raises(SpecError):
        bridge.validate_request(spec)


def test_validate_request_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        bridge.validate_request(
            {"adapter": "nope", "params": {}, "effect_key": "k1"}
        )


def test_validate_request_rejects_non_dict_params():
    with pytest.raises(SpecError):
        bridge.validate_request(
            {"adapter": "synthetic", "params": [], "effect_key": "k1"}
        )


def test_validate_request_rejects_non_json_params():
    with pytest.raises(SpecError):
        bridge.validate_request(
            {"adapter": "synthetic", "params": {"x": float("nan")}, "effect_key": "k1"}
        )


def test_validate_request_rejects_oversize_params(monkeypatch):
    monkeypatch.setattr(bridge, "MAX_PARAMS_BYTES", 10)
    monkeypatch.setitem(bridge.ADAPTERS, "synthetic", lambda p: p)
    with pytest.raises(SpecError):
        bridge.validate_request(
            {"adapter": "synthetic", "params": {"k": "1234567890abcdef"}, "effect_key": "k1"}
        )


def test_validate_request_rejects_bad_effect_key(monkeypatch):
    monkeypatch.setitem(bridge.ADAPTERS, "synthetic", lambda p: p)
    for bad in (None, "", 123, "has space", "has/slash", "x" * 201):
        with pytest.raises(SpecError):
            bridge.validate_request({"adapter": "synthetic", "params": {}, "effect_key": bad})
    with pytest.raises(SpecError):
        bridge.validate_request({"adapter": "synthetic", "params": {}})


def test_validate_request_rejects_synthetic_params():
    with pytest.raises(SpecError):
        bridge.validate_request(
            {"adapter": "synthetic", "params": {"sleep_s": -1}, "effect_key": "k1"}
        )


def test_runner_argv_shape(tmp_path):
    home = str(tmp_path)
    argv = bridge.runner_argv(home, "d9")
    assert isinstance(argv, tuple) and len(argv) == 3
    assert argv[0] == sys.executable
    assert argv[1].endswith("adapter_runner.py")
    assert argv[2] == bridge.request_path(home, "d9")


def test_read_report_missing_is_none(tmp_path):
    assert bridge.read_report(str(tmp_path), "absent") is None


def test_read_report_malformed_is_none(tmp_path):
    home = str(tmp_path)
    path = bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert bridge.read_report(home, "d1") is None


def test_read_report_rejects_non_dict(tmp_path):
    home = str(tmp_path)
    path = bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([1, 2], fh)
    assert bridge.read_report(home, "d1") is None


def test_read_report_rejects_bad_outcome(tmp_path):
    home = str(tmp_path)
    path = bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "weird", "retryable": False}, fh)
    assert bridge.read_report(home, "d1") is None


def test_read_report_rejects_non_bool_retryable(tmp_path):
    home = str(tmp_path)
    path = bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": "yes"}, fh)
    assert bridge.read_report(home, "d1") is None


def test_read_report_accepts_success_and_failure(tmp_path):
    home = str(tmp_path)
    for outcome in ("success", "failure"):
        path = bridge.report_path(home, outcome)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"outcome": outcome, "retryable": True}, fh)
        got = bridge.read_report(home, outcome)
        assert got is not None and got["outcome"] == outcome and got["retryable"] is True


def test_cleanup_removes_files_and_is_idempotent(tmp_path):
    home = str(tmp_path)
    req = bridge.request_path(home, "d1")
    rep = bridge.report_path(home, "d1")
    os.makedirs(os.path.dirname(req), exist_ok=True)
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    for path in (req, rep):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{}")
    bridge.cleanup(home, "d1")
    assert not os.path.exists(req)
    assert not os.path.exists(rep)
    bridge.cleanup(home, "d1")


def _ns_spec(dispatch_id="d7"):
    return SimpleNamespace(
        adapter="synthetic",
        params={},
        attempt=1,
        task_id="t1",
        dispatch_id=dispatch_id,
        effect_key="k-7",
        artifact_dir="artifacts/d7",
    )


def test_write_request_round_trip(tmp_path):
    home = str(tmp_path)
    spec = _ns_spec()
    path = bridge.write_request(home, spec)
    assert path == bridge.request_path(home, "d7")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["adapter"] == "synthetic"
    assert data["dispatch_id"] == "d7"
    assert data["effect_key"] == "k-7"
    assert data["report"] == bridge.report_path(home, "d7")


def test_write_request_drops_stale_report(tmp_path):
    home = str(tmp_path)
    stale = bridge.report_path(home, "d7")
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    bridge.write_request(home, _ns_spec())
    assert not os.path.exists(stale)


def test_atomic_json_sorted_and_overwrites(tmp_path):
    target = str(tmp_path / "sub" / "data.json")
    bridge._atomic_json(target, {"b": 2, "a": 1})
    with open(target, encoding="utf-8") as fh:
        raw = fh.read()
    assert raw.index('"a"') < raw.index('"b"')
    bridge._atomic_json(target, {"c": 3})
    with open(target, encoding="utf-8") as fh:
        assert json.load(fh) == {"c": 3}


def test_module_constants():
    assert "synthetic" in bridge.ADAPTERS
    assert bridge.REPORT_OUTCOMES == frozenset({"success", "failure"})
    assert bridge.MAX_PARAMS_BYTES == 64 * 1024
    assert bridge.RUNNER_SCRIPT.endswith("adapter_runner.py")
    assert bridge.EFFECT_KEY_RE.match("A1-_.:x")
    assert not bridge.EFFECT_KEY_RE.match("bad key!")
