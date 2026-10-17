"""P9 hardening: courier_core.verification source-digest + verifier identity.

Tests only; no behavior change. Covers the offline provenance helpers:

- ``_source_sha256``: unknown module, module without ``__file__``,
  unreadable path, directory path, real digest value, digest shape,
  and re-read after the file changes.
- ``verifier_identity``: name wiring, missing ``__module__`` fallback,
  version absent / coerced / truncated, and ``source_sha256`` wiring.

No network, no credentials, no subprocesses. Temporary modules are
injected into ``sys.modules`` under unique names and removed again;
temporary files live under pytest's ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import sys
import types

import courier_core.verification as verification
from courier_core.verification import _source_sha256, verifier_identity


def _fake_module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _drop_fake_module(name: str) -> None:
    sys.modules.pop(name, None)
    for key in [k for k in verification._SOURCE_DIGESTS if k[0] and name in str(k[0])]:
        verification._SOURCE_DIGESTS.pop(key, None)


def test_source_sha256_unknown_module_is_none():
    assert _source_sha256("no.such.module.anywhere") is None


def test_source_sha256_module_without_file_is_none():
    name = "p9_srcdigest_no_file_probe"
    _fake_module(name)
    try:
        assert getattr(sys.modules[name], "__file__", None) is None
        assert _source_sha256(name) is None
    finally:
        _drop_fake_module(name)


def test_source_sha256_missing_file_is_none(tmp_path):
    name = "p9_srcdigest_missing_probe"
    _fake_module(name, __file__=str(tmp_path / "gone.py"))
    try:
        assert _source_sha256(name) is None
    finally:
        _drop_fake_module(name)


def test_source_sha256_directory_is_none(tmp_path):
    name = "p9_srcdigest_dir_probe"
    _fake_module(name, __file__=str(tmp_path))
    try:
        assert _source_sha256(name) is None
    finally:
        _drop_fake_module(name)


def test_source_sha256_matches_file_bytes(tmp_path):
    target = tmp_path / "mod_bytes.py"
    target.write_bytes(b"print('hello')\n")
    name = "p9_srcdigest_bytes_probe"
    _fake_module(name, __file__=str(target))
    try:
        assert _source_sha256(name) == hashlib.sha256(b"print('hello')\n").hexdigest()
    finally:
        _drop_fake_module(name)


def test_source_sha256_digest_shape_is_hex64(tmp_path):
    target = tmp_path / "mod_shape.py"
    target.write_bytes(b"x = 1\n")
    name = "p9_srcdigest_shape_probe"
    _fake_module(name, __file__=str(target))
    try:
        digest = _source_sha256(name)
        assert isinstance(digest, str) and len(digest) == 64
        int(digest, 16)
    finally:
        _drop_fake_module(name)


def test_source_sha256_same_content_is_stable(tmp_path):
    target = tmp_path / "mod_stable.py"
    target.write_bytes(b"stable = True\n")
    name = "p9_srcdigest_stable_probe"
    _fake_module(name, __file__=str(target))
    try:
        assert _source_sha256(name) == _source_sha256(name)
    finally:
        _drop_fake_module(name)


def test_source_sha256_rereads_after_change(tmp_path):
    target = tmp_path / "mod_change.py"
    target.write_bytes(b"v = 1\n")
    name = "p9_srcdigest_change_probe"
    _fake_module(name, __file__=str(target))
    try:
        first = _source_sha256(name)
        target.write_bytes(b"v = 2 with more bytes so size differs\n")
        second = _source_sha256(name)
        assert first != second
        assert second == hashlib.sha256(target.read_bytes()).hexdigest()
    finally:
        _drop_fake_module(name)


def test_source_sha256_real_module_matches_disk():
    digest = _source_sha256("courier_core.verification")
    assert isinstance(digest, str) and len(digest) == 64
    with open(verification.__file__, "rb") as handle:
        assert digest == hashlib.sha256(handle.read()).hexdigest()


def test_identity_names_adapter_function():
    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = "some_adapter_mod"
    identity = verifier_identity(sample_verify)
    assert identity["kind"] == "adapter"
    assert identity["name"] == f"some_adapter_mod.{sample_verify.__qualname__}"
    assert identity["name"].endswith(".sample_verify")


def test_identity_version_none_when_module_has_no_version():
    name = "p9_srcdigest_noversion_probe"

    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = name
    _fake_module(name)
    try:
        identity = verifier_identity(sample_verify)
        assert identity["version"] is None
    finally:
        _drop_fake_module(name)


def test_identity_version_coerced_to_str():
    name = "p9_srcdigest_intversion_probe"

    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = name
    _fake_module(name, VERIFIER_VERSION=3)
    try:
        assert verifier_identity(sample_verify)["version"] == "3"
    finally:
        _drop_fake_module(name)


def test_identity_version_truncated_to_100():
    name = "p9_srcdigest_longversion_probe"

    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = name
    _fake_module(name, VERIFIER_VERSION="v" * 250)
    try:
        version = verifier_identity(sample_verify)["version"]
        assert version == "v" * 100
    finally:
        _drop_fake_module(name)


def test_identity_missing_module_falls_back():
    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = None
    identity = verifier_identity(sample_verify)
    assert identity["name"].startswith("?.")
    assert identity["version"] is None
    assert identity["source_sha256"] is None


def test_identity_source_digest_wired_to_helper(tmp_path):
    target = tmp_path / "adapt_mod.py"
    target.write_bytes(b"VERIFIER_VERSION = 1\n")
    name = "p9_srcdigest_wired_probe"

    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = name
    _fake_module(name, __file__=str(target), VERIFIER_VERSION=1)
    try:
        identity = verifier_identity(sample_verify)
        assert identity["source_sha256"] == _source_sha256(name)
        assert identity["source_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    finally:
        _drop_fake_module(name)


def test_identity_source_none_when_no_file():
    name = "p9_srcdigest_nofile_identity_probe"

    def sample_verify(task, result, home):  # pragma: no cover - identity only
        raise AssertionError("must not be called")

    sample_verify.__module__ = name
    _fake_module(name)
    try:
        assert verifier_identity(sample_verify)["source_sha256"] is None
    finally:
        _drop_fake_module(name)
