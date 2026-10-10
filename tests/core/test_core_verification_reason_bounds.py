"""P9 hardening for courier_core.verification: reason and version bounds.

Tests-only. No behavior change. Offline: no network, no credentials.
Covers the truncation and fail-closed bounds the controller depends on:
reason capped at 500 chars, verifier version capped at 100 chars,
adapter-name allowlist, loader/identity edges, and run_verifier coercion.
"""

from __future__ import annotations

import hashlib
import sys
import types
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core import verification as V
from courier_core.verification import (
    ADAPTER_NAME,
    Verdict,
    _rule,
    _source_sha256,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)


def _task(adapter: str = "synthetic", effect_class: str = "idempotent") -> TaskState:
    return TaskState(
        task_id="t1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=6,
        timeout_s=None,
    )


def _result(payload: dict, task_id: str = "t1") -> Event:
    return Event(
        type=EventType.RESULT_READY,
        task_id=task_id,
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=payload,
    )


def _success(payload_extra: dict | None = None) -> Event:
    payload = {"artifacts": [], "outcome": "success"}
    if payload_extra:
        payload.update(payload_extra)
    return _result(payload)


# --- Verdict value object ---

def test_verdict_defaults():
    v = Verdict(False)
    assert v.accepted is False
    assert v.reason == ""
    assert v.retryable is False
    assert v.verifier is None


def test_verdict_is_frozen():
    v = Verdict(True, "ok", True)
    with pytest.raises(FrozenInstanceError):
        v.reason = "mut"  # type: ignore[misc]


# --- ADAPTER_NAME allowlist (regex pins) ---

@pytest.mark.parametrize("name", ["a", "synthetic", "a1_", "z" + "0" * 62 + "_"])
def test_adapter_name_accepts_wellformed(name):
    assert ADAPTER_NAME.match(name) is not None


@pytest.mark.parametrize("name", [
    "", "A", "0abc", "_abc", "-abc", "has-hyphen", "has space",
    "UPPER", "a" * 65, "x" * 100, "synthetic!",
])
def test_adapter_name_rejects_malformed(name):
    assert ADAPTER_NAME.match(name) is None


@pytest.mark.parametrize("name", ["", "A", "0abc", "has-hyphen", "a" * 65])
def test_adapter_verifier_returns_none_for_bad_name_without_import(name, monkeypatch):
    called = []

    def _fail_import(_name):
        called.append(_name)
        raise AssertionError("must not import for a bad adapter name")

    monkeypatch.setattr(V.importlib, "import_module", _fail_import)
    assert adapter_verifier(name) is None
    assert called == []


# --- adapter_verifier loader edges ---

def test_adapter_verifier_returns_none_for_missing_adapter():
    assert adapter_verifier("no_such_adapter_xyz") is None


def test_adapter_verifier_returns_none_when_no_verify_attr(monkeypatch):
    mod = types.ModuleType("adapters.fake_no_verify_attr")
    monkeypatch.setitem(sys.modules, "adapters.fake_no_verify_attr", mod)
    assert adapter_verifier("fake_no_verify_attr") is None


def test_adapter_verifier_returns_none_when_verify_not_callable(monkeypatch):
    mod = types.ModuleType("adapters.fake_not_callable")
    mod.verify = "not-a-function"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adapters.fake_not_callable", mod)
    assert adapter_verifier("fake_not_callable") is None


def test_adapter_verifier_returns_callable_when_present(monkeypatch):
    def _verify(task, result, home):
        return Verdict(True, "ok")

    mod = types.ModuleType("adapters.fake_has_verify")
    mod.verify = _verify  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "adapters.fake_has_verify", mod)
    assert adapter_verifier("fake_has_verify") is _verify


def test_adapter_verifier_reraises_nested_import_error(monkeypatch):
    def _boom(_name):
        raise ModuleNotFoundError("no module named 'some_dep'", name="some_dep")

    monkeypatch.setattr(V.importlib, "import_module", _boom)
    with pytest.raises(ModuleNotFoundError):
        adapter_verifier("synthetic")


