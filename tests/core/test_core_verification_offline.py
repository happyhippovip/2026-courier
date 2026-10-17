"""Offline fail-closed pins for courier_core.verification (P9 test hardening).

No dedicated test file covers this module on the base tree: existing tests
reach it only incidentally through adapter end-to-end paths. These tests pin
the module's own rules with stub resolvers -- no adapter execution, no
network, no filesystem writes.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core_builders import stable
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import (
    ADAPTER_NAME,
    Verdict,
    adapter_verifier,
    run_verifier,
    verifier_identity,
)


def make_task(adapter="synthetic", effect_class="idempotent"):
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


def make_result(outcome="success", **payload_extra):
    payload = {"artifacts": [], "outcome": outcome}
    payload.update(payload_extra)
    return Event(**stable(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
        result_id="r-t1-1",
        payload=payload,
    ))


def test_verdict_defaults_are_fail_closed_shape():
    verdict = Verdict(True)
    assert verdict.accepted is True
    assert verdict.reason == ""
    assert verdict.retryable is False
    assert verdict.verifier is None


def test_verdict_is_frozen():
    verdict = Verdict(True)
    with pytest.raises(FrozenInstanceError):
        verdict.accepted = False  # type: ignore[misc]


@pytest.mark.parametrize("name", [
    "synthetic", "a", "local_shell", "a" * 64, "abc123_xyz",
])
def test_adapter_name_allowlists_sane_names(name):
    assert ADAPTER_NAME.match(name) is not None


@pytest.mark.parametrize("name", [
    "", "Synthetic", "SYNTHETIC", "has space", "has-dash", "dot.name",
    "0starts_with_digit", "a" * 65, "under/slash",
])
def test_adapter_verifier_rejects_bad_names_without_importing(name):
    assert adapter_verifier(name) is None


def test_adapter_verifier_returns_none_for_unknown_adapter():
    assert adapter_verifier("no_such_adapter_xyz") is None


def test_adapter_verifier_resolves_synthetic_offline():
    verify = adapter_verifier("synthetic")
    assert callable(verify)
    assert verify.__module__ == "adapters.synthetic"


def test_worker_reported_failure_is_rejected(tmp_path):
    verdict = run_verifier(lambda _name: None, make_task(), make_result("failure"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is True  # idempotent may retry when the worker is silent
    assert verdict.verifier == {
        "kind": "courier_rule", "name": "worker_reported_failure", "adapter": "synthetic",
    }


def test_worker_failure_explicit_retryable_false_wins(tmp_path):
    verdict = run_verifier(
        lambda _name: None, make_task(),
        make_result("failure", retryable=False, reason="boom"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "boom"


def test_worker_failure_non_idempotent_is_not_retryable_by_default(tmp_path):
    verdict = run_verifier(
        lambda _name: None, make_task(effect_class="non_idempotent"),
        make_result("failure"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "worker reported failure"


def test_worker_failure_reason_truncated_to_500(tmp_path):
    verdict = run_verifier(
        lambda _name: None, make_task(),
        make_result("failure", retryable=False, reason="x" * 600), Path(tmp_path))
    assert verdict.reason == "x" * 500


def test_missing_verifier_rejects_non_retryably(tmp_path):
    verdict = run_verifier(lambda _name: None, make_task(), make_result("success"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "no verifier registered" in verdict.reason
    assert verdict.verifier["name"] == "no_verifier"


def test_loader_exception_rejects_and_names_the_error(tmp_path):
    def boom(_name):
        raise ValueError("bad module")

    verdict = run_verifier(boom, make_task(), make_result("success"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "ValueError" in verdict.reason
    assert verdict.verifier["name"] == "verifier_load_failed"


def test_verifier_exception_rejects_with_identity(tmp_path):
    def raiser(_task, _result, _home):
        raise RuntimeError("adapter blew up")

    verdict = run_verifier(lambda _name: raiser, make_task(), make_result("success"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier raised RuntimeError"
    assert verdict.verifier["kind"] == "adapter"


@pytest.mark.parametrize("bad", ["yes", None, 42, {"accepted": True}])
def test_non_verdict_return_rejects(tmp_path, bad):
    verdict = run_verifier(lambda _name: (lambda *_a: bad), make_task(),
                           make_result("success"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_non_bool_accepted_rejects(tmp_path):
    verdict = run_verifier(lambda _name: (lambda *_a: Verdict("yes")), make_task(),
                           make_result("success"), Path(tmp_path))
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"


def test_success_passthrough_stamps_identity_and_bounds(tmp_path):
    def approve(_task, _result, _home):
        return Verdict(True, "r" * 600, 1)

    verdict = run_verifier(lambda _name: approve, make_task(), make_result("success"), Path(tmp_path))
    assert verdict.accepted is True
    assert verdict.reason == "r" * 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"
    assert verdict.verifier["name"].endswith(".approve")


def test_verifier_identity_for_plain_function_has_no_version():
    def approve(_task, _result, _home):
        return Verdict(True)

    identity = verifier_identity(approve)
    assert identity["kind"] == "adapter"
    assert identity["name"].endswith(".approve")
    assert identity["version"] is None


def test_verifier_identity_for_synthetic_carries_version_and_digest():
    verify = adapter_verifier("synthetic")
    identity = verifier_identity(verify)
    assert identity == {
        "kind": "adapter",
        "name": "adapters.synthetic.verify",
        "version": "1",
        "source_sha256": identity["source_sha256"],
    }
    assert len(identity["source_sha256"]) == 64
