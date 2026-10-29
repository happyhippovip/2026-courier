"""P9 hardening pins for courier_core.verification (coercion + identity edges).

Tests only: no behaviour change. Everything here runs offline with tiny
synthetic fixtures; no network, no credentials, no real uploads.

Focus: the value coercions ``run_verifier`` applies around an adapter
verdict (reason truncation, retryable normalisation, fail-closed shapes),
the adapter-name gate in ``adapter_verifier``, and the normalisation in
``verifier_identity`` / ``_source_sha256``.
"""

from __future__ import annotations

import re
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

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _task(adapter: str = "synthetic", effect_class: str = "idempotent", **overrides) -> TaskState:
    base = {
        "task_id": "t-coercion",
        "status": TaskStatus.VERIFYING,
        "adapter": adapter,
        "params": {},
        "effect_class": effect_class,
        "max_attempts": 3,
        "lease_ttl_s": 60,
        "timeout_s": None,
    }
    base.update(overrides)
    return TaskState(**base)


def _result(payload: dict, **overrides) -> Event:
    merged = {"artifacts": []}
    merged.update(payload)
    base = {
        "type": EventType.RESULT_READY,
        "task_id": "t-coercion",
        "attempt": 1,
        "dispatch_id": "d-coercion",
        "worker_id": "w-coercion",
        "result_id": "r-d-coercion",
        "payload": merged,
    }
    base.update(overrides)
    return Event(**base)


def _never_resolve(name: str):
    raise AssertionError(f"resolve must not be called for this payload: {name!r}")


# -- Verdict value shape -------------------------------------------------------


def test_verdict_defaults_are_fail_closed_friendly():
    verdict = Verdict(True)
    assert verdict.accepted is True
    assert verdict.reason == ""
    assert verdict.retryable is False
    assert verdict.verifier is None


def test_verdict_accepted_is_required():
    with pytest.raises(TypeError):
        Verdict()  # type: ignore[call-arg]


def test_verdict_is_frozen():
    verdict = Verdict(True)
    with pytest.raises(Exception):
        verdict.accepted = False  # type: ignore[misc]


# -- adapter_verifier name gate -------------------------------------------------


@pytest.mark.parametrize("name", ["", "Synthetic", "SYNTHETIC", "has-dash", "has space",
                                  "dot.name", "../escape", "9leading", "a" * 65])
def test_adapter_verifier_rejects_bad_names_without_importing(name):
    assert adapter_verifier(name) is None


def test_adapter_name_pattern_matches_gate():
    assert ADAPTER_NAME.match("synthetic")
    assert ADAPTER_NAME.match("a" * 64)
    assert not ADAPTER_NAME.match("a" * 65)


def test_adapter_verifier_missing_adapter_returns_none():
    assert adapter_verifier("zz_no_such_adapter_coercion") is None


def test_adapter_verifier_module_without_verify_returns_none(monkeypatch):
    mod = types.ModuleType("adapters.zz_coercion_noverify")
    monkeypatch.setitem(sys.modules, "adapters.zz_coercion_noverify", mod)
    assert adapter_verifier("zz_coercion_noverify") is None


def test_adapter_verifier_returns_plain_function(monkeypatch):
    def verify(task, result, home):
        return Verdict(True)

    mod = types.ModuleType("adapters.zz_coercion_plain")
    mod.verify = verify
    monkeypatch.setitem(sys.modules, "adapters.zz_coercion_plain", mod)
    assert adapter_verifier("zz_coercion_plain") is verify


def test_adapter_verifier_non_callable_verify_returns_none(monkeypatch):
    mod = types.ModuleType("adapters.zz_coercion_notcallable")
    mod.verify = "not-a-function"
    monkeypatch.setitem(sys.modules, "adapters.zz_coercion_notcallable", mod)
    assert adapter_verifier("zz_coercion_notcallable") is None


def test_adapter_verifier_finds_repo_synthetic_offline():
    verify = adapter_verifier("synthetic")
    assert callable(verify)


# -- verifier_identity normalisation --------------------------------------------


def test_verifier_identity_for_repo_synthetic():
    from adapters import synthetic

    identity = verifier_identity(synthetic.verify)
    assert identity["kind"] == "adapter"
    assert identity["name"].endswith(".verify")
    assert identity["version"] == "1"
    assert isinstance(identity["source_sha256"], str)
    assert SHA256_RE.match(identity["source_sha256"])