# --- _source_sha256 edges ---

def test_source_sha256_none_for_unknown_module():
    assert _source_sha256("no.such.module.xyz") is None


def test_source_sha256_none_when_no_file(monkeypatch):
    mod = types.ModuleType("fake_nofile_mod_xyz")
    monkeypatch.setitem(sys.modules, "fake_nofile_mod_xyz", mod)
    assert _source_sha256("fake_nofile_mod_xyz") is None


def test_source_sha256_none_on_oserror(monkeypatch, tmp_path):
    mod = types.ModuleType("fake_missing_file_mod")
    mod.__file__ = str(tmp_path / "does-not-exist.py")
    monkeypatch.setitem(sys.modules, "fake_missing_file_mod", mod)
    assert _source_sha256("fake_missing_file_mod") is None


def test_source_sha256_digest_and_cache(monkeypatch, tmp_path):
    V._SOURCE_DIGESTS.clear()
    target = tmp_path / "fake_mod.py"
    target.write_bytes(b"VERIFIER_VERSION = '1'\n")
    mod = types.ModuleType("fake_digest_mod")
    mod.__file__ = str(target)
    monkeypatch.setitem(sys.modules, "fake_digest_mod", mod)
    first = _source_sha256("fake_digest_mod")
    assert first == hashlib.sha256(b"VERIFIER_VERSION = '1'\n").hexdigest()
    second = _source_sha256("fake_digest_mod")
    assert second == first
    assert len(V._SOURCE_DIGESTS) == 1


# --- verifier_identity bounds ---

def test_verifier_identity_version_none_when_absent(monkeypatch):
    def _verify(task, result, home):
        return Verdict(True, "ok")

    _verify.__module__ = "fake_ident_no_version"
    _verify.__qualname__ = "verify_fn"
    mod = types.ModuleType("fake_ident_no_version")
    monkeypatch.setitem(sys.modules, "fake_ident_no_version", mod)
    ident = verifier_identity(_verify)
    assert ident["kind"] == "adapter"
    assert ident["name"] == "fake_ident_no_version.verify_fn"
    assert ident["version"] is None


def test_verifier_identity_version_truncated_to_100(monkeypatch):
    def _verify(task, result, home):
        return Verdict(True, "ok")

    _verify.__module__ = "fake_ident_long_version"
    _verify.__qualname__ = "my_verify"
    mod = types.ModuleType("fake_ident_long_version")
    mod.VERIFIER_VERSION = "v" * 150
    monkeypatch.setitem(sys.modules, "fake_ident_long_version", mod)
    ident = verifier_identity(_verify)
    assert ident["version"] == "v" * 100


def test_verifier_identity_version_coerced_to_str(monkeypatch):
    def _verify(task, result, home):
        return Verdict(True, "ok")

    _verify.__module__ = "fake_ident_int_version"
    mod = types.ModuleType("fake_ident_int_version")
    mod.VERIFIER_VERSION = 123
    monkeypatch.setitem(sys.modules, "fake_ident_int_version", mod)
    assert verifier_identity(_verify)["version"] == "123"


def test_verifier_identity_missing_module_name():
    def _verify(task, result, home):
        return Verdict(True, "ok")

    _verify.__module__ = None  # type: ignore[assignment]
    ident = verifier_identity(_verify)
    assert ident["name"].startswith("?.")


def test_rule_shape():
    assert _rule("no_verifier", "synthetic") == {
        "kind": "courier_rule", "name": "no_verifier", "adapter": "synthetic",
    }


# --- run_verifier: worker-reported failure path ---

def test_worker_failure_uses_explicit_reason_and_retryable(tmp_path):
    out = run_verifier(
        lambda _a: (_ for _ in ()).throw(AssertionError("must not resolve on failure")),
        _task(effect_class="idempotent"),
        _result({"artifacts": [], "outcome": "failure", "reason": "boom", "retryable": True}),
        tmp_path,
    )
    assert out.accepted is False
    assert out.reason == "boom"
    assert out.retryable is True
    assert out.verifier == {"kind": "courier_rule", "name": "worker_reported_failure", "adapter": "synthetic"}


