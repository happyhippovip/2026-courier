"""P9 hardening for courier_core.verification: worker-failure + adapter-name pins.

Tests only; no behavior change. Covers the fail-closed rules that do not need
any adapter code or network:

- adapter_verifier refuses malformed adapter names without importing.
- run_verifier treats any non-success worker outcome as rejected, with
  retryable defaulting to may_auto_retry(effect_class) and reason capped.
- run_verifier stays fail-closed when the verifier is missing, fails to load,
  raises, or returns a non-Verdict.
- success passthrough truncates reason and attaches verifier identity.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    ADAPTER_NAME,
    Verdict,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)

SHA = "ab" * 32


def _task(adapter="synthetic", effect_class="idempotent"):
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


def _result(outcome="failure", extra=None, result_id="r-t1-1"):
    payload = {"artifacts": [{"path": "out.txt", "sha256": SHA}], "outcome": outcome}
    if extra:
        payload.update(extra)
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
        result_id=result_id,
        payload=payload,
    )


def test_adapter_name_rejects_malformed_without_import():
    bad = ["", "UPPER", "has-dash", "0start", "with space", "with.dot", "a" * 65, "synthetic!"]
    for name in bad:
        assert not ADAPTER_NAME.match(name), name
        assert adapter_verifier(name) is None


def test_adapter_name_accepts_shape_but_missing_module_returns_none():
    assert ADAPTER_NAME.match("no_such_adapter_xyz")
    assert adapter_verifier("no_such_adapter_xyz") is None


def test_worker_failure_is_rejected_and_resolve_not_called():
    def _boom(_name):
        raise AssertionError("resolve must not be called for worker failure")

    event = _result("failure", {"reason": "boom", "retryable": True})
    verdict = run_verifier(_boom, _task(), event, Path("."))
    assert verdict.accepted is False
    assert verdict.reason == "boom"
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "courier_rule"
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_worker_failure_retryable_defaults_by_effect_class():
    from courier_core.state_machine import may_auto_retry

    idem = run_verifier(lambda _n: None, _task(effect_class="idempotent"), _result("failure"), Path("."))
    non = run_verifier(lambda _n: None, _task(effect_class="non_idempotent"), _result("failure"), Path("."))
    # Only an idempotent effect is auto-retryable by omission.
    assert idem.retryable is True
    assert non.retryable is False
    assert idem.retryable is bool(may_auto_retry("idempotent"))
    assert non.retryable is bool(may_auto_retry("non_idempotent"))


def test_worker_failure_reason_truncated_and_defaulted():
    long_reason = "x" * 600
    verdict = run_verifier(lambda _n: None, _task(), _result("failure", {"reason": long_reason}), Path("."))
    assert len(verdict.reason) == 500
    missing = run_verifier(lambda _n: None, _task(), _result("failure"), Path("."))
    assert missing.reason == "worker reported failure"


def test_missing_verifier_rejects_non_retryably():
    verdict = run_verifier(lambda _n: None, _task(adapter="missing"), _result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "no_verifier"


def test_verifier_load_failure_rejects():
    def _raise(_name):
        raise ImportError("broken")

    verdict = run_verifier(_raise, _task(), _result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "verifier_load_failed"


def test_verifier_raises_rejects_with_identity():
    def _bad(_task_state, _result_event, _home):
        raise ValueError("kaput")

    verdict = run_verifier(lambda _n: _bad, _task(), _result("success"), Path("."))
    assert verdict.accepted is False
    assert "ValueError" in verdict.reason
    assert verdict.verifier["kind"] == "adapter"


def test_verifier_invalid_return_rejects():
    # None means "no verifier registered", which is its own fail-closed branch.
    verdict = run_verifier(lambda _n: None, _task(), _result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.verifier["name"] == "no_verifier"
    for bad in ({"accepted": True}, "yes", 42):
        verdict = run_verifier(lambda _n, _b=bad: (lambda _t, _r, _h: _b), _task(), _result("success"), Path("."))
        assert verdict.accepted is False
        assert verdict.reason == "verifier returned an invalid verdict"

    def _wrong_type(_t, _r, _h):
        return Verdict("yes")

    verdict = run_verifier(lambda _n: _wrong_type, _task(), _result("success"), Path("."))
    assert verdict.accepted is False


def test_success_passthrough_truncates_and_attaches_identity():
    def _ok(_t, _r, _h):
        return Verdict(True, "y" * 600, 1)

    verdict = run_verifier(lambda _n: _ok, _task(), _result("success"), Path("."))
    assert verdict.accepted is True
    assert len(verdict.reason) == 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"
    assert "name" in verdict.verifier


def test_verifier_identity_version_truncated():
    mod = types.ModuleType("fake_verifier_mod_long")
    mod.VERIFIER_VERSION = "v" * 200
    sys.modules["fake_verifier_mod_long"] = mod
    try:

        def _fn(_t, _r, _h):
            return Verdict(True)

        _fn.__module__ = "fake_verifier_mod_long"
        ident = verifier_identity(_fn)
        assert len(ident["version"]) == 100
    finally:
        del sys.modules["fake_verifier_mod_long"]


def test_verifier_identity_missing_version_is_none():
    def _fn(_t, _r, _h):
        return Verdict(True)

    _fn.__module__ = "definitely_missing_module_xyz"
    ident = verifier_identity(_fn)
    assert ident["version"] is None
    assert ident["source_sha256"] is None
