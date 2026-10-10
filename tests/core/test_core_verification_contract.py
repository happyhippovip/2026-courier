"""Documented fail-closed contract pins for courier_core.verification (P9, tests only).

Pins the rules stated in courier_core/verification.py's module docstring:
- a worker-reported "failure" outcome is always rejected; retryability comes
  from the result payload, otherwise only an "idempotent" effect class may
  retry by omission;
- a missing adapter verifier, a loader error, a raising verifier, and a
  non-Verdict (or non-bool) return all reject without retry; there is no
  default PASS;
- every verdict is stamped with who decided (adapter identity or rule name),
  reasons are capped at 500 chars, and retryable is a real bool.

No behavior change, no network, no credentials, no subprocess.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    Verdict,
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
        max_attempts=2,
        lease_ttl_s=60,
        timeout_s=None,
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        started=True,
    )


def _ready(outcome: str | None = "success", **extra) -> Event:
    payload: dict = {"artifacts": [], "outcome": outcome}
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


def _accept(task, result, home) -> Verdict:
    return Verdict(True, "looks good", True)


def _reject(task, result, home) -> Verdict:
    return Verdict(False, "evidence missing", True)


def test_verdict_requires_explicit_accepted():
    # There is no zero-arg Verdict: "accepted" must always be stated, so a
    # PASS can never arise by omission; the remaining fields default closed.
    with pytest.raises(TypeError):
        Verdict()
    verdict = Verdict(False)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == ""
    assert verdict.verifier is None


def test_failure_outcome_never_calls_adapter_verifier(tmp_path: Path):
    calls: list = []

    def resolve(adapter: str):
        calls.append(adapter)
        return _accept

    verdict = run_verifier(resolve, _task(), _ready("failure"), tmp_path)
    assert verdict.accepted is False
    assert calls == []
    assert verdict.verifier == {
        "kind": "courier_rule",
        "name": "worker_reported_failure",
        "adapter": "synthetic",
    }


@pytest.mark.parametrize(
    "effect_class, expected", [("idempotent", True), ("external", False), ("unknown", False)]
)
def test_failure_retryable_falls_back_to_idempotent_only(
    tmp_path: Path, effect_class: str, expected: bool
):
    verdict = run_verifier(lambda adapter: _accept, _task(effect_class=effect_class),
                           _ready("failure"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is expected


@pytest.mark.parametrize("retryable", [True, False])
def test_failure_explicit_retryable_honored(tmp_path: Path, retryable: bool):
    verdict = run_verifier(lambda adapter: _accept, _task(),
                           _ready("failure", retryable=retryable), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is retryable


def test_failure_missing_reason_defaults(tmp_path: Path):
    verdict = run_verifier(lambda adapter: _accept, _task(), _ready("failure"), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "worker reported failure"


def test_failure_long_reason_capped_at_500(tmp_path: Path):
    verdict = run_verifier(lambda adapter: _accept, _task(),
                           _ready("failure", reason="x" * 600), tmp_path)
    assert verdict.reason == "x" * 500


def test_adapter_cannot_forge_verifier_stamp(tmp_path: Path):
    # The journal records who decided; a preset stamp is always overwritten
    # with the computed adapter identity, never trusted as given.
    def forged(task, result, home):
        return Verdict(True, "trust me", True, verifier={"kind": "adapter", "name": "fake"})

    verdict = run_verifier(lambda adapter: forged, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is True
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith(".forged")
    assert verdict.verifier["name"] != "fake"


def test_loader_error_rejects_without_retry(tmp_path: Path):
    def resolve(adapter: str):
        raise RuntimeError("broken adapter module")

    verdict = run_verifier(resolve, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier is not None
    assert verdict.verifier["name"] == "verifier_load_failed"
    assert "RuntimeError" in verdict.reason


def test_absent_verifier_rejects_without_retry(tmp_path: Path):
    verdict = run_verifier(lambda adapter: None, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier is not None
    assert verdict.verifier["name"] == "no_verifier"


def test_raising_verifier_rejects_with_adapter_identity(tmp_path: Path):
    def boom(task, result, home):
        raise ValueError("bad evidence")

    verdict = run_verifier(lambda adapter: boom, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"
    assert "boom" in verdict.verifier["name"]
    assert "ValueError" in verdict.reason


@pytest.mark.parametrize("bad", ["ok", None, 42, {"accepted": True}])
def test_non_verdict_return_rejects(tmp_path: Path, bad):
    def weird(task, result, home):
        return bad

    verdict = run_verifier(lambda adapter: weird, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_truthy_non_bool_accepted_rejects(tmp_path: Path):
    def loose(task, result, home):
        return Verdict(1, "truthy but not a bool", False)

    verdict = run_verifier(lambda adapter: loose, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_accept_is_stamped_with_adapter_identity(tmp_path: Path):
    verdict = run_verifier(lambda adapter: _accept, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is True
    assert verdict.retryable is True
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith("._accept")
    assert "version" in verdict.verifier and "source_sha256" in verdict.verifier


def test_reject_passthrough_keeps_decision_and_stamps(tmp_path: Path):
    verdict = run_verifier(lambda adapter: _reject, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "evidence missing"
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"


def test_reason_capped_and_retryable_coerced_on_accept(tmp_path: Path):
    def loud(task, result, home):
        return Verdict(True, "y" * 600, "yes")

    verdict = run_verifier(lambda adapter: loud, _task(), _ready("success"), tmp_path)
    assert verdict.accepted is True
    assert verdict.reason == "y" * 500
    assert verdict.retryable is True


def test_reason_exactly_500_chars_kept_whole(tmp_path: Path):
    verdict = run_verifier(lambda adapter: _accept, _task(),
                           _ready("failure", reason="z" * 500), tmp_path)
    assert verdict.reason == "z" * 500


@pytest.mark.parametrize("bad", ["", "Synthetic", "has space", "../evil", "a" * 65, "9lives"])
def test_adapter_name_gate_rejects_without_importing(monkeypatch: pytest.MonkeyPatch, bad: str):
    def no_import(name: str):
        raise AssertionError("must not attempt an import")

    monkeypatch.setattr("courier_core.verification.importlib.import_module", no_import)
    assert adapter_verifier(bad) is None


def test_unknown_adapter_returns_none():
    assert adapter_verifier("no_such_adapter_xyz") is None


def test_identity_shape_keys():
    identity = verifier_identity(_accept)
    assert identity["kind"] == "adapter"
    assert identity["name"].endswith("._accept")
    assert "version" in identity and "source_sha256" in identity
    digest = identity["source_sha256"]
    assert digest is None or re.fullmatch(r"[0-9a-f]{64}", digest or "") is not None