def test_worker_failure_defaults_reason_when_missing_or_empty(tmp_path):
    for payload in ({"artifacts": [], "outcome": "failure"}, {"artifacts": [], "outcome": "failure", "reason": ""}):
        out = run_verifier(lambda _a: None, _task(), _result(payload), tmp_path)
        assert out.reason == "worker reported failure"
        assert out.accepted is False


def test_worker_failure_reason_truncated_to_500(tmp_path):
    out = run_verifier(
        lambda _a: None, _task(),
        _result({"artifacts": [], "outcome": "failure", "reason": "x" * 600}),
        tmp_path,
    )
    assert out.reason == "x" * 500


def test_worker_failure_non_string_reason_coerced_and_truncated(tmp_path):
    out = run_verifier(
        lambda _a: None, _task(),
        _result({"artifacts": [], "outcome": "failure", "reason": 123456}),
        tmp_path,
    )
    assert out.reason == "123456"


@pytest.mark.parametrize("effect_class,expected", [("idempotent", True), ("non_idempotent", False), ("weird", False)])
def test_worker_failure_retryable_fallback_by_effect_class(tmp_path, effect_class, expected):
    out = run_verifier(
        lambda _a: None, _task(effect_class=effect_class),
        _result({"artifacts": [], "outcome": "failure"}),
        tmp_path,
    )
    assert out.retryable is expected


def test_worker_failure_explicit_retryable_overrides_fallback(tmp_path):
    out = run_verifier(
        lambda _a: None, _task(effect_class="idempotent"),
        _result({"artifacts": [], "outcome": "failure", "retryable": False}),
        tmp_path,
    )
    assert out.retryable is False
    out2 = run_verifier(
        lambda _a: None, _task(effect_class="non_idempotent"),
        _result({"artifacts": [], "outcome": "failure", "retryable": True}),
        tmp_path,
    )
    assert out2.retryable is True


def test_non_success_payload_treated_as_failure(tmp_path):
    # Defensive pin: anything whose outcome is not "success" fails closed,
    # even a non-RESULT_READY event carrying no outcome at all.
    other = Event(
        type=EventType.TASK_PROGRESS,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        payload={},
    )
    out = run_verifier(
        lambda _a: (_ for _ in ()).throw(AssertionError("must not resolve without success")),
        _task(), other, tmp_path,
    )
    assert out.accepted is False
    assert out.verifier["name"] == "worker_reported_failure"


# --- run_verifier: resolution edges ---

def test_resolve_raises_is_fail_closed(tmp_path):
    def _boom(_adapter):
        raise ImportError("broken")

    out = run_verifier(_boom, _task(adapter="synthetic"), _success(), tmp_path)
    assert out.accepted is False
    assert out.retryable is False
    assert out.verifier == {"kind": "courier_rule", "name": "verifier_load_failed", "adapter": "synthetic"}
    assert "ImportError" in out.reason


def test_no_verifier_is_fail_closed(tmp_path):
    out = run_verifier(lambda _a: None, _task(adapter="synthetic"), _success(), tmp_path)
    assert out.accepted is False
    assert out.retryable is False
    assert out.verifier == {"kind": "courier_rule", "name": "no_verifier", "adapter": "synthetic"}
    assert "synthetic" in out.reason


def test_verifier_raises_is_fail_closed_with_identity(tmp_path, monkeypatch):
    def _bad(task, result, home):
        raise RuntimeError("kaput")

    _bad.__module__ = "fake_raise_mod"
    _bad.__qualname__ = "bad_verify"
    monkeypatch.setitem(sys.modules, "fake_raise_mod", types.ModuleType("fake_raise_mod"))
    out = run_verifier(lambda _a: _bad, _task(), _success(), tmp_path)
    assert out.accepted is False
    assert out.retryable is False
    assert out.reason == "verifier raised RuntimeError"
    assert out.verifier["kind"] == "adapter"
    assert out.verifier["name"] == "fake_raise_mod.bad_verify"


