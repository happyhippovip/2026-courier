"""P9 hardening for courier_core.verification (P9-verification_verdict_defaults).

Tests only. Pins Verdict defaults/frozen shape, ADAPTER_NAME bounds,
verifier_identity version handling, and run_verifier reason/retryable
coercion. All offline, no network.
"""

from __future__ import annotations

import dataclasses
import sys
import types
from pathlib import Path

import pytest

from courier_core import verification as V
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus


def _task(adapter: str = "synthetic", effect_class: str = "idempotent") -> TaskState:
    return TaskState(
        task_id="t1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=30,
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
    )


def _ready(payload: dict) -> Event:
    base = {"artifacts": [], "outcome": "success"}
    base.update(payload)
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=base,
    )


def test_verdict_defaults():
    v = V.Verdict(accepted=True)
    assert v.accepted is True
    assert v.reason == ""
    assert v.retryable is False
    assert v.verifier is None


def test_verdict_is_frozen():
    v = V.Verdict(accepted=False, reason="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.reason = "y"  # type: ignore[misc]


def test_verdict_accepted_must_be_bool_for_run_verifier(tmp_path):
    task = _task()
    event = _ready({})

    def bad(task, result, home):
        return V.Verdict(accepted="yes")  # type: ignore[arg-type]

    out = V.run_verifier(lambda name: bad, task, event, tmp_path)
    assert out.accepted is False
    assert out.reason == "verifier returned an invalid verdict"
    assert out.retryable is False


def test_adapter_name_bounds():
    # valid: lowercase start, up to 64 chars total
    assert V.ADAPTER_NAME.match("a") is not None
    assert V.ADAPTER_NAME.match("synthetic") is not None
    assert V.ADAPTER_NAME.match("a" * 64) is not None
    # invalid: empty, uppercase start, too long, bad chars
    assert V.ADAPTER_NAME.match("") is None
    assert V.ADAPTER_NAME.match("Synthetic") is None
    assert V.ADAPTER_NAME.match("0abc") is None
    assert V.ADAPTER_NAME.match("a" * 65) is None
    assert V.ADAPTER_NAME.match("a-b") is None
    assert V.ADAPTER_NAME.match("a.b") is None


def test_adapter_verifier_rejects_bad_name_without_import():
    assert V.adapter_verifier("") is None
    assert V.adapter_verifier("Synthetic") is None
    assert V.adapter_verifier("a" * 65) is None
    assert V.adapter_verifier("has-dash") is None


def test_adapter_verifier_missing_module_returns_none():
    assert V.adapter_verifier("no_such_adapter_xyz") is None


def test_adapter_verifier_module_without_verify_returns_none(monkeypatch):
    mod = types.ModuleType("adapters.noverify_xyz")
    monkeypatch.setitem(sys.modules, "adapters.noverify_xyz", mod)
    assert V.adapter_verifier("noverify_xyz") is None


def test_adapter_verifier_returns_callable_when_verify_present(monkeypatch):
    mod = types.ModuleType("adapters.hasverify_xyz")

    def verify(task, result, home):
        return V.Verdict(True)

    mod.verify = verify
    monkeypatch.setitem(sys.modules, "adapters.hasverify_xyz", mod)
    assert V.adapter_verifier("hasverify_xyz") is verify


def test_verifier_identity_missing_version_gives_none():
    def verify(task, result, home):
        return V.Verdict(True)

    verify.__module__ = "no_such_module_xyz_123"
    verify.__qualname__ = "verify"
    ident = V.verifier_identity(verify)
    assert ident["kind"] == "adapter"
    assert ident["name"].endswith(".verify")
    assert ident["version"] is None
    assert ident["source_sha256"] is None


def test_verifier_identity_version_truncated_to_100(monkeypatch):
    mod = types.ModuleType("fakever_xyz")
    mod.VERIFIER_VERSION = "v" * 250
    monkeypatch.setitem(sys.modules, "fakever_xyz", mod)

    def verify(task, result, home):
        return V.Verdict(True)

    verify.__module__ = "fakever_xyz"
    ident = V.verifier_identity(verify)
    assert ident["version"] == "v" * 100


def test_verifier_identity_version_strified(monkeypatch):
    mod = types.ModuleType("fakever_int_xyz")
    mod.VERIFIER_VERSION = 2
    monkeypatch.setitem(sys.modules, "fakever_int_xyz", mod)

    def verify(task, result, home):
        return V.Verdict(True)

    verify.__module__ = "fakever_int_xyz"
    ident = V.verifier_identity(verify)
    assert ident["version"] == "2"


def test_rule_shape():
    rule = V._rule("worker_reported_failure", "synthetic")
    assert rule == {"kind": "courier_rule", "name": "worker_reported_failure", "adapter": "synthetic"}


def test_run_verifier_failure_outcome_uses_payload_retryable(tmp_path):
    task = _task(effect_class="non_idempotent")
    event = _ready({"outcome": "failure", "reason": "boom", "retryable": True})
    out = V.run_verifier(lambda name: (_ for _ in ()).throw(AssertionError("must not resolve")), task, event, tmp_path)
    assert out.accepted is False
    assert out.reason == "boom"
    assert out.retryable is True
    assert out.verifier["kind"] == "courier_rule"
    assert out.verifier["name"] == "worker_reported_failure"


def test_run_verifier_failure_falls_back_to_may_auto_retry(tmp_path):
    idem = V.run_verifier(
        lambda name: (_ for _ in ()).throw(AssertionError("must not resolve")),
        _task(effect_class="idempotent"),
        _ready({"outcome": "failure"}),
        tmp_path,
    )
    assert idem.retryable is True
    assert idem.reason == "worker reported failure"
    non = V.run_verifier(
        lambda name: (_ for _ in ()).throw(AssertionError("must not resolve")),
        _task(effect_class="non_idempotent"),
        _ready({"outcome": "failure"}),
        tmp_path,
    )
    assert non.retryable is False


def test_run_verifier_failure_reason_truncated_to_500(tmp_path):
    task = _task()
    event = _ready({"outcome": "failure", "reason": "r" * 900})
    out = V.run_verifier(lambda name: (_ for _ in ()).throw(AssertionError("must not resolve")), task, event, tmp_path)
    assert out.reason == "r" * 500


def test_run_verifier_resolve_raises_is_load_failed(tmp_path):
    def resolve(name):
        raise ImportError("broken")

    out = V.run_verifier(resolve, _task(), _ready({}), tmp_path)
    assert out.accepted is False
    assert out.retryable is False
    assert out.verifier["name"] == "verifier_load_failed"
    assert "ImportError" in out.reason


def test_run_verifier_no_verifier(tmp_path):
    out = V.run_verifier(lambda name: None, _task(), _ready({}), tmp_path)
    assert out.accepted is False
    assert out.verifier["name"] == "no_verifier"


def test_run_verifier_raising_verifier_fails_closed(tmp_path):
    def bad(task, result, home):
        raise RuntimeError("oops")

    out = V.run_verifier(lambda name: bad, _task(), _ready({}), tmp_path)
    assert out.accepted is False
    assert out.reason == "verifier raised RuntimeError"
    assert out.verifier["kind"] == "adapter"


def test_run_verifier_success_coerces_reason_and_retryable(tmp_path: Path):
    def good(task, result, home):
        return V.Verdict(accepted=True, reason="x" * 900, retryable=1)  # type: ignore[arg-type]

    out = V.run_verifier(lambda name: good, _task(), _ready({}), tmp_path)
    assert out.accepted is True
    assert out.reason == "x" * 500
    assert out.retryable is True
    assert out.verifier["kind"] == "adapter"


def test_source_sha256_none_for_unknown_module():
    assert V._source_sha256("no_such_module_xyz_123") is None
