"""P9 test hardening for courier_core.verification (worker-failure retryable path).

Tests-only: pins the fail-closed fallback in run_verifier when the worker
reports outcome "failure":

- an explicit payload retryable always wins;
- when retryable is absent, only effect_class "idempotent" is retryable
  (may_auto_retry); every other class fails closed;
- the verdict is rejected, carries the courier_rule worker_reported_failure,
  truncates long reasons to 500 chars, and never consults the adapter
  registry on this path.

No network, no credentials, no behaviour change.
"""

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import run_verifier


def make_task(effect_class="idempotent", adapter="probe"):
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


def make_failure(extra=None):
    payload = {"outcome": "failure", "artifacts": []}
    if extra:
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


def exploding_resolve(adapter):
    raise AssertionError("failure path must not consult the adapter registry")


def test_explicit_retryable_true_wins(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(effect_class="non_idempotent"),
        make_failure({"retryable": True, "reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True
    assert verdict.reason == "boom"


def test_explicit_retryable_false_wins_for_idempotent(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(effect_class="idempotent"),
        make_failure({"retryable": False, "reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_missing_retryable_idempotent_is_retryable(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(effect_class="idempotent"),
        make_failure({"reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is True


def test_missing_retryable_non_idempotent_is_not_retryable(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(effect_class="non_idempotent"),
        make_failure({"reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_missing_retryable_unknown_class_fails_closed(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(effect_class="consequential"),
        make_failure({"reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_missing_reason_uses_default(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(),
        make_failure({"retryable": False}), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "worker reported failure"


def test_empty_reason_uses_default(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(),
        make_failure({"retryable": False, "reason": ""}), tmp_path)
    assert verdict.reason == "worker reported failure"


def test_long_reason_truncated_to_500(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(),
        make_failure({"retryable": False, "reason": "x" * 600}), tmp_path)
    assert verdict.reason == "x" * 500


def test_failure_carries_worker_rule_identity(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(adapter="probe"),
        make_failure({"retryable": False, "reason": "boom"}), tmp_path)
    assert verdict.verifier == {
        "kind": "courier_rule", "name": "worker_reported_failure", "adapter": "probe"}


def test_failure_with_unknown_adapter_still_worker_rule(tmp_path):
    verdict = run_verifier(
        exploding_resolve, make_task(adapter="nope-missing"),
        make_failure({"retryable": True, "reason": "boom"}), tmp_path)
    assert verdict.accepted is False
    assert verdict.verifier["name"] == "worker_reported_failure"
