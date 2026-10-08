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


def make_task(adapter="mock_adapter", effect_class="idempotent"):
    return TaskState(
        task_id="task-001",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=30,
        timeout_s=60,
    )


def make_result(outcome="success", retryable=False, reason=""):
    payload = {"artifacts": [], "outcome": outcome}
    if retryable:
        payload["retryable"] = retryable
    if reason:
        payload["reason"] = reason
    return Event(
        type=EventType.RESULT_READY,
        task_id="task-001",
        attempt=1,
        dispatch_id="disp-001",
        worker_id="worker-001",
        result_id="res-001",
        payload=payload,
    )


def test_verdict_immutability():
    v = Verdict(accepted=True, reason="ok", retryable=False)
    assert v.accepted is True
    with pytest.raises(AttributeError):
        v.accepted = False


def test_adapter_verifier_regex_and_missing():
    assert adapter_verifier("INVALID-ADAPTER-NAME") is None
    assert adapter_verifier("nonexistent_adapter_xyz") is None


def test_run_verifier_worker_failure_is_always_rejected():
    task = make_task(effect_class="idempotent")
    result = make_result(outcome="failure", reason="model timeout")
    home = Path("/tmp")

    verdict = run_verifier(lambda name: None, task, result, home)
    assert verdict.accepted is False
    assert "model timeout" in verdict.reason
    assert verdict.retryable is True
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_run_verifier_non_idempotent_omission_is_not_retryable():
    task = make_task(effect_class="non_idempotent")
    result = make_result(outcome="failure", reason="connection cut")
    home = Path("/tmp")

    verdict = run_verifier(lambda name: None, task, result, home)
    assert verdict.accepted is False
    assert verdict.retryable is False


def test_run_verifier_no_registered_verifier():
    task = make_task(adapter="some_adapter")
    result = make_result(outcome="success")
    home = Path("/tmp")

    verdict = run_verifier(lambda name: None, task, result, home)
    assert verdict.accepted is False
    assert "no verifier registered" in verdict.reason
    assert verdict.verifier["name"] == "no_verifier"


def test_run_verifier_loader_exception():
    task = make_task(adapter="some_adapter")
    result = make_result(outcome="success")
    home = Path("/tmp")

    def broken_loader(name):
        raise ImportError("Corrupt dependency")

    verdict = run_verifier(broken_loader, task, result, home)
    assert verdict.accepted is False
    assert "failed to load: ImportError" in verdict.reason
    assert verdict.verifier["name"] == "verifier_load_failed"


def test_run_verifier_verifier_raises_fails_closed():
    task = make_task(adapter="some_adapter")
    result = make_result(outcome="success")
    home = Path("/tmp")

    def crashing_verify(t, r, h):
        raise ValueError("Explosion during verification")

    verdict = run_verifier(lambda name: crashing_verify, task, result, home)
    assert verdict.accepted is False
    assert "verifier raised ValueError" in verdict.reason


def test_run_verifier_invalid_return_type_fails_closed():
    task = make_task(adapter="some_adapter")
    result = make_result(outcome="success")
    home = Path("/tmp")

    def bad_verify(t, r, h):
        return "I am a string, not a Verdict object"

    verdict = run_verifier(lambda name: bad_verify, task, result, home)
    assert verdict.accepted is False
    assert "invalid verdict" in verdict.reason


def test_run_verifier_success_attaches_identity():
    task = make_task(adapter="some_adapter")
    result = make_result(outcome="success")
    home = Path("/tmp")

    def honest_verifier(t, r, h):
        return Verdict(accepted=True, reason="All checks passed")

    verdict = run_verifier(lambda name: honest_verifier, task, result, home)
    assert verdict.accepted is True
    assert verdict.reason == "All checks passed"
    assert verdict.verifier is not None
    assert verdict.verifier["kind"] == "adapter"
