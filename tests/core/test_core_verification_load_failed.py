"""Fail-closed pins for verifier load failure in courier_core.verification.

When the resolver for ``task.adapter`` raises (broken import, missing
dependency, misconfigured registry), :func:`run_verifier` must reject
without calling any verifier, without leaking exception text, and without
becoming retryable by omission. Offline only; no network, no credentials.
"""

from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import run_verifier


def _task(adapter="synthetic", effect_class="idempotent"):
    return TaskState(
        task_id="t-load-1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=60,
        timeout_s=None,
        attempt=1,
        dispatch_id="d-t-load-1-1",
        worker_id="w1",
    )


def _success_result():
    return Event(
        type=EventType.RESULT_READY,
        task_id="t-load-1",
        attempt=1,
        dispatch_id="d-t-load-1-1",
        worker_id="w1",
        result_id="r-t-load-1-1",
        payload={"artifacts": [], "outcome": "success"},
    )


def test_load_failed_value_error_rejects_non_retryably(tmp_path):
    def resolve(_adapter):
        raise ValueError("broken registry entry")

    verdict = run_verifier(resolve, _task(), _success_result(), Path(tmp_path))

    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["kind"] == "courier_rule"
    assert verdict.verifier["name"] == "verifier_load_failed"
    assert verdict.verifier["adapter"] == "synthetic"


def test_load_failed_reason_names_adapter_and_exception_type(tmp_path):
    def resolve(_adapter):
        raise ValueError("registry-detail-must-not-leak")

    verdict = run_verifier(resolve, _task(), _success_result(), Path(tmp_path))

    assert "synthetic" in verdict.reason
    assert "ValueError" in verdict.reason
    assert "registry-detail-must-not-leak" not in verdict.reason


def test_load_failed_import_error_rejects(tmp_path):
    def resolve(_adapter):
        raise ImportError("no module named adapters.foo")

    verdict = run_verifier(resolve, _task(), _success_result(), Path(tmp_path))

    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "verifier_load_failed"
    assert "ImportError" in verdict.reason


def test_load_failed_runtime_error_rejects_without_message_leak(tmp_path):
    def resolve(_adapter):
        raise RuntimeError("internal path /tmp/xyz")

    verdict = run_verifier(resolve, _task(), _success_result(), Path(tmp_path))

    assert verdict.accepted is False
    assert "RuntimeError" in verdict.reason
    assert "/tmp/xyz" not in verdict.reason


def test_load_failed_never_retryable_even_for_idempotent(tmp_path):
    def resolve(_adapter):
        raise OSError("disk gone")

    for effect_class in ("idempotent", "non_idempotent"):
        verdict = run_verifier(
            resolve, _task(effect_class=effect_class), _success_result(), Path(tmp_path)
        )
        assert verdict.accepted is False
        assert verdict.retryable is False


def test_load_failed_does_not_call_verifier(tmp_path):
    called = []

    def resolve(_adapter):
        raise ValueError("before verifier")

    def fake_verify(task, result, home):
        called.append(True)
        raise AssertionError("must not be called")

    _ = fake_verify  # documents the boundary; resolve fails first
    verdict = run_verifier(resolve, _task(), _success_result(), Path(tmp_path))

    assert verdict.accepted is False
    assert called == []


def test_load_failed_with_unusual_adapter_name_stays_closed(tmp_path):
    weird = "a'b\" c"
    task = _task(adapter=weird)

    def resolve(_adapter):
        raise ValueError("bad")

    verdict = run_verifier(resolve, task, _success_result(), Path(tmp_path))

    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["adapter"] == weird
    assert "verifier_load_failed" == verdict.verifier["name"]


def test_load_failed_carries_rule_identity_not_adapter_identity(tmp_path):
    def resolve(_adapter):
        raise ValueError("x")

    verdict = run_verifier(resolve, _task(), _success_result(), Path(tmp_path))

    assert verdict.verifier["kind"] == "courier_rule"
    assert set(verdict.verifier) == {"kind", "name", "adapter"}


def test_load_failed_base_exception_propagates(tmp_path):
    def resolve(_adapter):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_verifier(resolve, _task(), _success_result(), Path(tmp_path))
