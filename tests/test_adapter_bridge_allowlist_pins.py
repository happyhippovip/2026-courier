"""P9 allowlist pins for courier_worker.adapter_bridge (tests only).

Offline hardening for the allowlisted claim-spec gate: the worker never runs
a supplied command, only a closed adapter set with validated params and a
well-formed effect key. No network, no subprocess, no behavior change.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as ab
from courier_worker.host import SpecError


def _valid_spec(**overrides):
    base = {
        "adapter": "synthetic",
        "params": {"sleep_s": 0, "write": "out.txt", "content": "hi"},
        "effect_key": "order-123_abc:1",
    }
    base.update(overrides)
    return base


def test_adapters_closed_allows_only_synthetic():
    assert set(ab.ADAPTERS.keys()) == {"synthetic"}


def test_validate_request_accepts_minimal_valid():
    adapter, params, effect_key = ab.validate_request(_valid_spec())
    assert adapter == "synthetic"
    assert params["write"] == "out.txt"
    assert effect_key == "order-123_abc:1"


def test_validate_request_rejects_non_dict_spec():
    for bad in (None, [], "x", 42):
        with pytest.raises(SpecError):
            ab.validate_request(bad)


def test_validate_request_rejects_supplied_argv():
    spec = _valid_spec(argv=["/bin/sh"])
    with pytest.raises(SpecError):
        ab.validate_request(spec)


def test_validate_request_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(adapter="shell"))
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(adapter="../synthetic"))


def test_validate_request_rejects_non_object_params():
    for bad in (None, [], "x", 42):
        with pytest.raises(SpecError):
            ab.validate_request(_valid_spec(params=bad))


def test_validate_request_rejects_non_json_params():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"x": float("nan")}))
    with pytest.raises(SpecError):
        # set is not plain JSON
        ab.validate_request(_valid_spec(params={"x": {1, 2}}))


def test_validate_request_rejects_oversized_params():
    big = "y" * (ab.MAX_PARAMS_BYTES + 1)
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"write": "out.txt", "content": big}))


def test_validate_request_rejects_bad_synthetic_params():
    with pytest.raises(SpecError):
        ab.validate_request(_valid_spec(params={"write": "../evil.txt"}))


def test_validate_request_rejects_bad_effect_key():
    for bad in (None, "", 42, "has space", "x" * 201, "bad/slash!"):
        with pytest.raises(SpecError):
            ab.validate_request(_valid_spec(effect_key=bad))


def test_safe_sanitizes_and_empty_names_unnamed():
    assert ab._safe("abc-123_.x") == "abc-123_.x"
    assert ab._safe("a/b\\c:d") == "a_b_c_d"
    assert ab._safe("") == "unnamed"


def test_request_and_report_paths_stay_under_home(tmp_path):
    home = str(tmp_path)
    req = ab.request_path(home, "d/1")
    rep = ab.report_path(home, "d/1")
    assert req.startswith(os.path.join(home, "run", "requests") + os.sep)
    assert rep.startswith(os.path.join(home, "run", "reports") + os.sep)
    assert req.endswith(".json") and rep.endswith(".json")
    # traversal in dispatch id cannot escape the owned dirs
    assert ".." not in os.path.basename(req)
    assert ".." not in os.path.basename(rep)


def test_runner_argv_uses_trusted_runner_only(tmp_path):
    home = str(tmp_path)
    argv = ab.runner_argv(home, "dispatch-1")
    assert argv[0] == sys.executable
    assert argv[1] == ab.RUNNER_SCRIPT
    assert os.path.isabs(argv[1])
    assert os.path.basename(argv[1]) == "adapter_runner.py"
    assert argv[2] == ab.request_path(home, "dispatch-1")
    # no spec-controlled executable or fragment leaks into argv
    assert len(argv) == 3


def _ns_spec(home, dispatch_id="dispatch-1"):
    return SimpleNamespace(
        adapter="synthetic",
        params={"sleep_s": 0, "write": "out.txt", "content": "hi"},
        attempt=1,
        task_id="task-1",
        dispatch_id=dispatch_id,
        effect_key="ek-1",
        artifact_dir=os.path.join(home, "artifacts", dispatch_id),
    )


def test_write_request_roundtrip_and_clears_stale_report(tmp_path):
    home = str(tmp_path)
    spec = _ns_spec(home)
    # plant a stale report that must be removed before the runner starts
    stale = ab.report_path(home, spec.dispatch_id)
    os.makedirs(os.path.dirname(stale), exist_ok=True)
    with open(stale, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    path = ab.write_request(home, spec)
    assert path == ab.request_path(home, spec.dispatch_id)
    assert not os.path.exists(stale)
    with open(path, encoding="utf-8") as fh:
        body = json.load(fh)
    assert body["adapter"] == "synthetic"
    assert body["dispatch_id"] == spec.dispatch_id
    assert body["effect_key"] == "ek-1"
    assert body["report"] == ab.report_path(home, spec.dispatch_id)


def test_read_report_edges(tmp_path):
    home = str(tmp_path)
    assert ab.read_report(home, "missing") is None
    # malformed JSON
    bad_path = ab.report_path(home, "bad")
    os.makedirs(os.path.dirname(bad_path), exist_ok=True)
    with open(bad_path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert ab.read_report(home, "bad") is None
    # non-dict / bad outcome / non-bool retryable
    for name, payload in (
        ("nondict", [1, 2]),
        ("badoutcome", {"outcome": "maybe", "retryable": False}),
        ("badretry", {"outcome": "success", "retryable": "yes"}),
    ):
        p = ab.report_path(home, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        assert ab.read_report(home, name) is None
    # valid report passes through
    p = ab.report_path(home, "good")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "reason": "ok", "retryable": False}, fh)
    report = ab.read_report(home, "good")
    assert report is not None and report["outcome"] == "success"


def test_cleanup_removes_both_and_is_idempotent(tmp_path):
    home = str(tmp_path)
    spec = _ns_spec(home)
    ab.write_request(home, spec)
    p = ab.report_path(home, spec.dispatch_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "failure", "retryable": True}, fh)
    ab.cleanup(home, spec.dispatch_id)
    assert not os.path.exists(ab.request_path(home, spec.dispatch_id))
    assert not os.path.exists(p)
    ab.cleanup(home, spec.dispatch_id)  # missing files are fine
