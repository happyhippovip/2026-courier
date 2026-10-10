"""P9 test hardening for courier_core.verification (adapter lookup + identity pins).

Tests only: no behavior change. Covers the fail-closed adapter-verifier
lookup (name gating, missing/unusable verifiers, unexpected import errors
re-raised), the verifier source-digest helper and identity pins, and the
run_verifier lookup-failure edges. No network, no credentials, no subprocesses.
"""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

import pytest

from courier_core import verification as V
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus


def _task(adapter: str = "missing_adapter_xyz", effect_class: str = "idempotent") -> TaskState:
    return TaskState(
        task_id="t-lookup-1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=None,
    )


def _ready(outcome: str = "success") -> Event:
    return Event(
        type=EventType.RESULT_READY,
        task_id="t-lookup-1",
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
        result_id="r-1",
        payload={"artifacts": [], "outcome": outcome},
    )


# --- adapter_verifier: name gating (no import attempted for bad names) ---

INVALID_NAMES = ["", "A", "0abc", "-x", "has-hyphen", "has space", "UPPER", "a" * 65, "adapters.x"]


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_invalid_adapter_names_return_none_without_import(name):
    assert V.adapter_verifier(name) is None


def test_missing_adapter_module_returns_none():
    assert V.adapter_verifier("no_such_adapter_xyz") is None


def test_single_char_name_is_valid_shape_but_missing_returns_none():
    # "z" matches ^[a-z][a-z0-9_]{0,63}$ yet resolves to nothing.
    assert V.adapter_verifier("z") is None


def test_max_length_name_shape_is_accepted_for_lookup():
    name = "a" * 64
    assert V.ADAPTER_NAME.match(name) is not None
    assert V.adapter_verifier(name) is None


# --- adapter_verifier: unusable verifier objects ---

def test_adapter_without_verify_attribute_returns_none(monkeypatch):
    pkg = types.ModuleType("adapters")
    pkg.__path__ = []
    mod = types.ModuleType("adapters.n verify dummy".replace(" ", "_"))
    monkeypatch.setitem(sys.modules, "adapters", pkg)
    monkeypatch.setitem(sys.modules, mod.__name__, mod)
    short = mod.__name__.split(".", 1)[1]
    assert V.adapter_verifier(short) is None


def test_adapter_with_non_callable_verify_returns_none(monkeypatch):
    pkg = types.ModuleType("adapters")
    pkg.__path__ = []
    mod = types.ModuleType("adapters.plain_object")
    mod.verify = "not-a-function"
    monkeypatch.setitem(sys.modules, "adapters", pkg)
    monkeypatch.setitem(sys.modules, "adapters.plain_object", mod)
    assert V.adapter_verifier("plain_object") is None


def test_adapter_with_callable_verify_is_returned(monkeypatch):
    def verify(task, result, home):
        return V.Verdict(True, "ok")

    pkg = types.ModuleType("adapters")
    pkg.__path__ = []
    mod = types.ModuleType("adapters.working_fake")
    mod.verify = verify
    monkeypatch.setitem(sys.modules, "adapters", pkg)
    monkeypatch.setitem(sys.modules, "adapters.working_fake", mod)
    assert V.adapter_verifier("working_fake") is verify


