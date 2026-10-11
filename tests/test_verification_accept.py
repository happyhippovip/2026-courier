"""P9 hardening: accept-path normalization + worker-failure defaults.

Covers courier_core.verification.run_verifier where no dedicated base test
file exists (the controller suite exercises verification only indirectly):

- ACCEPT path: reason truncated to 500 chars, retryable coerced with bool(),
  adapter verifier identity attached to the verdict.
- worker-reported failure: default reason, retryable default derived from
  effect_class via may_auto_retry, explicit retryable honored, reason bound.
- failure short-circuits before resolve(); invalid verdict shapes and
  raising verifiers reject non-retryably (fail closed).

Offline only: synthetic TaskState / RESULT_READY fixtures, stub resolve.
"""

from __future__ import annotations

from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import Verdict, run_verifier

SHA = "ab" * 32


def _task(effect_class="idempotent", adapter="synthetic"):
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
        dispatch_id="d1",
        worker_id="w1",
    )


def _ready(outcome="success", reason=None, retryable=None):
    payload = {"artifacts": [{"path": "out.txt", "sha256": SHA}], "outcome": outcome}
    if reason is not None:
        payload["reason"] = reason
    if retryable is not None:
        payload["retryable"] = retryable
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=payload,
    )


def test_accept_attaches_adapter_identity(tmp_path):
    def verify(task, result, home):
        return Verdict(True, "looks good", False)

    seen = {}

    def resolve(adapter):
        seen["adapter"] = adapter
        return verify

    verdict = run_verifier(resolve, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is True
    assert verdict.reason == "looks good"
    assert verdict.retryable is False
    assert seen["adapter"] == "synthetic"
    assert isinstance(verdict.verifier, dict)
    assert verdict.verifier["kind"] == "adapter"
    assert "verify" in verdict.verifier["name"]


def test_accept_truncates_long_reason(tmp_path):
    def verify(task, result, home):
        return Verdict(True, "x" * 600, False)

    verdict = run_verifier(lambda adapter: verify, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is True
    assert verdict.reason == "x" * 500


def test_accept_coerces_retryable_to_bool(tmp_path):
    def verify(task, result, home):
        return Verdict(True, "ok", 1)

    verdict = run_verifier(lambda adapter: verify, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is True
    assert verdict.retryable is True

    def verify_zero(task, result, home):
        return Verdict(True, "ok", 0)

    verdict = run_verifier(lambda adapter: verify_zero, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is True
    assert verdict.retryable is False


def test_failure_defaults_reason_when_missing(tmp_path):
    verdict = run_verifier(lambda adapter: None, _task(), _ready(outcome="failure"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.reason == "worker reported failure"


def test_failure_empty_reason_defaults(tmp_path):
    verdict = run_verifier(
        lambda adapter: None, _task(), _ready(outcome="failure", reason=""), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.reason == "worker reported failure"


def test_failure_retryable_defaults_by_effect_class(tmp_path):
    idempotent = run_verifier(
        lambda adapter: None, _task(effect_class="idempotent"),
        _ready(outcome="failure"), Path(tmp_path))
    assert idempotent.accepted is False
    assert idempotent.retryable is True

    consequential = run_verifier(
        lambda adapter: None, _task(effect_class="non_idempotent"),
        _ready(outcome="failure"), Path(tmp_path))
    assert consequential.accepted is False
    assert consequential.retryable is False


def test_failure_explicit_retryable_overrides_default(tmp_path):
    pin = run_verifier(
        lambda adapter: None, _task(effect_class="idempotent"),
        _ready(outcome="failure", reason="do not retry", retryable=False), Path(tmp_path))
    assert pin.accepted is False
    assert pin.retryable is False

    force = run_verifier(
        lambda adapter: None, _task(effect_class="non_idempotent"),
        _ready(outcome="failure", reason="transient", retryable=True), Path(tmp_path))
    assert force.accepted is False
    assert force.retryable is True


def test_failure_truncates_long_reason(tmp_path):
    verdict = run_verifier(
        lambda adapter: None, _task(), _ready(outcome="failure", reason="y" * 600),
        Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.reason == "y" * 500


def test_failure_short_circuits_before_resolve(tmp_path):
    def resolve(adapter):
        raise AssertionError("resolve must not run on worker-reported failure")

    verdict = run_verifier(resolve, _task(), _ready(outcome="failure"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.verifier["kind"] == "courier_rule"
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_invalid_verdict_shape_rejects_non_retryably(tmp_path):
    def verify(task, result, home):
        return True

    verdict = run_verifier(lambda adapter: verify, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_non_bool_accepted_flag_rejects(tmp_path):
    def verify(task, result, home):
        return Verdict("yes", "ok", False)

    verdict = run_verifier(lambda adapter: verify, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_raising_verifier_rejects_non_retryably(tmp_path):
    def verify(task, result, home):
        raise RuntimeError("boom")

    verdict = run_verifier(lambda adapter: verify, _task(), _ready(), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier raised RuntimeError"
