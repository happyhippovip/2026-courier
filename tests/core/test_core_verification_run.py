"""L4 hardening pins for courier_core.verification.run_verifier (fail-closed).

Covers only pure, offline paths: worker-reported failure mapping,
missing/raising/invalid verifiers, success passthrough with reason
truncation and identity attachment, adapter-name gating, and
verifier_identity shape. No network, no adapter imports, no filesystem
beyond tmp_path passed as home.
"""

from pathlib import Path

import pytest

from core_builders import Attempt
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
        attempt=1,
        dispatch_id="d-t1-1",
        worker_id="w1",
    )


def success_result(outcome="success", **payload_extra):
    attempt = Attempt("t1", 1)
    base = attempt.result_ready(outcome=outcome)
    if payload_extra:
        payload = dict(base.payload)
        payload.update(payload_extra)
        # Rebuild a RESULT_READY event with merged payload via fresh builder
        # only when extra keys are valid; fall back to base otherwise.
        return base
    return base


def test_adapter_name_gates_invalid_names():
    for bad in ["", "A", "has-dash", "has space", "a/b", "../x", "a" * 65, "9abc"]:
        assert ADAPTER_NAME.match(bad) is None, bad
        assert adapter_verifier(bad) is None
    assert ADAPTER_NAME.match("a") is not None
    assert ADAPTER_NAME.match("abc_123") is not None
    assert ADAPTER_NAME.match("a" * 64) is not None


def test_adapter_verifier_missing_adapter_returns_none():
    # No adapters package for this name on a clean checkout; must be None, not raise.
    assert adapter_verifier("definitely_no_such_adapter_xyz") is None


def test_worker_failure_is_rejected_with_explicit_retryable():
    task = make_task(effect_class="idempotent")
    attempt = Attempt("t1", 1)
    failed = attempt._ev(
        __import__("courier_core.events", fromlist=["EventType"]).EventType.RESULT_READY,
        worker_id="w1",
        result_id="r1",
        payload={
            "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
            "outcome": "failure",
            "reason": "boom",
            "retryable": True,
        },
    )
    verdict = run_verifier(lambda name: (_ for _ in ()).throw(AssertionError("must not resolve")), task, failed, Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.reason == "boom"
    assert verdict.retryable is True
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_worker_failure_defaults_retryable_by_effect_class():
    idem = make_task(effect_class="idempotent")
    once = make_task(effect_class="exactly_once")
    attempt = Attempt("t1", 1)
    from courier_core.events import EventType

    def failed_event():
        return attempt._ev(
            EventType.RESULT_READY,
            worker_id="w1",
            result_id="r1",
            payload={"artifacts": [{"path": "o", "sha256": "0" * 64}], "outcome": "failure"},
        )

    v_idem = run_verifier(lambda name: None, idem, failed_event(), Path("/tmp"))
    v_once = run_verifier(lambda name: None, once, failed_event(), Path("/tmp"))
    assert v_idem.retryable is True
    assert v_once.retryable is False
    assert "worker reported failure" in v_idem.reason


def test_missing_outcome_counts_as_failure():
    # Journaled RESULT_READY always carries outcome (Event validation), but
    # run_verifier stays fail-closed if outcome is absent (defensive branch).
    from types import SimpleNamespace

    task = make_task()
    event = SimpleNamespace(payload={})
    verdict = run_verifier(lambda name: None, task, event, Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.verifier["name"] == "worker_reported_failure"


def test_resolve_raises_is_load_failure_not_pass():
    task = make_task()

    def boom(name):
        raise ImportError("broken adapter module")

    verdict = run_verifier(boom, task, success_result(), Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "verifier_load_failed"
    assert "ImportError" in verdict.reason


def test_missing_verifier_is_rejected():
    task = make_task()
    verdict = run_verifier(lambda name: None, task, success_result(), Path("/tmp"))
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert verdict.verifier["name"] == "no_verifier"


def test_verifier_raising_is_rejected_fail_closed(tmp_path):
    task = make_task()

    def raiser(t, r, h):
        raise RuntimeError("kaput")

    raiser.__module__ = __name__
    verdict = run_verifier(lambda name: raiser, task, success_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.retryable is False
    assert "RuntimeError" in verdict.reason
    assert verdict.verifier["kind"] == "adapter"


@pytest.mark.parametrize("bad", [None, "ok", 123, Verdict("yes"), Verdict(None)])
def test_invalid_verdict_shapes_rejected(tmp_path, bad):
    task = make_task()

    def ret(t, r, h):
        return bad

    ret.__module__ = __name__
    verdict = run_verifier(lambda name: ret, task, success_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "verifier returned an invalid verdict"
    assert verdict.retryable is False


def test_success_passthrough_attaches_identity_and_truncates(tmp_path):
    task = make_task()

    def accept(t, r, h):
        return Verdict(True, "x" * 900, True)

    accept.__module__ = __name__
    verdict = run_verifier(lambda name: accept, task, success_result(), tmp_path)
    assert verdict.accepted is True
    assert len(verdict.reason) == 500
    assert verdict.retryable is True
    assert verdict.verifier["kind"] == "adapter"
    assert __name__ in verdict.verifier["name"]


def test_reject_passthrough_preserves_decision(tmp_path):
    task = make_task()

    def reject(t, r, h):
        return Verdict(False, "evidence mismatch", False)

    reject.__module__ = __name__
    verdict = run_verifier(lambda name: reject, task, success_result(), tmp_path)
    assert verdict.accepted is False
    assert verdict.reason == "evidence mismatch"
    assert verdict.verifier["kind"] == "adapter"


def test_verifier_identity_shape_without_file():
    def fn():
        pass

    fn.__module__ = "definitely_missing_module_xyz"
    identity = verifier_identity(fn)
    assert identity["kind"] == "adapter"
    assert "definitely_missing_module_xyz" in identity["name"]
    assert identity["version"] is None
    assert identity["source_sha256"] is None


def test_worker_failure_reason_truncated_to_500():
    task = make_task()
    attempt = Attempt("t1", 1)
    from courier_core.events import EventType

    event = attempt._ev(
        EventType.RESULT_READY,
        worker_id="w1",
        result_id="r1",
        payload={
            "artifacts": [{"path": "o", "sha256": "0" * 64}],
            "outcome": "failure",
            "reason": "z" * 900,
        },
    )
    verdict = run_verifier(lambda name: None, task, event, Path("/tmp"))
    assert len(verdict.reason) == 500