def test_unexpected_import_error_is_reraised(tmp_path, monkeypatch):
    pkg_dir = tmp_path / "adapters"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "broken_dep.py").write_text(
        "import definitely_missing_dependency_xyz\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "adapters", raising=False)
    monkeypatch.delitem(sys.modules, "adapters.broken_dep", raising=False)
    with pytest.raises(ModuleNotFoundError):
        V.adapter_verifier("broken_dep")


# --- _source_sha256 ---

def test_source_digest_none_when_module_has_no_file(monkeypatch):
    mod = types.ModuleType("no_file_module_xyz")
    monkeypatch.setitem(sys.modules, "no_file_module_xyz", mod)
    assert V._source_sha256("no_file_module_xyz") is None


def test_source_digest_none_for_unknown_module():
    assert V._source_sha256("definitely_not_a_module_xyz") is None


def test_source_digest_matches_file_bytes_and_is_cached():
    digest = V._source_sha256("courier_core.verification")
    assert digest is not None and len(digest) == 64 and all(
        c in "0123456789abcdef" for c in digest
    )
    path = Path(sys.modules["courier_core.verification"].__file__)
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == expected
    assert V._source_sha256("courier_core.verification") == digest


def test_source_digest_none_when_file_is_missing(monkeypatch):
    mod = types.ModuleType("gone_module_xyz")
    mod.__file__ = "/nonexistent/path/module_xyz.py"
    monkeypatch.setitem(sys.modules, "gone_module_xyz", mod)
    assert V._source_sha256("gone_module_xyz") is None


# --- verifier_identity ---

def test_identity_truncates_long_version_to_100_chars(monkeypatch):
    def verify(task, result, home):
        return V.Verdict(True, "ok")

    verify.__module__ = "fake_versioned_module_xyz"
    verify.__qualname__ = "verify"
    mod = types.ModuleType("fake_versioned_module_xyz")
    mod.__file__ = __file__
    mod.VERIFIER_VERSION = "v" * 200
    monkeypatch.setitem(sys.modules, "fake_versioned_module_xyz", mod)
    identity = V.verifier_identity(verify)
    assert identity["kind"] == "adapter"
    assert identity["name"] == "fake_versioned_module_xyz.verify"
    assert identity["version"] == "v" * 100


def test_identity_version_none_when_unset(monkeypatch):
    def verify(task, result, home):
        return V.Verdict(True, "ok")

    verify.__module__ = "fake_unversioned_module_xyz"
    verify.__qualname__ = "verify"
    mod = types.ModuleType("fake_unversioned_module_xyz")
    mod.__file__ = __file__
    monkeypatch.setitem(sys.modules, "fake_unversioned_module_xyz", mod)
    identity = V.verifier_identity(verify)
    assert identity["version"] is None
    assert identity["source_sha256"] is not None


def test_identity_for_unknown_module_is_fail_closed_shape():
    def verify(task, result, home):  # pragma: no cover - never called
        return V.Verdict(True, "ok")

    verify.__module__ = "missing_module_xyz"
    identity = V.verifier_identity(verify)
    assert identity["version"] is None
    assert identity["source_sha256"] is None
    assert identity["name"].endswith(".verify")


# --- run_verifier: lookup-failure edges ---

def test_resolve_exception_rejects_non_retryably():
    def resolve(adapter):
        raise RuntimeError("boom")

    verdict = V.run_verifier(resolve, _task(), _ready(), Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "failed to load" in verdict.reason
    assert verdict.verifier == {
        "kind": "courier_rule",
        "name": "verifier_load_failed",
        "adapter": "missing_adapter_xyz",
    }


def test_missing_verifier_rejects_non_retryably():
    verdict = V.run_verifier(lambda adapter: None, _task(), _ready(), Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "no verifier registered" in verdict.reason
    assert verdict.verifier["name"] == "no_verifier"


def test_real_lookup_missing_adapter_rejects_without_network():
    verdict = V.run_verifier(V.adapter_verifier, _task(), _ready(), Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "no_verifier"


def test_worker_failure_reason_and_retryable_defaults():
    task = _task(effect_class="idempotent")
    result = Event(
        type=EventType.RESULT_READY,
        task_id="t-lookup-1",
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
        result_id="r-1",
        payload={"artifacts": [], "outcome": "failure"},
    )
    verdict = V.run_verifier(lambda adapter: None, task, result, Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.reason == "worker reported failure"
    assert verdict.retryable is True


def test_adapter_success_passthrough_carries_identity():
    def verify(task, result, home):
        return V.Verdict(True, "looks good", False)

    verify.__module__ = "courier_core.verification"
    task = _task(adapter="synthetic")
    verdict = V.run_verifier(lambda adapter: verify, task, _ready(), Path("/tmp"))
    assert verdict.accepted is True
    assert verdict.reason == "looks good"
    assert verdict.verifier["kind"] == "adapter"
