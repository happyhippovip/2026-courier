"""Unit tests for courier_core.verification.

Hardens verifier hand-off contracts, regex bounds, fail-closed handling,
and verifier identity composition.
"""

from __future__ import annotations

import sys
import types
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    ADAPTER_NAME,
    Verdict,
    _rule,
    _source_sha256,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)


def _sample_task(adapter: str = "synthetic", effect_class: str = "idempotent") -> TaskState:
    return TaskState(
        task_id="t-1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=30,
        timeout_s=10,
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
    )


def _sample_result_event(
    outcome: str = "success",
    artifacts: list | None = None,
    retryable: bool | None = None,
    reason: str | None = None,
) -> Event:
    payload: dict = {
        "outcome": outcome,
        "artifacts": artifacts or [],
    }
    if retryable is not None:
        payload["retryable"] = retryable
    if reason is not None:
        payload["reason"] = reason
    return Event(
        type=EventType.RESULT_READY,
        seq=5,
        task_id="t-1",
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
        result_id="r-1",
        payload=payload,
    )


class TestAdapterNameRegex:
    def test_valid_adapter_names(self):
        valid = ["a", "synthetic", "local_shell", "adapter_123", "a" * 64]
        for name in valid:
            assert ADAPTER_NAME.match(name) is not None

    def test_invalid_adapter_names(self):
        invalid = [
            "",
            "1adapter",
            "_adapter",
            "Adapter",
            "adapter-name",
            "adapter.name",
            "../adapter",
            "adapter/name",
            "a" * 65,
        ]
        for name in invalid:
            assert ADAPTER_NAME.match(name) is None


class TestVerdictDataclass:
    def test_verdict_defaults_and_fields(self):
        v = Verdict(accepted=True)
        assert v.accepted is True
        assert v.reason == ""
        assert v.retryable is False
        assert v.verifier is None

    def test_verdict_frozen(self):
        v = Verdict(accepted=True)
        with pytest.raises(FrozenInstanceError):
            v.accepted = False  # type: ignore[misc]


class TestAdapterVerifierResolution:
    def test_malformed_adapter_returns_none(self):
        assert adapter_verifier("bad-adapter") is None
        assert adapter_verifier("../bad") is None
        assert adapter_verifier("") is None

    def test_missing_adapter_returns_none(self):
        assert adapter_verifier("nonexistent_adapter_xyz_123") is None

    def test_synthetic_adapter_resolves(self):
        verify = adapter_verifier("synthetic")
        assert callable(verify)


class TestVerifierIdentityAndSourceDigest:
    def test_rule_structure(self):
        rule = _rule("no_verifier", "custom")
        assert rule == {
            "kind": "courier_rule",
            "name": "no_verifier",
            "adapter": "custom",
        }

    def test_verifier_identity_with_version(self, monkeypatch):
        fake_mod = types.ModuleType("adapters.fake_adapter")
        fake_mod.__file__ = __file__
        fake_mod.VERIFIER_VERSION = "2.1.0"

        def fake_verify(task, result, home):
            return Verdict(accepted=True)

        fake_verify.__module__ = "adapters.fake_adapter"
        fake_verify.__qualname__ = "fake_verify"
        monkeypatch.setitem(sys.modules, "adapters.fake_adapter", fake_mod)

        ident = verifier_identity(fake_verify)
        assert ident["kind"] == "adapter"
        assert ident["name"] == "adapters.fake_adapter.fake_verify"
        assert ident["version"] == "2.1.0"
        assert isinstance(ident["source_sha256"], str)
        assert len(ident["source_sha256"]) == 64

    def test_verifier_identity_without_version(self, monkeypatch):
        fake_mod = types.ModuleType("adapters.no_version_adapter")
        fake_mod.__file__ = None

        def fake_verify(task, result, home):
            return Verdict(accepted=True)

        fake_verify.__module__ = "adapters.no_version_adapter"
        fake_verify.__qualname__ = "fake_verify"
        monkeypatch.setitem(sys.modules, "adapters.no_version_adapter", fake_mod)

        ident = verifier_identity(fake_verify)
        assert ident["version"] is None
        assert ident["source_sha256"] is None

    def test_verifier_identity_long_version_truncated(self, monkeypatch):
        fake_mod = types.ModuleType("adapters.long_ver_adapter")
        fake_mod.__file__ = None
        fake_mod.VERIFIER_VERSION = "v" * 150

        def fake_verify(task, result, home):
            return Verdict(accepted=True)

        fake_verify.__module__ = "adapters.long_ver_adapter"
        fake_verify.__qualname__ = "fake_verify"
        monkeypatch.setitem(sys.modules, "adapters.long_ver_adapter", fake_mod)

        ident = verifier_identity(fake_verify)
        assert ident["version"] == "v" * 100

    def test_source_sha256_missing_or_unreadable(self):
        assert _source_sha256("nonexistent_mod_123") is None