def test_verifier_identity_missing_version_is_none():
    def verify(task, result, home):
        return Verdict(True)

    verify.__module__ = "zz_coercion_noversion_mod"
    mod = types.ModuleType("zz_coercion_noversion_mod")
    monkeypatch_mod = mod
    sys.modules["zz_coercion_noversion_mod"] = monkeypatch_mod
    try:
        identity = verifier_identity(verify)
    finally:
        del sys.modules["zz_coercion_noversion_mod"]
    assert identity["version"] is None


def test_verifier_identity_coerces_non_string_version(monkeypatch):
    def verify(task, result, home):
        return Verdict(True)

    verify.__module__ = "zz_coercion_intversion_mod"
    mod = types.ModuleType("zz_coercion_intversion_mod")
    mod.VERIFIER_VERSION = 7
    monkeypatch.setitem(sys.modules, "zz_coercion_intversion_mod", mod)
    assert verifier_identity(verify)["version"] == "7"


def test_verifier_identity_truncates_long_version(monkeypatch):
    def verify(task, result, home):
        return Verdict(True)

    verify.__module__ = "zz_coercion_longversion_mod"
    mod = types.ModuleType("zz_coercion_longversion_mod")
    mod.VERIFIER_VERSION = "v" * 150
    monkeypatch.setitem(sys.modules, "zz_coercion_longversion_mod", mod)
    version = verifier_identity(verify)["version"]
    assert version == "v" * 100


def test_verifier_identity_unknown_module_marks_question():
    class _CallableWithoutNames:
        __module__ = None  # type: ignore[assignment]

        def __call__(self, task, result, home):
            return Verdict(True)

    identity = verifier_identity(_CallableWithoutNames())
    assert identity == {"kind": "adapter", "name": "?.?", "version": None, "source_sha256": None}


# -- _source_sha256 edges --------------------------------------------------------


def test_source_sha256_unknown_module_is_none():
    assert _source_sha256("zz_no_such_module_coercion") is None


def test_source_sha256_module_without_file_is_none():
    assert _source_sha256("sys") is None


def test_source_sha256_is_stable_hex_and_cached():
    first = _source_sha256("courier_core.verification")
    assert isinstance(first, str) and SHA256_RE.match(first)
    from courier_core import verification as verification_mod

    assert verification_mod._SOURCE_DIGESTS  # populated by the call above
    size_before = len(verification_mod._SOURCE_DIGESTS)
    second = _source_sha256("courier_core.verification")
    assert second == first
    assert len(verification_mod._SOURCE_DIGESTS) == size_before


# -- run_verifier: worker-reported failure branch ---------------------------------


def test_failure_outcome_keeps_explicit_retryable_true(tmp_path):
    verdict = run_verifier(_never_resolve, _task(), _result({"outcome": "failure", "retryable": True}), tmp_path)
    assert verdict == Verdict(False, "worker reported failure", True,
                              {"kind": "courier_rule", "name": "worker_reported_failure",
                               "adapter": "synthetic"})


