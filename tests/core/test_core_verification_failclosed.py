"""P9 hardening for courier_core.verification: fail-closed verifier hand-off.

Pure unit tests only. No network, no controller, no journal. Every test
constructs its own TaskState / Event fakes and injects the adapter resolver,
so nothing here can pass because of controller or adapter behavior.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import types
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    ADAPTER_NAME,
    Verdict,
    _source_sha256,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)

SHA = hashlib.sha256(b"courier-failclosed").hexdigest()


def make_task(adapter="probe", effect_class="idempotent"):
    return TaskState(
        task_id="t1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=6,
        timeout_s=None,
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
    )


def make_result(outcome="success", **payload_extra):
    payload = {
        "artifacts": [{"path": "out.txt", "sha256": SHA}],
        "outcome": outcome,
    }
    payload.update(payload_extra)
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
        result_id="r-t1-1",
        payload=payload,
    )


def test_adapter_name_regex_matches_module_contract():
    assert ADAPTER_NAME.match("synthetic")
    assert ADAPTER_NAME.match("a")
    for bad in ["", "Upper", "has-dash", "9abc", "_lead", "a b", "../x", "a" * 65]:
        assert not ADAPTER_NAME.match(bad), bad


@pytest.mark.parametrize("bad", ["", "UPPER", "has-dash", "9abc", "../x", "a" * 65, "with space"])
def test_adapter_verifier_rejects_malformed_names_without_importing(monkeypatch, bad):
    called = []

    def _fail(name):
        called.append(name)
        raise AssertionError("must not import for a malformed name")

    monkeypatch.setattr(importlib, "import_module", _fail)
    assert adapter_verifier(bad) is None
    assert called == []


def test_adapter_verifier_returns_none_for_unknown_adapter():
    assert adapter_verifier("nosuchadapterxyz") is None


def test_adapter_verifier_resolves_real_adapters_without_network():
    for name in ("synthetic", "local_shell"):
        verify = adapter_verifier(name)
        assert callable(verify)


def test_adapter_verifier_none_when_module_has_no_verify(monkeypatch):
    module = types.ModuleType("adapters.noverify")
    monkeypatch.setitem(sys.modules, "adapters.noverify", module)
    assert adapter_verifier("noverify") is None


def test_adapter_verifier_none_when_verify_is_not_callable(monkeypatch):
    module = types.ModuleType("adapters.noncallable")
    module.verify = "not-a-function"
    monkeypatch.setitem(sys.modules, "adapters.noncallable", module)
    assert adapter_verifier("noncallable") is None


def test_adapter_verifier_reraises_unrelated_module_not_found(monkeypatch):
    def _raise(name):
        raise ModuleNotFoundError("inner dependency missing", name="some_other_dep")

    monkeypatch.setattr(importlib, "import_module", _raise)
    with pytest.raises(ModuleNotFoundError):
        adapter_verifier("synthetic")


def test_adapter_verifier_does_not_swallow_unexpected_errors(monkeypatch):
    def _raise(name):
        raise RuntimeError("boom")

    monkeypatch.setattr(importlib, "import_module", _raise)
    with pytest.raises(RuntimeError):
        adapter_verifier("synthetic")


def test_source_sha256_none_for_unknown_module():
    assert _source_sha256("no.such.module.xyz") is None


def test_source_sha256_digest_matches_file_bytes_and_caches():
    first = _source_sha256("courier_core.verification")
    assert first is not None and len(first) == 64
    path = sys.modules["courier_core.verification"].__file__
    with open(path, "rb") as handle:
        expected = hashlib.sha256(handle.read()).hexdigest()
    assert first == expected
    assert _source_sha256("courier_core.verification") == first


def test_source_sha256_none_when_file_unreadable(monkeypatch):
    import builtins

    def _raise(*args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(builtins, "open", _raise)
    assert _source_sha256("courier_core.verification") is None


def test_verifier_identity_shape_without_version():
    def verify(task, result, home):
        return Verdict(True, "ok")

    identity = verifier_identity(verify)
    assert identity["kind"] == "adapter"
    assert identity["name"].startswith(__name__ + ".")
    assert identity["name"].endswith(".verify")
    assert identity["version"] is None


def test_verifier_identity_carries_and_truncates_version(monkeypatch):
    module = types.ModuleType("fake_versioned_mod")
    module.VERIFIER_VERSION = "v" * 150
    module.__file__ = None
    monkeypatch.setitem(sys.modules, "fake_versioned_mod", module)

    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = "fake_versioned_mod"
    identity = verifier_identity(verify)
    assert identity["version"] == "v" * 100
    assert identity["source_sha256"] is None


def test_verifier_identity_without_module_uses_placeholder():
    verify = lambda task, result, home: Verdict(True, "ok")  # noqa: E731
    verify.__module__ = None
    identity = verifier_identity(verify)
    assert identity["name"].startswith("?.")


@pytest.mark.parametrize("retryable", [True, False])
def test_worker_failure_keeps_explicit_retryable(retryable):
    task = make_task(effect_class="idempotent")
    result = make_result(outcome="failure", retryable=retryable, reason="provider busy")
    verdict = run_verifier(lambda adapter: (_ for _ in ()).throw(AssertionError("unused")), task, result, Path("home"))
    assert verdict.accepted is False
    assert verdict.retryable is retryable
    assert verdict.reason == "provider busy"
    assert verdict.verifier == {"kind": "courier_rule", "name": "worker_reported_failure", "adapter": "probe"}


@pytest.mark.parametrize(
    "effect_class, expected",
    [("idempotent", True), ("non_idempotent", False), ("unknown-class", False)],
)
def test_worker_failure_without_retryable_fails_closed_by_effect_class(effect_class, expected):
    task = make_task(effect_class=effect_class)
    payload = {"artifacts": [{"path": "out.txt", "sha256": SHA}], "outcome": "failure"}
    result = Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
        result_id="r-t1-1",
        payload=payload,
    )
    verdict = run_verifier(lambda adapter: (_ for _ in ()).throw(AssertionError("unused")), task, result, Path("home"))
    assert verdict.accepted is False
    assert verdict.retryable is expected
    assert verdict.reason == "worker reported failure"


def test_worker_failure_reason_defaults_and_truncates():
    task = make_task()
    long_reason = "r" * 600
    verdict = run_verifier(lambda adapter: None, task, make_result(outcome="failure", reason=long_reason), Path("home"))
    assert len(verdict.reason) == 500
    missing = make_result(outcome="failure")
    object.__setattr__(missing, "payload", {**missing.payload, "reason": ""})
    verdict2 = run_verifier(lambda adapter: None, task, missing, Path("home"))
    assert verdict2.reason == "worker reported failure"


def test_missing_outcome_is_treated_as_worker_failure():
    # RESULT_READY validation requires an outcome key, so a payload without
    # one cannot be a journaled RESULT_READY. A progress-shaped event carries
    # the same empty-outcome shape through run_verifier's payload read.
    task = make_task()
    result = Event(type=EventType.TASK_PROGRESS, task_id="t1", attempt=1, dispatch_id="d-t1-1", payload={})
    verdict = run_verifier(lambda adapter: (_ for _ in ()).throw(AssertionError("unused")), task, result, Path("home"))
    assert verdict.accepted is False
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_resolve_error_fails_closed():
    def _raise(adapter):
        raise RuntimeError("import blew up")

    verdict = run_verifier(_raise, make_task(), make_result(), Path("home"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "RuntimeError" in verdict.reason
    assert verdict.verifier == {"kind": "courier_rule", "name": "verifier_load_failed", "adapter": "probe"}


def test_missing_verifier_fails_closed():
    verdict = run_verifier(lambda adapter: None, make_task(), make_result(), Path("home"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "no_verifier", "adapter": "probe"}


def test_raising_verifier_fails_closed_with_identity():
    def verify(task, result, home):
        raise ValueError("bad evidence")

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), Path("home"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier raised ValueError"
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith(".verify")


@pytest.mark.parametrize("bad", [None, True, {"accepted": True}, Verdict(1, "truthy is not True")])
def test_invalid_verdict_fails_closed_with_identity(bad):
    verdict = run_verifier(lambda adapter: (lambda task, result, home: bad), make_task(), make_result(), Path("home"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier returned an invalid verdict"
    assert verdict.verifier["kind"] == "adapter"


def test_accepted_verdict_is_stamped_with_identity():
    def verify(task, result, home):
        return Verdict(True, "evidence ok", False)

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), Path("home"))
    assert verdict.accepted is True
    assert verdict.reason == "evidence ok"
    assert verdict.retryable is False
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith(".verify")


def test_accepted_verdict_reason_truncated_and_retryable_coerced():
    def verify(task, result, home):
        return Verdict(True, "x" * 600, 1)

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), Path("home"))
    assert verdict.accepted is True
    assert len(verdict.reason) == 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"
