"""P9 hardening for courier_core.verification: adapter-name gating.

Tests only; no behavior change. Pins the fail-closed resolution edges of
``adapter_verifier`` (invalid names never reach the import system, unknown
adapters resolve to None, nested import failures propagate) plus the offline
identity helpers (``verifier_identity`` / ``_source_sha256``).
"""

import sys
import types

from courier_core import verification
from courier_core.verification import (
    adapter_verifier,
    verifier_identity,
    _source_sha256,
)


def _recorder(result=None, error=None):
    calls = []

    def fake(name):
        calls.append(name)
        if error is not None:
            raise error
        return result

    fake.calls = calls
    return fake


# -- adapter name gating: invalid names never import ---------------------------

def test_empty_name_returns_none_without_import(monkeypatch):
    fake = _recorder(result=object())
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("") is None
    assert fake.calls == []


def test_uppercase_name_returns_none_without_import(monkeypatch):
    fake = _recorder(result=object())
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("Synthetic") is None
    assert fake.calls == []


def test_leading_digit_returns_none_without_import(monkeypatch):
    fake = _recorder(result=object())
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("1abc") is None
    assert fake.calls == []


def test_hyphen_dot_and_slash_return_none_without_import(monkeypatch):
    fake = _recorder(result=object())
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("my-adapter") is None
    assert adapter_verifier("my.adapter") is None
    assert adapter_verifier("my/adapter") is None
    assert fake.calls == []


def test_overlong_name_returns_none_without_import(monkeypatch):
    fake = _recorder(result=object())
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("a" * 65) is None
    assert fake.calls == []


def test_max_length_name_reaches_import(monkeypatch):
    fake = _recorder(result=types.SimpleNamespace(verify=lambda *a: None))
    monkeypatch.setattr("importlib.import_module", fake)
    adapter_verifier("a" * 64)
    assert fake.calls == ["adapters." + "a" * 64]


# -- resolution: missing vs broken adapters ------------------------------------

def test_unknown_adapter_returns_none():
    assert adapter_verifier("no_such_adapter_xyz") is None


def test_module_without_verify_returns_none(monkeypatch):
    fake = _recorder(result=types.SimpleNamespace())
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("synthetic") is None
    assert fake.calls == ["adapters.synthetic"]


def test_non_callable_verify_returns_none(monkeypatch):
    fake = _recorder(result=types.SimpleNamespace(verify="not-a-function"))
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("synthetic") is None


def test_callable_verify_is_returned(monkeypatch):
    def verify(task, result, home):
        raise AssertionError("must not be called")

    fake = _recorder(result=types.SimpleNamespace(verify=verify))
    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("synthetic") is verify


def test_nested_import_failure_propagates(monkeypatch):
    err = ModuleNotFoundError("inner failure")
    err.name = "adapters.synthetic.dependency"
    fake = _recorder(error=err)
    monkeypatch.setattr("importlib.import_module", fake)
    try:
        adapter_verifier("synthetic")
    except ModuleNotFoundError:
        return
    raise AssertionError("nested ModuleNotFoundError must propagate")


def test_real_synthetic_verifier_resolves():
    from adapters import synthetic

    assert adapter_verifier("synthetic") is synthetic.verify


# -- verifier_identity / _source_sha256 (offline) -------------------------------

def test_identity_for_unknown_module_has_no_version_or_digest():
    def verify(task, result, home):
        raise AssertionError("must not be called")

    verify.__module__ = "no.such.module.xyz"
    identity = verifier_identity(verify)
    assert identity["kind"] == "adapter"
    assert identity["name"].endswith(".verify")
    assert identity["version"] is None
    assert identity["source_sha256"] is None


def test_identity_truncates_long_version(monkeypatch):
    stub = types.SimpleNamespace(
        __file__="missing.py", VERIFIER_VERSION="v" * 200)

    def verify(task, result, home):
        raise AssertionError("must not be called")

    verify.__module__ = "stub_adapter_module_xyz"
    monkeypatch.setitem(sys.modules, "stub_adapter_module_xyz", stub)
    identity = verifier_identity(verify)
    assert identity["version"] == "v" * 100
    assert identity["source_sha256"] is None


def test_identity_stringifies_non_string_version(monkeypatch):
    stub = types.SimpleNamespace(__file__="missing.py", VERIFIER_VERSION=2)

    def verify(task, result, home):
        raise AssertionError("must not be called")

    verify.__module__ = "stub_adapter_version_xyz"
    monkeypatch.setitem(sys.modules, "stub_adapter_version_xyz", stub)
    assert verifier_identity(verify)["version"] == "2"


def test_source_digest_unknown_module_is_none():
    assert _source_sha256("no.such.module.xyz") is None


def test_source_digest_missing_file_is_none(monkeypatch):
    stub = types.SimpleNamespace(__file__="missing.py")
    monkeypatch.setitem(sys.modules, "stub_adapter_digest_xyz", stub)
    assert _source_sha256("stub_adapter_digest_xyz") is None


def test_source_digest_of_real_module_is_stable_hex():
    first = _source_sha256("courier_core.verification")
    second = _source_sha256("courier_core.verification")
    assert first == second
    assert isinstance(first, str) and len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


def test_adapter_name_pattern_allows_underscores_and_digits(monkeypatch):
    seen = []

    def marker(task, result, home):
        raise AssertionError("must not be called")

    def fake(name):
        seen.append(name)
        return types.SimpleNamespace(verify=marker)

    monkeypatch.setattr("importlib.import_module", fake)
    assert adapter_verifier("a1_b2") is marker
    assert seen == ["adapters.a1_b2"]
    assert verification.ADAPTER_NAME.match("a1_b2") is not None