def test_failure_outcome_falsy_retryable_coerces_false(tmp_path):
    # Event validation requires a boolean retryable, so the falsy-int path
    # is pinned through the same minimal input run_verifier reads.
    verdict = run_verifier(_never_resolve, _task(), _BareResult({"outcome": "failure", "retryable": 0}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_failure_outcome_defaults_retryable_from_effect_class(tmp_path):
    idem = run_verifier(_never_resolve, _task(effect_class="idempotent"),
                        _result({"outcome": "failure"}), tmp_path)
    assert idem.retryable is True
    non_idem = run_verifier(_never_resolve, _task(effect_class="non_idempotent"),
                            _result({"outcome": "failure"}), tmp_path)
    assert non_idem.retryable is False


def test_failure_outcome_truncates_long_reason(tmp_path):
    verdict = run_verifier(_never_resolve, _task(), _result({"outcome": "failure", "reason": "r" * 600}), tmp_path)
    assert verdict.reason == "r" * 500


class _BareResult:
    """Minimal run_verifier input: only .payload is read on the failure path."""

    def __init__(self, payload: dict):
        self.payload = payload


def test_missing_outcome_treated_as_failure_without_calling_resolve(tmp_path):
    verdict = run_verifier(_never_resolve, _task(), _BareResult({"artifacts": []}), tmp_path)
    assert verdict.accepted is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "worker_reported_failure",
                                "adapter": "synthetic"}


@pytest.mark.parametrize("reason", [None, ""])
def test_empty_reason_falls_back_to_default(tmp_path, reason):
    verdict = run_verifier(_never_resolve, _task(), _result({"outcome": "failure", "reason": reason}), tmp_path)
    assert verdict.reason == "worker reported failure"


# -- run_verifier: loader branch ---------------------------------------------------


def test_resolve_raising_rejects_without_retry(tmp_path):
    def resolve(name):
        raise ImportError("broken adapter plugin")

    verdict = run_verifier(resolve, _task(), _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "verifier_load_failed",
                                "adapter": "synthetic"}
    assert "ImportError" in verdict.reason


def test_resolve_returning_none_rejects_without_retry(tmp_path):
    verdict = run_verifier(lambda name: None, _task(), _result({"outcome": "success"}), tmp_path)
    assert verdict == Verdict(False, "no verifier registered for adapter 'synthetic'", False,
                              {"kind": "courier_rule", "name": "no_verifier", "adapter": "synthetic"})


# -- run_verifier: adapter verdict branch -------------------------------------------


def test_verify_raising_rejects_and_keeps_identity(tmp_path):
    def resolve(name):
        def verify(task, result, home):
            raise ValueError("boom")

        verify.__module__ = "zz_coercion_raising_mod"
        return verify

    verdict = run_verifier(resolve, _task(), _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier raised ValueError"
    assert verdict.retryable is False
    assert verdict.verifier["kind"] == "adapter"


@pytest.mark.parametrize("bad", [None, {"accepted": True}, "yes", True, 1])
def test_invalid_verdict_shapes_reject(tmp_path, bad):
    verdict = run_verifier(lambda name: (lambda t, r, h: bad), _task(),
                           _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"
    assert verdict.retryable is False


def test_non_bool_accepted_flag_rejects(tmp_path):
    verdict = run_verifier(lambda name: (lambda t, r, h: Verdict(1)), _task(),
                           _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_non_callable_resolve_result_rejects_as_raised(tmp_path):
    verdict = run_verifier(lambda name: "not-a-function", _task(),
                           _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier raised TypeError"


def test_success_passthrough_truncates_and_coerces(tmp_path):
    def resolve(name):
        def verify(task, result, home):
            return Verdict(True, "o" * 600, retryable=1, verifier={"stale": True})

        return verify

    verdict = run_verifier(resolve, _task(), _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "o" * 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"
    assert "stale" not in verdict.verifier


def test_adapter_rejection_passes_through_with_rule_free_identity(tmp_path):
    def resolve(name):
        def verify(task, result, home):
            return Verdict(False, "hash mismatch", retryable=False)

        return verify

    verdict = run_verifier(resolve, _task(), _result({"outcome": "success"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "hash mismatch"
    assert verdict.retryable is False
    assert verdict.verifier["kind"] == "adapter"


# -- end to end with the repo synthetic adapter (offline) -----------------------------


def test_end_to_end_synthetic_accepts_matching_evidence(tmp_path: Path):
    from courier_core.verification import adapter_verifier as resolve

    data = b"coercion-evidence"
    (tmp_path / "out.bin").write_bytes(data)
    digest = __import__("hashlib").sha256(data).hexdigest()
    task = _task()
    result = _result({"outcome": "success", "artifacts": [{"path": "out.bin", "sha256": digest}]})
    verdict = run_verifier(resolve, task, result, tmp_path)
    assert verdict.accepted is True
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["version"] == "1"


def test_end_to_end_synthetic_rejects_tampered_evidence(tmp_path: Path):
    from courier_core.verification import adapter_verifier as resolve

    (tmp_path / "out.bin").write_bytes(b"tampered")
    digest = "0" * 64
    task = _task()
    result = _result({"outcome": "success", "artifacts": [{"path": "out.bin", "sha256": digest}]})
    verdict = run_verifier(resolve, task, result, tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
