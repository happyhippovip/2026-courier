"""P9 offline pins for courier_core.verification (resolve + fail-closed rules).

Tests only; no behavior change. Covers the parts of the verifier hand-off
that need no network, no credentials and no real adapters:

- adapter_verifier: name gate, missing/nameless verifiers, error propagation
- verifier_identity / _source_sha256: shape, version bounds, digest behavior
- run_verifier: worker-reported failure rule, resolve gate, and the
  fail-closed wrapping of an adapter verdict (invalid verdicts, reason
  truncation, retryable coercion, identity stamping)
"""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from courier_core import verification
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    Verdict,
    _source_sha256,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)


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
    )


def make_result(outcome="success", **extra):
    payload = {"artifacts": [], "outcome": outcome}
    payload.update(extra)
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=payload,
    )


def install_fake_adapter(monkeypatch, name, **attrs):
    module = types.ModuleType(f"adapters.{name}")
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, f"adapters.{name}", module)
    return module


# --- adapter_verifier: name gate -------------------------------------------


@pytest.mark.parametrize("bad", ["", "Bad", "a-b", "a b", "0abc", "a" * 65, "UPPER"])
def test_invalid_adapter_names_return_none_without_importing(bad):
    with mock.patch.object(verification.importlib, "import_module") as importer:
        assert adapter_verifier(bad) is None
        importer.assert_not_called()


def test_missing_adapter_module_returns_none():
    assert adapter_verifier("no_such_adapter_xyz") is None


def test_module_without_verify_returns_none():
    # adapters.spreadsheet ships with no verify function.
    assert adapter_verifier("spreadsheet") is None


def test_non_callable_verify_returns_none(monkeypatch):
    install_fake_adapter(monkeypatch, "fake_noncall", verify=42)
    assert adapter_verifier("fake_noncall") is None


def test_synthetic_adapter_returns_callable():
    verify = adapter_verifier("synthetic")
    assert callable(verify)


def test_nested_missing_dependency_reraises():
    with mock.patch.object(
        verification.importlib,
        "import_module",
        side_effect=ModuleNotFoundError("No module named 'dep_xyz'", name="dep_xyz"),
    ):
        with pytest.raises(ModuleNotFoundError):
            adapter_verifier("probe")


def test_unexpected_import_error_propagates():
    with mock.patch.object(
        verification.importlib, "import_module", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError):
            adapter_verifier("probe")


# --- verifier_identity / _source_sha256 ------------------------------------


def test_identity_shape_for_real_verifier():
    verify = adapter_verifier("synthetic")
    identity = verifier_identity(verify)
    assert identity["kind"] == "adapter"
    assert identity["name"].endswith(".verify")
    assert identity["version"] == "1"
    digest = identity["source_sha256"]
    assert isinstance(digest, str) and len(digest) == 64


def test_identity_with_missing_module_name():
    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = None
    identity = verifier_identity(verify)
    assert identity["name"].startswith("?.")
    assert identity["version"] is None


def test_version_truncated_to_100_chars(monkeypatch):
    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = "adapters.fake_ver"
    module = install_fake_adapter(monkeypatch, "fake_ver")
    module.VERIFIER_VERSION = "v" * 200
    assert verifier_identity(verify)["version"] == "v" * 100


def test_non_string_version_coerced(monkeypatch):
    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = "adapters.fake_ver2"
    module = install_fake_adapter(monkeypatch, "fake_ver2")
    module.VERIFIER_VERSION = 3
    assert verifier_identity(verify)["version"] == "3"


def test_source_sha256_none_without_file(monkeypatch):
    module = install_fake_adapter(monkeypatch, "fake_nofile")
    if hasattr(module, "__file__"):
        delattr(module, "__file__")
    assert _source_sha256("adapters.fake_nofile") is None


def test_source_sha256_none_for_missing_file(monkeypatch):
    module = install_fake_adapter(monkeypatch, "fake_gone")
    module.__file__ = str(Path("definitely") / "not-here-xyz.py")
    assert _source_sha256("adapters.fake_gone") is None


