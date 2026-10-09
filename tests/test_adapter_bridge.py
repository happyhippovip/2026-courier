"""Dedicated unit tests for courier_worker.adapter_bridge (lane L4 test hardening).

Validates allowlisted adapter specification, parameter bounds, effect keys,
path generation, atomic JSON serialization, report parsing, and cleanup.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from courier_worker import adapter_bridge
from courier_worker.host import SpecError


def test_constants():
    assert adapter_bridge.MAX_PARAMS_BYTES == 64 * 1024
    assert adapter_bridge.REPORT_OUTCOMES == frozenset({"success", "failure"})
    assert "synthetic" in adapter_bridge.ADAPTERS
    assert callable(adapter_bridge.ADAPTERS["synthetic"])
    assert os.path.isfile(adapter_bridge.RUNNER_SCRIPT)
    assert adapter_bridge.RUNNER_SCRIPT.endswith("adapter_runner.py")


def test_effect_key_regex():
    pattern = adapter_bridge.EFFECT_KEY_RE
    assert pattern.match("valid-key_123.test:colons")
    assert pattern.match("a" * 200)
    assert not pattern.match("")
    assert not pattern.match("a" * 201)
    assert not pattern.match("has space")
    assert not pattern.match("has/slash")
    assert not pattern.match("has$special#chars")


def test_safe_dispatch_id():
    safe = adapter_bridge._safe
    assert safe("disp-123_abc.0") == "disp-123_abc.0"
    assert safe("") == "unnamed"
    assert safe("../../../etc/passwd") == ".._.._.._etc_passwd"
    assert safe("hello world:test/foo") == "hello_world_test_foo"
    assert safe("!@#$%^&*()") == "__________"


def test_request_and_report_paths(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dispatch-42"
    req = adapter_bridge.request_path(home, dispatch_id)
    rep = adapter_bridge.report_path(home, dispatch_id)

    assert req == os.path.join(home, "run", "requests", "dispatch-42.json")
    assert rep == os.path.join(home, "run", "reports", "dispatch-42.json")

    # Unsafe characters are sanitized
    req_unsafe = adapter_bridge.request_path(home, "sub/dir:id")
    assert req_unsafe == os.path.join(home, "run", "requests", "sub_dir_id.json")


def test_runner_argv(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dispatch-99"
    argv = adapter_bridge.runner_argv(home, dispatch_id)

    assert isinstance(argv, tuple)
    assert len(argv) == 3
    assert argv[0] == sys.executable
    assert argv[1] == adapter_bridge.RUNNER_SCRIPT
    assert argv[2] == adapter_bridge.request_path(home, dispatch_id)


def test_validate_request_success():
    spec = {
        "adapter": "synthetic",
        "params": {"write": "out.txt", "content": "hello world"},
        "effect_key": "effect-key-01",
    }
    adapter, params, effect_key = adapter_bridge.validate_request(spec)
    assert adapter == "synthetic"
    assert params == {"write": "out.txt", "content": "hello world"}
    assert effect_key == "effect-key-01"


def test_validate_request_not_dict():
    for invalid in [None, "string", 123, [1, 2], True]:
        with pytest.raises(SpecError, match="claim carries no spec object"):
            adapter_bridge.validate_request(invalid)


def test_validate_request_rejects_argv():
    spec = {
        "adapter": "synthetic",
        "params": {},
        "effect_key": "k",
        "argv": ["python", "-c", "print(1)"],
    }
    with pytest.raises(SpecError, match="claim spec must not carry argv"):
        adapter_bridge.validate_request(spec)


def test_validate_request_adapter_allowlist():
    for bad_adapter in [None, 123, "", "unknown", "shell", "bash", "python"]:
        spec = {"adapter": bad_adapter, "params": {}, "effect_key": "k"}
        with pytest.raises(SpecError, match="is not allowlisted on this worker"):
            adapter_bridge.validate_request(spec)


def test_validate_request_params_type():
    for bad_params in [None, "string", 123, [1, 2], True]:
        spec = {"adapter": "synthetic", "params": bad_params, "effect_key": "k"}
        with pytest.raises(SpecError, match="claim spec params must be an object"):
            adapter_bridge.validate_request(spec)


def test_validate_request_params_not_plain_json():
    # NaN and Infinity are not valid standard JSON
    spec_nan = {"adapter": "synthetic", "params": {"val": float("nan")}, "effect_key": "k"}
    with pytest.raises(SpecError, match="claim spec params are not plain JSON"):
        adapter_bridge.validate_request(spec_nan)

    spec_inf = {"adapter": "synthetic", "params": {"val": float("inf")}, "effect_key": "k"}
    with pytest.raises(SpecError, match="claim spec params are not plain JSON"):
        adapter_bridge.validate_request(spec_inf)


def test_validate_request_params_size_bound():
    large_params = {"big": "x" * (65 * 1024)}
    spec = {"adapter": "synthetic", "params": large_params, "effect_key": "k"}
    with pytest.raises(SpecError, match="claim spec params exceed the size bound"):
        adapter_bridge.validate_request(spec)


def test_validate_request_synthetic_rejected():
    # Invalid synthetic params (e.g. negative sleep_s or invalid path)
    spec_neg_sleep = {
        "adapter": "synthetic",
        "params": {"sleep_s": -5},
        "effect_key": "k",
    }
    with pytest.raises(SpecError, match="synthetic params rejected: sleep_s must be a non-negative number"):
        adapter_bridge.validate_request(spec_neg_sleep)

    spec_unsafe_write = {
        "adapter": "synthetic",
        "params": {"write": "../escape.txt"},
        "effect_key": "k",
    }
    with pytest.raises(SpecError, match="synthetic params rejected: write must be a safe workspace-relative file name"):
        adapter_bridge.validate_request(spec_unsafe_write)


def test_validate_synthetic_import_error():
    spec = {"adapter": "synthetic", "params": {}, "effect_key": "k"}
    with patch.dict(sys.modules, {"adapters": None, "adapters.synthetic": None}):
        with pytest.raises(SpecError, match="adapter implementation unavailable on this worker"):
            adapter_bridge.validate_request(spec)


def test_validate_request_effect_key_validation():
    base = {"adapter": "synthetic", "params": {}}

    for bad_key in [None, 123, True, "", " ", "k/1", "k:2@bad", "k" * 201]:
        spec = dict(base, effect_key=bad_key)
        with pytest.raises(SpecError, match="claim spec effect_key is missing or malformed"):
            adapter_bridge.validate_request(spec)

    # Valid boundary length (200 chars)
    spec_200 = dict(base, effect_key="a" * 200)
    adapter, params, effect_key = adapter_bridge.validate_request(spec_200)
    assert len(effect_key) == 200


def test_atomic_json(tmp_path):
    target = os.path.join(str(tmp_path), "nested", "dir", "data.json")
    data = {"b": 2, "a": 1}

    adapter_bridge._atomic_json(target, data)
    assert os.path.isfile(target)

    with open(target, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data

    # Verify temp file cleanup on error
    with patch("json.dump", side_effect=RuntimeError("serialization exploded")):
        with pytest.raises(RuntimeError, match="serialization exploded"):
            adapter_bridge._atomic_json(target, data)

    # Only target should exist in directory, no leftover tmp files
    files = os.listdir(os.path.dirname(target))
    assert files == ["data.json"]


def test_write_request_creates_file_and_cleans_stale_report(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-test-write"
    spec = SimpleNamespace(
        adapter="synthetic",
        params={"write": "result.txt", "content": "ok"},
        attempt=1,
        task_id="tsk-100",
        dispatch_id=dispatch_id,
        effect_key="eff-key-100",
        artifact_dir=os.path.join(home, "artifacts", dispatch_id),
    )

    # Place a stale report first
    stale_report_file = adapter_bridge.report_path(home, dispatch_id)
    os.makedirs(os.path.dirname(stale_report_file), exist_ok=True)
    with open(stale_report_file, "w", encoding="utf-8") as f:
        f.write('{"outcome": "stale"}')
    assert os.path.isfile(stale_report_file)

    # Write request
    req_path = adapter_bridge.write_request(home, spec)
    assert os.path.isfile(req_path)
    # Stale report must have been unlinked
    assert not os.path.exists(stale_report_file)

    # Verify request content
    with open(req_path, encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["adapter"] == "synthetic"
    assert payload["params"] == {"write": "result.txt", "content": "ok"}
    assert payload["attempt"] == 1
    assert payload["task_id"] == "tsk-100"
    assert payload["dispatch_id"] == dispatch_id
    assert payload["effect_key"] == "eff-key-100"
    assert payload["workdir"] == spec.artifact_dir
    assert payload["report"] == adapter_bridge.report_path(home, dispatch_id)


def test_read_report_missing_or_malformed(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-test-read"

    # 1. Missing report file
    assert adapter_bridge.read_report(home, dispatch_id) is None

    rep_path = adapter_bridge.report_path(home, dispatch_id)
    os.makedirs(os.path.dirname(rep_path), exist_ok=True)

    # 2. Corrupt JSON
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write("{broken json")
    assert adapter_bridge.read_report(home, dispatch_id) is None

    # 3. Not a JSON object (array or scalar)
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(["success"], f)
    assert adapter_bridge.read_report(home, dispatch_id) is None

    # 4. Missing outcome
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump({"retryable": False}, f)
    assert adapter_bridge.read_report(home, dispatch_id) is None

    # 5. Invalid outcome value
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump({"outcome": "completed", "retryable": False}, f)
    assert adapter_bridge.read_report(home, dispatch_id) is None

    # 6. Non-boolean retryable
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump({"outcome": "success", "retryable": 1}, f)
    assert adapter_bridge.read_report(home, dispatch_id) is None

    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump({"outcome": "failure", "retryable": "true"}, f)
    assert adapter_bridge.read_report(home, dispatch_id) is None


def test_read_report_valid_cases(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-test-valid"
    rep_path = adapter_bridge.report_path(home, dispatch_id)
    os.makedirs(os.path.dirname(rep_path), exist_ok=True)

    # Success outcome
    valid_success = {"outcome": "success", "retryable": False, "reason": "all good"}
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(valid_success, f)
    assert adapter_bridge.read_report(home, dispatch_id) == valid_success

    # Failure outcome with retryable=True
    valid_failure = {"outcome": "failure", "retryable": True, "reason": "transient timeout"}
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(valid_failure, f)
    assert adapter_bridge.read_report(home, dispatch_id) == valid_failure

    # Omitted retryable defaults to False (which is boolean)
    omitted_retryable = {"outcome": "success"}
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(omitted_retryable, f)
    assert adapter_bridge.read_report(home, dispatch_id) == omitted_retryable


def test_cleanup(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-cleanup"

    # Safe to call when files don't exist
    adapter_bridge.cleanup(home, dispatch_id)

    # Create both files
    req_path = adapter_bridge.request_path(home, dispatch_id)
    rep_path = adapter_bridge.report_path(home, dispatch_id)
    os.makedirs(os.path.dirname(req_path), exist_ok=True)
    os.makedirs(os.path.dirname(rep_path), exist_ok=True)
    with open(req_path, "w") as f:
        f.write("{}")
    with open(rep_path, "w") as f:
        f.write("{}")

    assert os.path.exists(req_path)
    assert os.path.exists(rep_path)

    adapter_bridge.cleanup(home, dispatch_id)

    assert not os.path.exists(req_path)
    assert not os.path.exists(rep_path)

    # Calling again is idempotent
    adapter_bridge.cleanup(home, dispatch_id)


def test_full_lifecycle(tmp_path):
    home = str(tmp_path)
    dispatch_id = "dsp-lifecycle"
    raw_spec = {
        "adapter": "synthetic",
        "params": {"write": "result.txt", "content": "lifecycle test"},
        "effect_key": "eff-lifecycle-1",
    }

    # 1. Validate spec
    adapter, params, effect_key = adapter_bridge.validate_request(raw_spec)
    assert adapter == "synthetic"

    # 2. Build host execution spec and write request
    spec_obj = SimpleNamespace(
        adapter=adapter,
        params=params,
        attempt=1,
        task_id="tsk-lifecycle",
        dispatch_id=dispatch_id,
        effect_key=effect_key,
        artifact_dir=os.path.join(home, "artifacts", dispatch_id),
    )
    req_path = adapter_bridge.write_request(home, spec_obj)
    assert os.path.isfile(req_path)

    # 3. Check runner argv
    argv = adapter_bridge.runner_argv(home, dispatch_id)
    assert argv[2] == req_path

    # 4. Report is initially absent
    assert adapter_bridge.read_report(home, dispatch_id) is None

    # 5. Simulate runner writing report
    rep_path = adapter_bridge.report_path(home, dispatch_id)
    adapter_bridge._atomic_json(rep_path, {"outcome": "success", "retryable": False})

    # 6. Host reads report
    report = adapter_bridge.read_report(home, dispatch_id)
    assert report == {"outcome": "success", "retryable": False}

    # 7. Cleanup
    adapter_bridge.cleanup(home, dispatch_id)
    assert not os.path.exists(req_path)
    assert not os.path.exists(rep_path)
