"""P9 hardening for courier_worker.adapter_bridge (validate + request/report IO).

Tests only; no behavior change. Offline, no network, no credentials.
Covers fail-closed validate_request branches, path helpers, runner argv,
and the write_request / read_report / cleanup round-trip with tmp dirs.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from courier_worker import adapter_bridge as B
from courier_worker.host import ExecutionSpec, SpecError


def _valid_spec_dict(effect_key: str = "eff-1", params: dict | None = None) -> dict:
    return {
        "adapter": "synthetic",
        "params": {} if params is None else params,
        "effect_key": effect_key,
    }


def _spec_obj(tmp_path, dispatch_id: str = "dsp-1"):
    home = str(tmp_path)
    return ExecutionSpec(
        task_id="t-1",
        attempt=1,
        dispatch_id=dispatch_id,
        worker_id="w-1",
        result_id="r-dsp-1",
        argv=(sys.executable, B.RUNNER_SCRIPT, B.request_path(home, dispatch_id)),
        timeout_s=10.0,
        lease_ttl_s=60.0,
        artifact_dir=os.path.join(home, "artifacts", dispatch_id),
        heartbeat_s=1.0,
        adapter="synthetic",
        params={},
        effect_key="eff-1",
    )


# -- _safe / paths --------------------------------------------------------


def test_safe_keeps_simple_names():
    assert B._safe("abc-123_.x") == "abc-123_.x"


def test_safe_replaces_separators():
    assert B._safe("a/b\\c:d") == "a_b_c_d"


def test_safe_empty_gives_unnamed():
    assert B._safe("") == "unnamed"


def test_request_and_report_paths_scoped(tmp_path):
    home = str(tmp_path)
    req = B.request_path(home, "dsp-7")
    rep = B.report_path(home, "dsp-7")
    assert req == os.path.join(home, "run", "requests", "dsp-7.json")
    assert rep == os.path.join(home, "run", "reports", "dsp-7.json")


def test_paths_sanitize_dispatch_id(tmp_path):
    home = str(tmp_path)
    req = B.request_path(home, "../evil")
    assert os.path.basename(req) == ".._evil.json"
    assert "/" not in os.path.basename(req)
    assert req.endswith(".json")
    assert os.path.dirname(req) == os.path.join(home, "run", "requests")


def test_runner_argv_uses_own_runner(tmp_path):
    home = str(tmp_path)
    argv = B.runner_argv(home, "dsp-7")
    assert argv[0] == sys.executable
    assert argv[1] == B.RUNNER_SCRIPT
    assert argv[2] == B.request_path(home, "dsp-7")
    assert B.RUNNER_SCRIPT.endswith("adapter_runner.py")


def test_adapters_closed_and_runner_script_exists():
    assert set(B.ADAPTERS.keys()) == {"synthetic"}
    assert os.path.isfile(B.RUNNER_SCRIPT)


# -- validate_request fail-closed ------------------------------------------


def test_validate_rejects_non_dict():
    with pytest.raises(SpecError):
        B.validate_request(None)
    with pytest.raises(SpecError):
        B.validate_request(["adapter"])


def test_validate_rejects_argv_carrying_spec():
    with pytest.raises(SpecError):
        B.validate_request({**_valid_spec_dict(), "argv": ["echo"]})


def test_validate_rejects_unknown_adapter():
    with pytest.raises(SpecError):
        B.validate_request({"adapter": "nope", "params": {}, "effect_key": "eff-1"})
    with pytest.raises(SpecError):
        B.validate_request({"params": {}, "effect_key": "eff-1"})
    with pytest.raises(SpecError):
        B.validate_request({"adapter": 123, "params": {}, "effect_key": "eff-1"})


def test_validate_rejects_non_dict_params():
    with pytest.raises(SpecError):
        B.validate_request({"adapter": "synthetic", "params": [], "effect_key": "eff-1"})
    with pytest.raises(SpecError):
        B.validate_request({"adapter": "synthetic", "effect_key": "eff-1"})


def test_validate_rejects_non_json_params():
    with pytest.raises(SpecError):
        B.validate_request({"adapter": "synthetic", "params": {"x": float("nan")}, "effect_key": "eff-1"})
    with pytest.raises(SpecError):
        B.validate_request({"adapter": "synthetic", "params": {"x": object()}, "effect_key": "eff-1"})


def test_validate_rejects_oversize_params():
    big = {"content": "x" * (B.MAX_PARAMS_BYTES + 1)}
    with pytest.raises(SpecError):
        B.validate_request({"adapter": "synthetic", "params": big, "effect_key": "eff-1"})


def test_validate_rejects_bad_synthetic_params():
    with pytest.raises(SpecError):
        B.validate_request(_valid_spec_dict(params={"sleep_s": -1}))
    with pytest.raises(SpecError):
        B.validate_request(_valid_spec_dict(params={"write": "../evil"}))


def test_validate_rejects_bad_effect_key():
    for bad in (None, "", 123, "has space", "x" * 201, "semi;colon-ok?"):
        # note: ':' '.' '-' '_' are allowed; ';' '?' ' ' are not
        if bad == "semi;colon-ok?":
            with pytest.raises(SpecError):
                B.validate_request(_valid_spec_dict(effect_key=bad))
        elif not isinstance(bad, str) or not B.EFFECT_KEY_RE.match(bad or ""):
            with pytest.raises(SpecError):
                B.validate_request(_valid_spec_dict(effect_key=bad))


def test_validate_accepts_dotted_effect_key():
    adapter, params, effect_key = B.validate_request(_valid_spec_dict(effect_key="a.b:c-d_e"))
    assert (adapter, effect_key) == ("synthetic", "a.b:c-d_e")
    assert isinstance(params, dict)


def test_validate_accepts_defaults():
    adapter, params, effect_key = B.validate_request(_valid_spec_dict())
    assert adapter == "synthetic"
    assert effect_key == "eff-1"


def test_validate_accepts_explicit_params():
    adapter, params, effect_key = B.validate_request(
        _valid_spec_dict(params={"content": "hi", "write": "out.txt"})
    )
    assert adapter == "synthetic"
    assert params["content"] == "hi"


# -- write_request / read_report / cleanup ----------------------------------


def test_write_request_persists_expected_keys(tmp_path):
    spec = _spec_obj(tmp_path)
    path = B.write_request(str(tmp_path), spec)
    assert path == B.request_path(str(tmp_path), spec.dispatch_id)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["adapter"] == "synthetic"
    assert data["dispatch_id"] == spec.dispatch_id
    assert data["task_id"] == spec.task_id
    assert data["attempt"] == spec.attempt
    assert data["effect_key"] == spec.effect_key
    assert data["workdir"] == spec.artifact_dir
    assert data["report"] == B.report_path(str(tmp_path), spec.dispatch_id)


def test_write_request_drops_stale_report(tmp_path):
    home = str(tmp_path)
    spec = _spec_obj(tmp_path)
    rep = B.report_path(home, spec.dispatch_id)
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    B.write_request(home, spec)
    assert not os.path.exists(rep)


def test_read_report_none_when_absent(tmp_path):
    assert B.read_report(str(tmp_path), "missing") is None


def test_read_report_none_when_malformed(tmp_path):
    home = str(tmp_path)
    rep = B.report_path(home, "dsp-x")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert B.read_report(home, "dsp-x") is None


def test_read_report_none_when_bad_shape(tmp_path):
    home = str(tmp_path)
    rep = B.report_path(home, "dsp-x")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    for bad in (
        {"outcome": "weird", "retryable": False},
        {"outcome": "success", "retryable": "yes"},
        ["success"],
    ):
        with open(rep, "w", encoding="utf-8") as fh:
            json.dump(bad, fh)
        assert B.read_report(home, "dsp-x") is None


def test_read_report_returns_valid(tmp_path):
    home = str(tmp_path)
    rep = B.report_path(home, "dsp-x")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "failure", "reason": "boom", "retryable": True}, fh)
    report = B.read_report(home, "dsp-x")
    assert report is not None
    assert report["outcome"] == "failure"
    assert report["retryable"] is True


def test_cleanup_removes_both_and_idempotent(tmp_path):
    home = str(tmp_path)
    spec = _spec_obj(tmp_path, dispatch_id="dsp-clean")
    req = B.write_request(home, spec)
    rep = B.report_path(home, spec.dispatch_id)
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    with open(rep, "w", encoding="utf-8") as fh:
        json.dump({"outcome": "success", "retryable": False}, fh)
    B.cleanup(home, spec.dispatch_id)
    assert not os.path.exists(req)
    assert not os.path.exists(rep)
    B.cleanup(home, spec.dispatch_id)  # idempotent, no raise
    B.cleanup(home, "never-created")  # missing files are fine