def test_source_sha256_hex_and_cached(tmp_path, monkeypatch):
    target = tmp_path / "fake_mod.py"
    target.write_bytes(b"print('courier')\n")
    module = install_fake_adapter(monkeypatch, "fake_hashed")
    module.__file__ = str(target)
    expected = hashlib.sha256(b"print('courier')\n").hexdigest()
    assert _source_sha256("adapters.fake_hashed") == expected
    assert _source_sha256("adapters.fake_hashed") == expected


# --- run_verifier: worker-reported failure rule ------------------------------


def test_failure_idempotent_defaults_retryable():
    verdict = run_verifier(lambda adapter: None, make_task(), make_result("failure"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.verifier == {
        "kind": "courier_rule",
        "name": "worker_reported_failure",
        "adapter": "probe",
    }


def test_failure_non_idempotent_defaults_non_retryable():
    task = make_task(effect_class="non_idempotent")
    verdict = run_verifier(lambda adapter: None, task, make_result("failure"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_failure_explicit_payload_retryable_wins():
    task = make_task(effect_class="non_idempotent")
    verdict = run_verifier(
        lambda adapter: None, task, make_result("failure", retryable=True), Path(".")
    )
    assert verdict.retryable is True
    verdict = run_verifier(
        lambda adapter: None, make_task(), make_result("failure", retryable=False), Path(".")
    )
    assert verdict.retryable is False


def test_failure_reason_truncated_and_defaulted():
    long_reason = "r" * 600
    verdict = run_verifier(
        lambda adapter: None, make_task(), make_result("failure", reason=long_reason), Path(".")
    )
    assert verdict.reason == "r" * 500
    verdict = run_verifier(lambda adapter: None, make_task(), make_result("failure"), Path("."))
    assert verdict.reason == "worker reported failure"
    verdict = run_verifier(
        lambda adapter: None, make_task(), make_result("failure", reason=""), Path(".")
    )
    assert verdict.reason == "worker reported failure"


def test_failure_never_consults_resolver():
    def resolve(adapter):
        raise AssertionError("resolver must not be consulted on worker failure")

    verdict = run_verifier(resolve, make_task(), make_result("failure"), Path("."))
    assert verdict.accepted is False


# --- run_verifier: resolve gate ----------------------------------------------


def test_resolve_error_is_load_failure():
    def resolve(adapter):
        raise RuntimeError("boom")

    verdict = run_verifier(resolve, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "verifier_load_failed"
    assert "RuntimeError" in verdict.reason


def test_missing_verifier_is_rejected():
    verdict = run_verifier(lambda adapter: None, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "no_verifier", "adapter": "probe"}
    assert "probe" in verdict.reason


# --- run_verifier: adapter verdict wrapping -----------------------------------


def test_raising_verifier_fails_closed_with_identity():
    def verify(task, result, home):
        raise ValueError("bad evidence")

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier raised ValueError"
    assert verdict.verifier["kind"] == "adapter"


@pytest.mark.parametrize("bogus", [True, "ok", {"accepted": True}, None, 0])
def test_non_verdict_return_fails_closed(bogus):
    def verify(task, result, home):
        return bogus

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier returned an invalid verdict"
    assert verdict.verifier["kind"] == "adapter"


def test_non_bool_accepted_fails_closed():
    def verify(task, result, home):
        return Verdict(accepted=1, reason="truthy but not bool")

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_accept_is_stamped_with_identity_not_adapter_value():
    def verify(task, result, home):
        return Verdict(True, "looks good", False, verifier={"kind": "spoof"})

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is True
    assert verdict.reason == "looks good"
    assert verdict.retryable is False
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith(".verify")


def test_accept_reason_truncated_and_retryable_coerced():
    def verify(task, result, home):
        return Verdict(True, "x" * 600, retryable=1)

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is True
    assert verdict.reason == "x" * 500
    assert verdict.retryable is True


def test_reject_with_retryable_preserved():
    def verify(task, result, home):
        return Verdict(False, "sha mismatch", True)

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result("success"), Path("."))
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "sha mismatch"
    assert verdict.verifier["kind"] == "adapter"
