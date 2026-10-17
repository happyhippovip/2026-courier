"""P9 hardening for courier_core.verification: digest cache + import re-raise.

Tests only; no behavior change. Covers the fail-closed paths the existing
suites do not pin down:

- adapter_verifier re-raises a ModuleNotFoundError that comes from *inside*
  an adapter module (a missing dependency) instead of swallowing it, and
  lets unexpected import-time errors propagate;
- run_verifier contains only Exception; a BaseException from resolve
  propagates instead of becoming a load-failure verdict;
- _source_sha256 serves a stale digest while the (path, mtime_ns, size)
  cache key is unchanged (documents the staleness window) and re-reads
  when size or mtime changes;
- verifier_identity coerces a non-string VERIFIER_VERSION with str().

No network, no credentials.
"""

import hashlib
import os
import sys
import types

import pytest

from courier_core import verification as verify_mod
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    _source_sha256,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)

_ARTIFACT_SHA = hashlib.sha256(b"verification-cache-probe").hexdigest()


def _task(**changes):
    value = dict(task_id="t1", status=TaskStatus.VERIFYING, adapter="synthetic",
                 params={}, effect_class="idempotent", max_attempts=3,
                 lease_ttl_s=6, timeout_s=None)
    value.update(changes)
    return TaskState(**value)


def _ready(payload, **changes):
    merged = {"outcome": "success",
              "artifacts": [{"path": "out.txt", "sha256": _ARTIFACT_SHA}]}
    merged.update(payload)
    base = dict(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                dispatch_id="d1", worker_id="w1", result_id="r1",
                payload=merged)
    base.update(changes)
    return Event(**base)


def _install_fake_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _drop_fake_module(name):
    sys.modules.pop(name, None)


# -- adapter_verifier: nested import failures propagate -----------------------


def test_adapter_verifier_reraises_nested_module_not_found(monkeypatch):
    """A missing *dependency* inside an adapter module must propagate."""

    def boom(dotted):
        raise ModuleNotFoundError("No module named 'dep'", name="dep")

    monkeypatch.setattr(verify_mod.importlib, "import_module", boom)
    with pytest.raises(ModuleNotFoundError):
        adapter_verifier("synthetic")


def test_adapter_verifier_reraises_unexpected_import_error(monkeypatch):
    """Non-import errors at import time are not swallowed into None."""

    def boom(dotted):
        raise RuntimeError("adapter blew up while importing")

    monkeypatch.setattr(verify_mod.importlib, "import_module", boom)
    with pytest.raises(RuntimeError):
        adapter_verifier("synthetic")


def test_adapter_verifier_none_when_adapters_package_missing(monkeypatch):
    """A missing top-level adapters package resolves to None (no verifier)."""

    def boom(dotted):
        raise ModuleNotFoundError("No module named 'adapters'", name="adapters")

    monkeypatch.setattr(verify_mod.importlib, "import_module", boom)
    assert adapter_verifier("synthetic") is None


# -- run_verifier: only Exception is contained ---------------------------------


def test_run_verifier_base_exception_from_resolve_propagates(tmp_path):
    """KeyboardInterrupt from resolve is not converted into a verdict."""

    def resolve(adapter):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_verifier(resolve, _task(), _ready({"outcome": "success"}), tmp_path)


def test_run_verifier_non_callable_resolve_result_is_fail_closed(tmp_path):
    """A resolve result that cannot be called fails closed, non-retryably."""

    verdict = run_verifier(lambda adapter: 42, _task(),
                           _ready({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "TypeError" in verdict.reason
    assert verdict.verifier["kind"] == "adapter"


# -- _source_sha256: cache hit versus re-read ----------------------------------


def _hash_counter(monkeypatch):
    """Count hashlib.sha256 constructions (one per real file hash)."""
    calls = []
    real_sha256 = hashlib.sha256

    def counting_sha256(data=b""):
        calls.append(1)
        return real_sha256(data)

    monkeypatch.setattr(verify_mod.hashlib, "sha256", counting_sha256)
    return calls


def test_source_sha256_cache_hit_serves_stale_digest(tmp_path, monkeypatch):
    """Unchanged (mtime_ns, size) serves the cached digest without re-hash."""
    name = "fake_cache_stale_mod_xyz"
    target = tmp_path / "stale_mod.py"
    target.write_bytes(b"v1 = 1\n")
    expected = hashlib.sha256(b"v1 = 1\n").hexdigest()
    _install_fake_module(name, __file__=str(target))
    calls = _hash_counter(monkeypatch)
    try:
        assert _source_sha256(name) == expected
        assert len(calls) == 1
        stat = os.stat(target)
        target.write_bytes(b"v2 = 2\n")  # same size, new content
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert _source_sha256(name) == expected  # stale: no re-hash happened
        assert len(calls) == 1
    finally:
        _drop_fake_module(name)


def test_source_sha256_rereads_when_size_changes(tmp_path, monkeypatch):
    """A size change invalidates the cache entry even if mtime is restored."""
    name = "fake_cache_size_mod_xyz"
    target = tmp_path / "size_mod.py"
    target.write_bytes(b"v1 = 1\n")
    expected_new = hashlib.sha256(b"v1 = 1\n# more\n").hexdigest()
    _install_fake_module(name, __file__=str(target))
    calls = _hash_counter(monkeypatch)
    try:
        first = _source_sha256(name)
        assert len(calls) == 1
        stat = os.stat(target)
        target.write_bytes(b"v1 = 1\n# more\n")
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        second = _source_sha256(name)
        assert second != first
        assert second == expected_new
        assert len(calls) == 2
    finally:
        _drop_fake_module(name)


def test_source_sha256_rereads_when_mtime_changes(tmp_path, monkeypatch):
    """An mtime change forces a re-hash even when the bytes are identical."""
    name = "fake_cache_mtime_mod_xyz"
    target = tmp_path / "mtime_mod.py"
    target.write_bytes(b"same = True\n")
    expected = hashlib.sha256(b"same = True\n").hexdigest()
    _install_fake_module(name, __file__=str(target))
    calls = _hash_counter(monkeypatch)
    try:
        assert _source_sha256(name) == expected
        assert len(calls) == 1
        stat = os.stat(target)
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        assert _source_sha256(name) == expected
        assert len(calls) == 2
    finally:
        _drop_fake_module(name)


# -- verifier_identity: version coercion ---------------------------------------


def test_verifier_identity_coerces_int_version_to_str():
    """A non-string VERIFIER_VERSION is stringified, never dropped."""
    name = "fake_int_version_mod_xyz"
    _install_fake_module(name, VERIFIER_VERSION=2)
    try:
        def verify(task, result, home):
            raise AssertionError("must not run")

        verify.__module__ = name
        identity = verifier_identity(verify)
        assert identity["version"] == "2"
        assert identity["source_sha256"] is None
        assert identity["name"].endswith(".verify")
    finally:
        _drop_fake_module(name)
