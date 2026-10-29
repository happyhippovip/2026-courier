"""P9 hardening pins for courier_worker.service failure surface (tests only).

Covers the small, pure, offline pieces of courier_worker.service that have
no dedicated test file in the base tree and are not covered by the open
P9-service_* PRs (runloop, client_errors, result_payload, argv, startup,
cancel, init, pure):

- ``build_spec_failure_payload``: exact wire shape for a spec refusal.
- ``CANCEL_TYPES``: the closed set of SSE types treated as cancellation.
- Error taxonomy: ``ControllerError`` / ``ControllerUnreachable`` /
  ``StaleDispatch`` subclass relations (no network, no client needed).

No behavior change. No network, no credentials, no subprocesses.
"""

from __future__ import annotations

import pytest

from courier_worker import service as S


# -- build_spec_failure_payload ----------------------------------------------


def test_spec_failure_payload_exact_shape():
    payload = S.build_spec_failure_payload("d-1", "r-d-1", "adapter not allowlisted")
    assert payload == {
        "dispatch_id": "d-1",
        "result_id": "r-d-1",
        "artifacts": [],
        "outcome": "failure",
        "retryable": False,
        "reason": "adapter not allowlisted",
    }


def test_spec_failure_payload_is_always_non_retryable_failure():
    payload = S.build_spec_failure_payload("d-2", "r-d-2", "boom")
    assert payload["outcome"] == "failure"
    assert payload["retryable"] is False
    assert payload["artifacts"] == []


def test_spec_failure_payload_reason_verbatim():
    # Unlike adapter-report reasons, the spec-refusal reason is passed
    # through unchanged (no truncation or coercion in this helper).
    reason = "héllo ✓ " * 40
    payload = S.build_spec_failure_payload("d-3", "r-d-3", reason)
    assert payload["reason"] == reason
    assert payload["reason"] is reason


def test_spec_failure_payload_empty_reason():
    payload = S.build_spec_failure_payload("d-4", "r-d-4", "")
    assert payload["reason"] == ""
    assert payload["outcome"] == "failure"


def test_spec_failure_payload_ids_verbatim():
    payload = S.build_spec_failure_payload("dispatch-1.2_3", "r-dispatch-1.2_3", "x")
    assert payload["dispatch_id"] == "dispatch-1.2_3"
    assert payload["result_id"] == "r-dispatch-1.2_3"


def test_spec_failure_payload_returns_fresh_dict():
    first = S.build_spec_failure_payload("d-5", "r-d-5", "a")
    first["artifacts"].append({"path": "mutated", "sha256": "0" * 64})
    first["reason"] = "mutated"
    second = S.build_spec_failure_payload("d-5", "r-d-5", "a")
    assert second["artifacts"] == []
    assert second["reason"] == "a"


# -- CANCEL_TYPES --------------------------------------------------------------


def test_cancel_types_exact_members():
    assert set(S.CANCEL_TYPES) == {"TASK_CANCEL_REQUESTED", "TASK_CANCELLED"}


def test_cancel_types_is_immutable_set():
    assert isinstance(S.CANCEL_TYPES, frozenset)
    with pytest.raises(AttributeError):
        S.CANCEL_TYPES.add("TASK_CANCELLED")  # type: ignore[attr-defined]


def test_cancel_types_membership():
    assert "TASK_CANCEL_REQUESTED" in S.CANCEL_TYPES
    assert "TASK_CANCELLED" in S.CANCEL_TYPES
    assert "TASK_CREATED" not in S.CANCEL_TYPES
    assert "RESULT_READY" not in S.CANCEL_TYPES
    assert "" not in S.CANCEL_TYPES


# -- error taxonomy --------------------------------------------------------------


def test_controller_error_is_runtime_error():
    assert issubclass(S.ControllerError, RuntimeError)


def test_unreachable_and_stale_are_controller_errors():
    assert issubclass(S.ControllerUnreachable, S.ControllerError)
    assert issubclass(S.StaleDispatch, S.ControllerError)
    assert S.ControllerUnreachable is not S.StaleDispatch


def test_errors_catchable_as_controller_error():
    with pytest.raises(S.ControllerError):
        raise S.ControllerUnreachable("no controller at startup")
    with pytest.raises(S.ControllerError):
        raise S.StaleDispatch("dispatch gone")
    with pytest.raises(S.ControllerError):
        raise S.ControllerError("down")


def test_error_siblings_are_distinct():
    assert not issubclass(S.StaleDispatch, S.ControllerUnreachable)
    assert not issubclass(S.ControllerUnreachable, S.StaleDispatch)
    err = S.StaleDispatch("gone")
    assert isinstance(err, S.ControllerError)
    assert not isinstance(err, S.ControllerUnreachable)