@pytest.mark.parametrize("bad", ["yes", {"accepted": True}, 123, None])
def test_invalid_verdict_shape_is_fail_closed(tmp_path, monkeypatch, bad):
    def _weird(task, result, home):
        return bad

    _weird.__module__ = "fake_weird_mod"
    monkeypatch.setitem(sys.modules, "fake_weird_mod", types.ModuleType("fake_weird_mod"))
    out = run_verifier(lambda _a: _weird, _task(), _success(), tmp_path)
    assert out.accepted is False
    assert out.reason == "verifier returned an invalid verdict"
    assert out.retryable is False


def test_verdict_accepted_not_bool_is_invalid(tmp_path, monkeypatch):
    bad = Verdict("yes")  # type: ignore[arg-type]

    def _weird(task, result, home):
        return bad

    _weird.__module__ = "fake_bool_mod"
    monkeypatch.setitem(sys.modules, "fake_bool_mod", types.ModuleType("fake_bool_mod"))
    out = run_verifier(lambda _a: _weird, _task(), _success(), tmp_path)
    assert out.accepted is False
    assert out.reason == "verifier returned an invalid verdict"


# --- run_verifier: valid-verdict coercion bounds ---

def test_valid_verdict_reason_truncated_to_500(tmp_path, monkeypatch):
    def _ok(task, result, home):
        return Verdict(True, "y" * 600, True)

    _ok.__module__ = "fake_ok_mod"
    monkeypatch.setitem(sys.modules, "fake_ok_mod", types.ModuleType("fake_ok_mod"))
    out = run_verifier(lambda _a: _ok, _task(), _success(), tmp_path)
    assert out.accepted is True
    assert out.reason == "y" * 500
    assert out.retryable is True
    assert out.verifier["kind"] == "adapter"


@pytest.mark.parametrize("given,expected", [(1, True), ("yes", True), ("", False), (None, False), (0, False), ([], False)])
def test_valid_verdict_retryable_coerced_to_bool(tmp_path, monkeypatch, given, expected):
    def _ok(task, result, home):
        return Verdict(True, "ok", given)

    _ok.__module__ = "fake_coerce_mod"
    monkeypatch.setitem(sys.modules, "fake_coerce_mod", types.ModuleType("fake_coerce_mod"))
    out = run_verifier(lambda _a: _ok, _task(), _success(), tmp_path)
    assert out.retryable is expected


def test_valid_verdict_non_string_reason_coerced(tmp_path, monkeypatch):
    def _ok(task, result, home):
        return Verdict(True, 123, False)  # type: ignore[arg-type]

    _ok.__module__ = "fake_reason_mod"
    monkeypatch.setitem(sys.modules, "fake_reason_mod", types.ModuleType("fake_reason_mod"))
    out = run_verifier(lambda _a: _ok, _task(), _success(), tmp_path)
    assert out.reason == "123"


def test_valid_verdict_overwrites_adapter_verifier_field(tmp_path, monkeypatch):
    def _ok(task, result, home):
        return Verdict(True, "ok", False, verifier={"kind": "spoof"})

    _ok.__module__ = "fake_spoof_mod"
    _ok.__qualname__ = "ok_verify"
    monkeypatch.setitem(sys.modules, "fake_spoof_mod", types.ModuleType("fake_spoof_mod"))
    out = run_verifier(lambda _a: _ok, _task(), _success(), tmp_path)
    assert out.verifier == {
        "kind": "adapter",
        "name": "fake_spoof_mod.ok_verify",
        "version": None,
        "source_sha256": None,
    }


def test_home_path_passed_through_to_verifier(tmp_path):
    seen = {}

    def _ok(task, result, home):
        seen["home"] = home
        return Verdict(True, "ok")

    _ok.__module__ = "fake_home_mod"
    sys.modules.setdefault("fake_home_mod", types.ModuleType("fake_home_mod"))
    try:
        out = run_verifier(lambda _a: _ok, _task(), _success(), tmp_path)
    finally:
        sys.modules.pop("fake_home_mod", None)
    assert out.accepted is True
    assert Path(seen["home"]) == tmp_path
