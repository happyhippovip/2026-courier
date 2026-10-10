"""Fail-closed pins for courier_core.verification (P9, tests only).

run_verifier must reject unless an adapter verifier returns a well-formed
Verdict for a success outcome. These pins cover the no-verifier and
loader-failure branches plus adapter-name gating. No network, no subprocess.
"""

from __future__ import annotations

import hashlib
import sys
import types
from unittest import mock

from courier_core import verification as V
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    Verdict,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)

SHA = "ab" * 32


def make_task(adapter="probe", effect_class="non_idempotent", **overrides):
    kwargs = dict(
        task_id="t1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=6,
        timeout_s=None,
    )
    kwargs.update(overrides)
    return TaskState(**kwargs)


def make_result(outcome="success", **payload_extra):
    payload = {
        "outcome": outcome,
        "artifacts": [{"path": "out.txt", "sha256": SHA}],
    }
    payload.update(payload_extra)
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=payload,
    )


def accept(task, result, home):
    return Verdict(True, "ok")


# -- worker-reported failure ---------------------------------------------------

def test_failure_outcome_rejected_with_default_reason(tmp_path):
    verdict = run_verifier(lambda adapter: accept, make_task(), make_result("failure"), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "worker reported failure"
    assert verdict.retryable is False
    assert verdict.verifier == {"kind": "courier_rule", "name": "worker_reported_failure",
                                "adapter": "probe"}


def test_failure_outcome_idempotent_retryable_by_omission(tmp_path):
    verdict = run_verifier(lambda adapter: accept, make_task(effect_class="idempotent"),
                           make_result("failure"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True


def test_failure_outcome_explicit_retryable_wins(tmp_path):
    verdict = run_verifier(lambda adapter: accept, make_task(effect_class="idempotent"),
                           make_result("failure", retryable=False), tmp_path)
    assert verdict.retryable is False


def test_failure_outcome_uses_payload_reason(tmp_path):
    verdict = run_verifier(lambda adapter: accept, make_task(),
                           make_result("failure", reason="boom"), tmp_path)
    assert verdict.reason == "boom"


def test_failure_outcome_empty_reason_falls_back(tmp_path):
    verdict = run_verifier(lambda adapter: accept, make_task(),
                           make_result("failure", reason=""), tmp_path)
    assert verdict.reason == "worker reported failure"


def test_failure_outcome_reason_truncated(tmp_path):
    verdict = run_verifier(lambda adapter: accept, make_task(),
                           make_result("failure", reason="x" * 900), tmp_path)
    assert len(verdict.reason) == 500


# -- loader failures -----------------------------------------------------------

def test_resolve_raises_rejected_as_load_failed(tmp_path):
    def resolve(adapter):
        raise ImportError("boom")

    verdict = run_verifier(resolve, make_task(), make_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "ImportError" in verdict.reason
    assert verdict.verifier == {"kind": "courier_rule", "name": "verifier_load_failed",
                                "adapter": "probe"}


def test_resolve_none_rejected_as_no_verifier(tmp_path):
    verdict = run_verifier(lambda adapter: None, make_task(), make_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "no verifier registered" in verdict.reason
    assert verdict.verifier == {"kind": "courier_rule", "name": "no_verifier",
                                "adapter": "probe"}


def test_verifier_raises_rejected_with_identity(tmp_path):
    def verify(task, result, home):
        raise RuntimeError("kaput")

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier raised RuntimeError"
    assert verdict.verifier["kind"] == "adapter"


def test_verifier_non_verdict_rejected(tmp_path):
    for bad in (None, True, "ok", {"accepted": True}):
        def verify(task, result, home, _bad=bad):
            return _bad

        verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), tmp_path)
        assert verdict.accepted is False
        assert verdict.retryable is False
        assert verdict.reason == "verifier returned an invalid verdict"


def test_verifier_non_bool_accepted_rejected(tmp_path):
    def verify(task, result, home):
        return Verdict(1, "truthy is not True")

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"


# -- success path normalization ------------------------------------------------

def test_success_stamps_identity_and_coerces(tmp_path):
    def verify(task, result, home):
        return Verdict(True, "y" * 900, retryable=1)

    verdict = run_verifier(lambda adapter: verify, make_task(), make_result(), tmp_path)
    assert verdict.accepted is True
    assert len(verdict.reason) == 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"
    assert verify.__qualname__ in verdict.verifier["name"]


def test_verdict_defaults():
    verdict = Verdict(True)
    assert verdict.reason == ""
    assert verdict.retryable is False
    assert verdict.verifier is None


# -- adapter-name gating (no import attempted) ---------------------------------

def test_adapter_verifier_rejects_bad_names():
    for bad in ("", "A", "0abc", "a-b", "a b", "../x", "a" * 65, "UPPER"):
        assert adapter_verifier(bad) is None


def test_adapter_verifier_missing_module_is_none():
    assert adapter_verifier("zz_no_such_adapter_xyz") is None


def test_adapter_verifier_reraise_unrelated_import_error():
    err = ModuleNotFoundError("No module named 'dep'")
    err.name = "dep"
    with mock.patch.object(V.importlib, "import_module", side_effect=err):
        try:
            adapter_verifier("probe")
        except ModuleNotFoundError as exc:
            assert exc.name == "dep"
        else:
            raise AssertionError("expected ModuleNotFoundError to propagate")


def test_adapter_verifier_none_without_verify(monkeypatch):
    package = types.ModuleType("adapters")
    package.__path__ = []
    module = types.ModuleType("adapters.novf")
    monkeypatch.setitem(sys.modules, "adapters", package)
    monkeypatch.setitem(sys.modules, "adapters.novf", module)
    assert adapter_verifier("novf") is None


def test_adapter_verifier_none_when_verify_not_callable(monkeypatch):
    package = types.ModuleType("adapters")
    package.__path__ = []
    module = types.ModuleType("adapters.plain")
    module.verify = "not-a-function"
    monkeypatch.setitem(sys.modules, "adapters", package)
    monkeypatch.setitem(sys.modules, "adapters.plain", module)
    assert adapter_verifier("plain") is None


# -- verifier identity ---------------------------------------------------------

def test_verifier_identity_version_coercion_and_truncation(monkeypatch):
    module = types.ModuleType("fake_ident_mod")
    module.VERIFIER_VERSION = 7
    monkeypatch.setitem(sys.modules, "fake_ident_mod", module)

    def verify(task, result, home):
        return Verdict(True, "ok")

    verify.__module__ = "fake_ident_mod"
    identity = verifier_identity(verify)
    assert identity["kind"] == "adapter"
    assert identity["version"] == "7"
    assert identity["source_sha256"] is None

    module.VERIFIER_VERSION = "v" * 150
    identity = verifier_identity(verify)
    assert len(identity["version"]) == 100


def test_verifier_identity_missing_version_is_none():
    identity = verifier_identity(accept)
    assert identity["version"] is None
    assert identity["name"].endswith(".accept")


def test_source_sha256_matches_file_and_missing_is_none(tmp_path):
    target = tmp_path / "mod.py"
    target.write_bytes(b"x = 1\n")
    module = types.ModuleType("fake_digest_mod")
    module.__file__ = str(target)

    import sys as _sys

    _sys.modules["fake_digest_mod"] = module
    try:
        def verify(task, result, home):
            return Verdict(True, "ok")

        verify.__module__ = "fake_digest_mod"
        identity = verifier_identity(verify)
        assert identity["source_sha256"] == hashlib.sha256(b"x = 1\n").hexdigest()
    finally:
        del _sys.modules["fake_digest_mod"]

    ghost = types.ModuleType("fake_ghost_mod")
    ghost.__file__ = str(tmp_path / "absent.py")

    def verify_ghost(task, result, home):
        return Verdict(True, "ok")

    verify_ghost.__module__ = "fake_ghost_mod"
    _sys.modules["fake_ghost_mod"] = ghost
    try:
        assert verifier_identity(verify_ghost)["source_sha256"] is None
    finally:
        del _sys.modules["fake_ghost_mod"]
