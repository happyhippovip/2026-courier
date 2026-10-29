"""P9 hardening for courier_core.verification: identity + loader pins.

Focused on who-decided provenance (verifier_identity), the file digest
helper (_source_sha256) and the adapter loader (adapter_verifier). These
decide what is recorded about a verdict, never whether a task passes, so
every case here is offline and leaves behavior unchanged.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import types

import pytest

from courier_core import verification as v
from courier_core.verification import (
    Verdict,
    _rule,
    _source_sha256,
    adapter_verifier,
    verifier_identity,
)


def test_verdict_defaults_are_fail_closed():
    verdict = Verdict(accepted=False)
    assert verdict.accepted is False
    assert verdict.reason == ""
    assert verdict.retryable is False
    assert verdict.verifier is None


def test_rule_envelope_shape():
    assert _rule("no_verifier", "synthetic") == {
        "kind": "courier_rule",
        "name": "no_verifier",
        "adapter": "synthetic",
    }


@pytest.mark.parametrize("bad", [
    "",
    "A",
    "0abc",
    "_lead",
    "has-hyphen",
    "has.dot",
    "has space",
    "UPPER",
    "a" * 65,
    "synthetic!",  # trailing punctuation
])
def test_adapter_verifier_rejects_bad_names_without_import(monkeypatch, bad):
    called = []

    def _fail(name):
        called.append(name)
        raise AssertionError("import must not run for an invalid adapter name")

    monkeypatch.setattr(importlib, "import_module", _fail)
    assert adapter_verifier(bad) is None
    assert called == []


def test_adapter_verifier_returns_none_when_adapter_missing(monkeypatch):
    def _missing(name):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(importlib, "import_module", _missing)
    assert adapter_verifier("ghost_adapter") is None


def test_adapter_verifier_returns_none_when_package_missing(monkeypatch):
    def _no_package(name):
        raise ModuleNotFoundError("No module named 'adapters'", name="adapters")

    monkeypatch.setattr(importlib, "import_module", _no_package)
    assert adapter_verifier("ghost_adapter") is None


def test_adapter_verifier_reraise_unrelated_missing_dependency(monkeypatch):
    def _broken(name):
        raise ModuleNotFoundError("No module named 'some_dep'", name="some_dep")

    monkeypatch.setattr(importlib, "import_module", _broken)
    with pytest.raises(ModuleNotFoundError):
        adapter_verifier("ghost_adapter")


def test_adapter_verifier_does_not_swallow_unexpected_import_errors(monkeypatch):
    def _boom(name):
        raise RuntimeError("import side effect failed")

    monkeypatch.setattr(importlib, "import_module", _boom)
    with pytest.raises(RuntimeError):
        adapter_verifier("ghost_adapter")


def _fake_adapter_module(monkeypatch, adapter, **attrs):
    module = types.ModuleType(f"adapters.{adapter}")
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, f"adapters.{adapter}", module)
    return module


def test_adapter_verifier_returns_none_without_verify_callable(monkeypatch):
    _fake_adapter_module(monkeypatch, "fake_no_verify")
    assert adapter_verifier("fake_no_verify") is None


def test_adapter_verifier_returns_none_when_verify_not_callable(monkeypatch):
    _fake_adapter_module(monkeypatch, "fake_bad_verify", verify="not-a-function")
    assert adapter_verifier("fake_bad_verify") is None


def test_adapter_verifier_returns_callable_verify(monkeypatch):
    def verify(task, result, home):
        return Verdict(True, "ok")

    _fake_adapter_module(monkeypatch, "fake_good_verify", verify=verify)
    assert adapter_verifier("fake_good_verify") is verify


def test_source_sha256_matches_file_bytes(monkeypatch, tmp_path):
    target = tmp_path / "mod_a.py"
    target.write_bytes(b"print('hello')\n")
    v._SOURCE_DIGESTS.clear()
    monkeypatch.setitem(sys.modules, "fake_mod_a", types.SimpleNamespace(__file__=str(target)))
    expected = hashlib.sha256(b"print('hello')\n").hexdigest()
    assert _source_sha256("fake_mod_a") == expected
    # Second call hits the cache but stays correct.
    assert _source_sha256("fake_mod_a") == expected


def test_source_sha256_is_none_without_module_or_file(monkeypatch):
    v._SOURCE_DIGESTS.clear()
    monkeypatch.delitem(sys.modules, "no_such_module_xyz", raising=False)
    assert _source_sha256("no_such_module_xyz") is None
    monkeypatch.setitem(sys.modules, "fake_nofile", types.SimpleNamespace())
    assert _source_sha256("fake_nofile") is None


def test_source_sha256_is_none_when_file_unreadable(monkeypatch, tmp_path):
    missing = tmp_path / "gone.py"
    v._SOURCE_DIGESTS.clear()
    monkeypatch.setitem(sys.modules, "fake_gone", types.SimpleNamespace(__file__=str(missing)))
    assert _source_sha256("fake_gone") is None


def test_source_sha256_changes_when_file_content_changes(monkeypatch, tmp_path):
    target = tmp_path / "mod_b.py"
    target.write_bytes(b"v1")
    v._SOURCE_DIGESTS.clear()
    monkeypatch.setitem(sys.modules, "fake_mod_b", types.SimpleNamespace(__file__=str(target)))
    first = _source_sha256("fake_mod_b")
    target.write_bytes(b"v1-plus-more-bytes")
    second = _source_sha256("fake_mod_b")
    assert first != second
    assert second == hashlib.sha256(b"v1-plus-more-bytes").hexdigest()


def _verify_fn_with_module(monkeypatch, module_name, **module_attrs):
    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = module_name
    module = types.ModuleType(module_name)
    for key, value in module_attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, module_name, module)
    return verify


def test_verifier_identity_without_version_or_file(monkeypatch):
    verify = _verify_fn_with_module(monkeypatch, "fake_ident_plain")
    identity = verifier_identity(verify)
    assert identity["kind"] == "adapter"
    assert identity["name"] == f"fake_ident_plain.{verify.__qualname__}"
    assert identity["version"] is None
    assert identity["source_sha256"] is None


def test_verifier_identity_coerces_int_version(monkeypatch):
    verify = _verify_fn_with_module(monkeypatch, "fake_ident_int", VERIFIER_VERSION=3)
    assert verifier_identity(verify)["version"] == "3"


def test_verifier_identity_truncates_long_version(monkeypatch):
    verify = _verify_fn_with_module(monkeypatch, "fake_ident_long", VERIFIER_VERSION="x" * 200)
    assert verifier_identity(verify)["version"] == "x" * 100


def test_verifier_identity_records_file_digest(monkeypatch, tmp_path):
    target = tmp_path / "ver_mod.py"
    target.write_bytes(b"verify-code")
    v._SOURCE_DIGESTS.clear()
    verify = _verify_fn_with_module(
        monkeypatch, "fake_ident_file", VERIFIER_VERSION="7", __file__=str(target))
    identity = verifier_identity(verify)
    assert identity["version"] == "7"
    assert identity["source_sha256"] == hashlib.sha256(b"verify-code").hexdigest()
