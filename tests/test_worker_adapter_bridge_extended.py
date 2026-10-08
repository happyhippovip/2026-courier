import json
import os
import pytest
from pathlib import Path
from courier_worker.adapter_bridge import (
    MAX_PARAMS_BYTES,
    cleanup,
    read_report,
    report_path,
    request_path,
    runner_argv,
    validate_request,
    write_request,
)
from courier_worker.host import SpecError

def test_validate_request_type_guards():
    with pytest.raises(SpecError, match="claim carries no spec object"):
        validate_request("not-a-dict")
    with pytest.raises(SpecError, match="claim spec must not carry argv"):
        validate_request({"argv": ["echo", "hi"]})
    with pytest.raises(SpecError, match="adapter 'unknown' is not allowlisted"):
        validate_request({"adapter": "unknown", "params": {}})
    with pytest.raises(SpecError, match="claim spec params must be an object"):
        validate_request({"adapter": "synthetic", "params": "not-dict"})

def test_validate_request_params_bounds():
    huge_params = {"data": "x" * (MAX_PARAMS_BYTES + 10)}
    with pytest.raises(SpecError, match="claim spec params exceed the size bound"):
        validate_request({"adapter": "synthetic", "params": huge_params})

def test_validate_request_effect_key_validation(monkeypatch):
    # Mock synthetic validator in ADAPTERS so we test effect_key parsing cleanly
    from courier_worker import adapter_bridge
    monkeypatch.setitem(adapter_bridge.ADAPTERS, "mock_adapter", lambda p: p)

    valid_spec = {
        "adapter": "mock_adapter",
        "params": {"key": "val"},
        "effect_key": "effect-valid-123_.:",
    }
    adapter, params, eff = validate_request(valid_spec)
    assert adapter == "mock_adapter"
    assert eff == "effect-valid-123_.:"

    # Malformed effect_keys
    for bad_key in ["", "has spaces", "bad$char", "x" * 201, 123, None]:
        bad_spec = {
            "adapter": "mock_adapter",
            "params": {"key": "val"},
            "effect_key": bad_key,
        }
        with pytest.raises(SpecError, match="effect_key is missing or malformed"):
            validate_request(bad_spec)

def test_paths_and_runner_argv(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-test/invalid chars@1"
    req_p = request_path(home, dispatch_id)
    rep_p = report_path(home, dispatch_id)
    
    assert "dsp-test_invalid_chars_1.json" in req_p
    assert "dsp-test_invalid_chars_1.json" in rep_p
    
    argv = runner_argv(home, dispatch_id)
    assert len(argv) == 3
    assert argv[2] == req_p

def test_write_request_unlinks_stale_report(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-stale"
    rep_p = Path(report_path(home, dispatch_id))
    rep_p.parent.mkdir(parents=True, exist_ok=True)
    rep_p.write_text('{"outcome": "success"}')
    assert rep_p.exists()

    class MockSpec:
        adapter = "mock"
        params = {"a": 1}
        attempt = 1
        task_id = "t-1"
        dispatch_id = "dsp-stale"
        effect_key = "eff-1"
        artifact_dir = "/tmp"

    req_p = write_request(home, MockSpec)
    assert Path(req_p).exists()
    # Stale report must have been unlinked
    assert not rep_p.exists()

def test_read_report_validations(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-rep"
    rep_p = Path(report_path(home, dispatch_id))
    rep_p.parent.mkdir(parents=True, exist_ok=True)

    # Missing file returns None
    assert read_report(home, dispatch_id) is None

    # Invalid JSON returns None
    rep_p.write_text("{bad json")
    assert read_report(home, dispatch_id) is None

    # Invalid outcome returns None
    rep_p.write_text(json.dumps({"outcome": "invalid_status", "retryable": False}))
    assert read_report(home, dispatch_id) is None

    # Non-boolean retryable returns None
    rep_p.write_text(json.dumps({"outcome": "success", "retryable": "not-bool"}))
    assert read_report(home, dispatch_id) is None

    # Valid report returns dict
    rep_p.write_text(json.dumps({"outcome": "success", "retryable": False, "data": 42}))
    report = read_report(home, dispatch_id)
    assert report is not None
    assert report["outcome"] == "success"
    assert report["data"] == 42

def test_cleanup_removes_both(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-clean"
    req_p = Path(request_path(home, dispatch_id))
    rep_p = Path(report_path(home, dispatch_id))
    req_p.parent.mkdir(parents=True, exist_ok=True)
    rep_p.parent.mkdir(parents=True, exist_ok=True)
    req_p.write_text("{}")
    rep_p.write_text("{}")

    assert req_p.exists() and rep_p.exists()
    cleanup(home, dispatch_id)
    assert not req_p.exists() and not rep_p.exists()

    # Re-running cleanup does not raise
    cleanup(home, dispatch_id)