class TestRunVerifier:
    def test_worker_outcome_failure_rejects(self):
        task = _sample_task()
        result = _sample_result_event(outcome="failure", reason="crashed", retryable=True)
        v = run_verifier(lambda a: None, task, result, Path("/tmp"))
        assert v.accepted is False
        assert v.reason == "crashed"
        assert v.retryable is True
        assert v.verifier == _rule("worker_reported_failure", "synthetic")

    def test_worker_failure_omitted_retryable_checks_idempotency(self):
        task_idempotent = _sample_task(effect_class="idempotent")
        result = _sample_result_event(outcome="failure")
        v1 = run_verifier(lambda a: None, task_idempotent, result, Path("/tmp"))
        assert v1.accepted is False
        assert v1.retryable is True
        assert v1.reason == "worker reported failure"

        task_unknown = _sample_task(effect_class="mutating")
        v2 = run_verifier(lambda a: None, task_unknown, result, Path("/tmp"))
        assert v2.accepted is False
        assert v2.retryable is False

    def test_worker_failure_truncates_long_reason(self):
        task = _sample_task()
        result = _sample_result_event(outcome="failure", reason="x" * 600)
        v = run_verifier(lambda a: None, task, result, Path("/tmp"))
        assert len(v.reason) == 500
        assert v.reason == "x" * 500

    def test_resolver_exception_fails_closed(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")

        def bad_resolver(name):
            raise ImportError("corrupt adapter")

        v = run_verifier(bad_resolver, task, result, Path("/tmp"))
        assert v.accepted is False
        assert "verifier for adapter 'synthetic' failed to load: ImportError" in v.reason
        assert v.retryable is False
        assert v.verifier == _rule("verifier_load_failed", "synthetic")

    def test_no_verifier_registered_fails_closed(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")
        v = run_verifier(lambda a: None, task, result, Path("/tmp"))
        assert v.accepted is False
        assert v.reason == "no verifier registered for adapter 'synthetic'"
        assert v.retryable is False
        assert v.verifier == _rule("no_verifier", "synthetic")

    def test_verifier_exception_fails_closed(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")

        def raising_verify(task, result, home):
            raise ValueError("corrupt evidence file")

        v = run_verifier(lambda a: raising_verify, task, result, Path("/tmp"))
        assert v.accepted is False
        assert v.reason == "verifier raised ValueError"
        assert v.retryable is False
        assert v.verifier["kind"] == "adapter"

    def test_verifier_returns_invalid_type_fails_closed(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")

        for bad_return in [None, "accepted", {"accepted": True}, Verdict(accepted="not_a_bool")]:  # type: ignore[arg-type]
            def bad_verify(task, result, home):
                return bad_return

            v = run_verifier(lambda a: bad_verify, task, result, Path("/tmp"))
            assert v.accepted is False
            assert v.reason == "verifier returned an invalid verdict"
            assert v.retryable is False

    def test_verifier_success_accepted(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")

        def good_verify(task, result, home):
            return Verdict(accepted=True, reason="evidence valid", retryable=False)

        v = run_verifier(lambda a: good_verify, task, result, Path("/tmp"))
        assert v.accepted is True
        assert v.reason == "evidence valid"
        assert v.retryable is False
        assert v.verifier["kind"] == "adapter"

    def test_verifier_success_rejected_with_retryable(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")

        def reject_verify(task, result, home):
            return Verdict(accepted=False, reason="missing artifact", retryable=True)

        v = run_verifier(lambda a: reject_verify, task, result, Path("/tmp"))
        assert v.accepted is False
        assert v.reason == "missing artifact"
        assert v.retryable is True
        assert v.verifier["kind"] == "adapter"

    def test_verifier_reason_truncated_to_500(self):
        task = _sample_task()
        result = _sample_result_event(outcome="success")

        def long_reason_verify(task, result, home):
            return Verdict(accepted=False, reason="r" * 700)

        v = run_verifier(lambda a: long_reason_verify, task, result, Path("/tmp"))
        assert len(v.reason) == 500
        assert v.reason == "r" * 500
