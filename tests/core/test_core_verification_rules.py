"""Rule pins for courier_core.verification.run_verifier.

Covers the fail-closed decision matrix around the adapter verdict:
worker-reported failures, loader failures, missing/raising/malformed
verifiers, and the success/adapters-reject pass-through (reason bound,
retryable coercion, verifier identity attached). Pure unit tests only:
no network, no filesystem writes, no credentials.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_core.verification import Verdict, _rule, run_verifier


def _task(adapter: str = "synthetic", effect_class: str = "idempotent") -> TaskState:
    return TaskState(
        task_id="t-1",
        status=TaskStatus.VERIFYING,
        adapter=adapter,
        params={},
        effect_class=effect_class,
        max_attempts=3,
        lease_ttl_s=30,
        timeout_s=10,
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
    )


def _result(payload: dict) -> Event:
    merged: dict = {"artifacts": []}
    merged.update(payload)
    return Event(
        type=EventType.RESULT_READY,
        task_id="t-1",
        attempt=1,
        dispatch_id="d-1",
        worker_id="w-1",
        result_id="r-1",
        payload=merged,
    )


def _success(payload: dict | None = None) -> Event:
    base: dict = {"outcome": "success", "artifacts": []}
    if payload:
        base.update(payload)
    return _result(base)


def _ok_verifier(task: TaskState, result: Event, home: Path) -> Verdict:
    return Verdict(True, "evidence checks out", False)


class TestWorkerReportedFailure:
    def test_failure_outcome_is_rejected_with_rule_identity(self):
        verdict = run_verifier(lambda adapter: _ok_verifier, _task(),
                               _result({"outcome": "failure", "reason": "boom"}), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.reason == "boom"
        assert verdict.verifier == {"kind": "courier_rule",
                                    "name": "worker_reported_failure",
                                    "adapter": "synthetic"}

    def test_missing_reason_gets_default_text(self):
        verdict = run_verifier(lambda adapter: _ok_verifier, _task(),
                               _result({"outcome": "failure"}), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.reason == "worker reported failure"

    def test_missing_outcome_counts_as_failure(self):
        # An outcome-less payload cannot pass journal validation, so exercise
        # the defensive branch with a minimal payload carrier instead.
        bare = SimpleNamespace(payload={"artifacts": []})
        verdict = run_verifier(lambda adapter: _ok_verifier, _task(), bare, Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.verifier is not None and verdict.verifier["name"] == "worker_reported_failure"

    def test_long_reason_is_bounded(self):
        verdict = run_verifier(lambda adapter: _ok_verifier, _task(),
                               _result({"outcome": "failure", "reason": "x" * 900}), Path("/tmp"))
        assert verdict.reason == "x" * 500

    def test_explicit_retryable_is_honored(self):
        yes = run_verifier(lambda adapter: _ok_verifier, _task(effect_class="side_effecting"),
                           _result({"outcome": "failure", "retryable": True}), Path("/tmp"))
        no = run_verifier(lambda adapter: _ok_verifier, _task(effect_class="idempotent"),
                          _result({"outcome": "failure", "retryable": False}), Path("/tmp"))
        assert yes.retryable is True
        assert no.retryable is False

    def test_default_retryable_follows_effect_class(self):
        idempotent = run_verifier(lambda adapter: _ok_verifier, _task(effect_class="idempotent"),
                                  _result({"outcome": "failure"}), Path("/tmp"))
        side_effecting = run_verifier(lambda adapter: _ok_verifier, _task(effect_class="side_effecting"),
                                      _result({"outcome": "failure"}), Path("/tmp"))
        assert idempotent.retryable is True
        assert side_effecting.retryable is False

    def test_rule_helper_shape(self):
        assert _rule("worker_reported_failure", "synthetic") == {
            "kind": "courier_rule", "name": "worker_reported_failure", "adapter": "synthetic"}


class TestLoaderAndVerifierFailures:
    def test_resolve_raising_rejects_without_retry(self):
        def _broken(adapter: str):
            raise ImportError("nope")

        verdict = run_verifier(_broken, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.retryable is False
        assert "ImportError" in verdict.reason
        assert verdict.verifier == {"kind": "courier_rule",
                                    "name": "verifier_load_failed",
                                    "adapter": "synthetic"}

    def test_no_verifier_rejects_without_retry(self):
        verdict = run_verifier(lambda adapter: None, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.retryable is False
        assert verdict.verifier == {"kind": "courier_rule",
                                    "name": "no_verifier",
                                    "adapter": "synthetic"}

    def test_verifier_raising_rejects_and_keeps_identity(self):
        def _raising(task: TaskState, result: Event, home: Path) -> Verdict:
            raise RuntimeError("evidence store gone")

        verdict = run_verifier(lambda adapter: _raising, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.retryable is False
        assert verdict.reason == "verifier raised RuntimeError"
        assert verdict.verifier is not None and verdict.verifier["kind"] == "adapter"

    def test_verifier_returning_non_verdict_is_rejected(self):
        def _wrong(task: TaskState, result: Event, home: Path):
            return {"accepted": True}

        verdict = run_verifier(lambda adapter: _wrong, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.retryable is False
        assert verdict.reason == "verifier returned an invalid verdict"
        assert verdict.verifier is not None and verdict.verifier["kind"] == "adapter"

    def test_verdict_with_non_bool_accepted_is_rejected(self):
        def _sloppy(task: TaskState, result: Event, home: Path) -> Verdict:
            return Verdict(accepted=1)  # type: ignore[arg-type]

        verdict = run_verifier(lambda adapter: _sloppy, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.reason == "verifier returned an invalid verdict"


class TestVerdictPassThrough:
    def test_accept_is_returned_with_identity_attached(self):
        verdict = run_verifier(lambda adapter: _ok_verifier, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is True
        assert verdict.reason == "evidence checks out"
        assert verdict.retryable is False
        assert verdict.verifier is not None
        assert verdict.verifier["kind"] == "adapter"
        assert verdict.verifier["name"].endswith("_ok_verifier")

    def test_adapter_rejection_keeps_retryable(self):
        def _reject(task: TaskState, result: Event, home: Path) -> Verdict:
            return Verdict(False, "bad evidence", True)

        verdict = run_verifier(lambda adapter: _reject, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is False
        assert verdict.reason == "bad evidence"
        assert verdict.retryable is True
        assert verdict.verifier is not None and verdict.verifier["kind"] == "adapter"

    def test_long_reason_truncated_and_retryable_coerced(self):
        def _loose(task: TaskState, result: Event, home: Path) -> Verdict:
            return Verdict(True, "y" * 700, 1)  # type: ignore[arg-type]

        verdict = run_verifier(lambda adapter: _loose, _task(), _success(), Path("/tmp"))
        assert verdict.accepted is True
        assert verdict.reason == "y" * 500
        assert verdict.retryable is True
