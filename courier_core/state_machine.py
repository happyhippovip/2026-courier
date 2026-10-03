"""Task state machine: the pure fold from events to per-task state.

apply(state, event) either returns the next TaskState or raises
TransitionError. The journal calls it inside the append transaction, so an
event that would break an invariant is never written; replay calls the same
function, so live state and rebuilt state cannot diverge.

Invariants enforced here:
- one creation per task; terminal states (COMPLETE, FAILED, CANCELLED) accept
  nothing but LATE_RESULT_DISCARDED; BLOCKED accepts only a human decision;
- attempts are claimed strictly in order, never beyond max_attempts;
- dispatch fencing: STARTED / PROGRESS / RESULT_READY / LEASE_EXPIRED must
  carry the current attempt, dispatch_id and worker_id;
- a result is accepted at most once and only the accepted result completes
  the task (exactly-once completion);
- only an effect explicitly classified "idempotent" may be retried
  automatically after an uncertain outcome; every other class, including
  any class this build does not know, fails closed: a started attempt whose
  outcome is unknown (lease lost) is BLOCKED, never retried, and a pending
  cancel request does not outrank that uncertainty;
- a BLOCKED task leaves BLOCKED only by a human decision carrying an actor:
  EFFECT_CONFIRMED (the effect happened; COMPLETE without re-executing it),
  RETRY_AUTHORIZED (one fresh, fenced attempt) or cancellation. Each names
  the blocked attempt, so a stale decision cannot act on a later block;
- lease deadlines are not state: the projection keeps the TTL duration only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any

from courier_core.events import (
    MAX_ATTEMPTS_LIMIT, RETRY_SAFE_EFFECT_CLASS, SYSTEM_EVENTS, Event, EventType,
)


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    ACCEPTED = "ACCEPTED"
    RETRY_PENDING = "RETRY_PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


TERMINAL = frozenset({TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED})

# TaskState.resolution: how a task reached COMPLETE, or that it was cancelled
# while its effect was unknown. A human confirmation is never shown as verified.
RESOLVED_VERIFIED = "verified"
RESOLVED_EFFECT_CONFIRMED = "effect_confirmed"
RESOLVED_CANCELLED_EFFECT_UNKNOWN = "cancelled_effect_unknown"
ACTIVE_LEASE = frozenset({TaskStatus.CLAIMED, TaskStatus.RUNNING})


class TransitionError(ValueError):
    """The event is not a legal next step for the task."""


class Decision(str, Enum):
    RETRY = "retry"
    FAIL = "fail"
    BLOCK = "block"
    CANCEL = "cancel"


@dataclass(frozen=True)
class TaskState:
    task_id: str
    status: TaskStatus
    adapter: str
    params: dict
    effect_class: str
    max_attempts: int
    lease_ttl_s: int
    timeout_s: int | None
    attempt: int = 0
    dispatch_id: str | None = None
    worker_id: str | None = None
    started: bool = False
    pending_result_id: str | None = None
    accepted_result_id: str | None = None
    cancel_requested: bool = False
    failure_kind: str | None = None
    retryable: bool | None = None
    last_reason: str | None = None
    late_results: int = 0
    resolution: str | None = None
    decided_by: str | None = None
    created_seq: int | None = None
    updated_seq: int | None = None

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["status"] = self.status.value
        return record

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "TaskState":
        values = dict(record)
        values["status"] = TaskStatus(values["status"])
        return cls(**values)


def _fail(event: Event, state: TaskState | None, why: str) -> TransitionError:
    status = state.status.value if state else "absent"
    return TransitionError(f"{event.type.value} for task {event.task_id} rejected in {status}: {why}")


def _fence(state: TaskState, event: Event, check_worker: bool = True) -> None:
    if event.attempt != state.attempt:
        raise _fail(event, state, f"attempt {event.attempt} is not the current attempt {state.attempt}")
    if event.dispatch_id != state.dispatch_id:
        raise _fail(event, state, "dispatch_id is not the current dispatch")
    if check_worker and event.worker_id is not None and event.worker_id != state.worker_id:
        raise _fail(event, state, "worker_id does not hold the lease")


def may_auto_retry(effect_class: str) -> bool:
    """Whitelist: only an explicitly idempotent effect is ever retried blindly."""
    return effect_class == RETRY_SAFE_EFFECT_CLASS


def decide_after_failure(state: TaskState) -> Decision:
    if state.status is not TaskStatus.RETRY_PENDING:
        raise ValueError(f"task {state.task_id} is {state.status.value}, not RETRY_PENDING")
    
    # L01/L02 Uncertainty gap: started non_idempotent tasks MUST BLOCK on failure
    if state.started and not may_auto_retry(state.effect_class):
        return Decision.BLOCK
        
    if state.cancel_requested:
        return Decision.CANCEL
        
    # Idempotent or unstarted tasks follow explicit hints or attempts
    if state.failure_kind == "rejected" and state.retryable is False:
        return Decision.BLOCK if may_auto_retry(state.effect_class) else Decision.FAIL
    if state.attempt >= state.max_attempts:
        return Decision.FAIL
    return Decision.RETRY


def apply(state: TaskState | None, event: Event) -> TaskState | None:
    """Return the task state after event; raise TransitionError if illegal."""
    if event.type in SYSTEM_EVENTS:
        return state
    if event.type is EventType.TASK_CREATED:
        if state is not None:
            raise _fail(event, state, "task already exists")
        p = event.payload
        return TaskState(
            task_id=event.task_id, status=TaskStatus.QUEUED, adapter=p["adapter"], params=p["params"],
            effect_class=p["effect_class"], max_attempts=p["max_attempts"], lease_ttl_s=p["lease_ttl_s"],
            timeout_s=p.get("timeout_s"), created_seq=event.seq, updated_seq=event.seq)
    if state is None:
        raise _fail(event, state, "unknown task")
    if event.task_id != state.task_id:
        raise _fail(event, state, "event belongs to another task")

    new = _transition(state, event)
    return replace(new, updated_seq=event.seq)


def _transition(state: TaskState, event: Event) -> TaskState:
    t = event.type
    s = state.status

    if t is EventType.LATE_RESULT_DISCARDED:
        if s in ACTIVE_LEASE and event.dispatch_id == state.dispatch_id:
            raise _fail(event, state, "result belongs to the active dispatch; it is not late")
        return replace(state, late_results=state.late_results + 1)

    if s in TERMINAL:
        raise _fail(event, state, "task is terminal")
    if s is TaskStatus.BLOCKED and t not in (EventType.TASK_CANCEL_REQUESTED, EventType.TASK_CANCELLED,
                                             EventType.EFFECT_CONFIRMED, EventType.RETRY_AUTHORIZED):
        raise _fail(event, state, "a blocked task needs a human decision")
    if t in (EventType.EFFECT_CONFIRMED, EventType.RETRY_AUTHORIZED):
        return _human_decision(state, event)

    if t is EventType.TASK_CLAIMED:
        if s is not TaskStatus.QUEUED:
            raise _fail(event, state, "only a queued task can be claimed")
        if state.cancel_requested:
            raise _fail(event, state, "cancellation was requested")
        if event.attempt != state.attempt + 1:
            raise _fail(event, state, f"next attempt must be {state.attempt + 1}")
        if event.attempt > state.max_attempts:
            raise _fail(event, state, f"max_attempts {state.max_attempts} exhausted")
        return replace(state, status=TaskStatus.CLAIMED, attempt=event.attempt, dispatch_id=event.dispatch_id,
                       worker_id=event.worker_id, started=False, pending_result_id=None,
                       failure_kind=None, retryable=None, last_reason=None)

    if t is EventType.TASK_STARTED:
        if s is not TaskStatus.CLAIMED:
            raise _fail(event, state, "only a claimed attempt can start")
        _fence(state, event)
        return replace(state, status=TaskStatus.RUNNING, started=True)

    if t is EventType.TASK_PROGRESS:
        if s is not TaskStatus.RUNNING:
            raise _fail(event, state, "progress requires a running attempt")
        _fence(state, event)
        return state

    if t is EventType.RESULT_READY:
        if s is not TaskStatus.RUNNING:
            raise _fail(event, state, "a result requires a running attempt")
        _fence(state, event)
        return replace(state, status=TaskStatus.VERIFYING, pending_result_id=event.result_id)

    if t in (EventType.RESULT_ACCEPTED, EventType.RESULT_REJECTED):
        if s is not TaskStatus.VERIFYING:
            raise _fail(event, state, "no result is being verified")
        _fence(state, event, check_worker=False)
        if event.result_id != state.pending_result_id:
            raise _fail(event, state, "verdict is for another result")
        if t is EventType.RESULT_ACCEPTED:
            return replace(state, status=TaskStatus.ACCEPTED, accepted_result_id=event.result_id,
                           pending_result_id=None, resolution=RESOLVED_VERIFIED)
        return replace(state, status=TaskStatus.RETRY_PENDING, pending_result_id=None, failure_kind="rejected",
                       retryable=event.payload["retryable"], last_reason=str(event.payload["reason"]))

    if t is EventType.TASK_COMPLETE:
        if s is not TaskStatus.ACCEPTED:
            raise _fail(event, state, "only an accepted result completes a task")
        _fence(state, event, check_worker=False)
        if event.result_id != state.accepted_result_id:
            raise _fail(event, state, "completion names a result that was not accepted")
        return replace(state, status=TaskStatus.COMPLETE)

    if t is EventType.LEASE_EXPIRED:
        if s not in ACTIVE_LEASE:
            raise _fail(event, state, "no active lease")
        _fence(state, event)
        return replace(state, status=TaskStatus.RETRY_PENDING, failure_kind="lease_lost", retryable=None,
                       last_reason=f"lease_expired:{event.payload['reason']}")

    if t is EventType.TASK_RETRY_SCHEDULED:
        if s is not TaskStatus.RETRY_PENDING:
            raise _fail(event, state, "nothing to retry")
        if event.attempt != state.attempt:
            raise _fail(event, state, "retry must name the failed attempt")
        decision = decide_after_failure(state)
        if decision is not Decision.RETRY:
            raise _fail(event, state, f"retry forbidden, required decision is {decision.value}")
        return replace(state, status=TaskStatus.QUEUED, dispatch_id=None, worker_id=None, started=False)

    if t is EventType.TASK_FAILED:
        if s not in (TaskStatus.RETRY_PENDING, TaskStatus.QUEUED):
            raise _fail(event, state, "only a queued or failed attempt can fail the task")
        if s is TaskStatus.RETRY_PENDING and decide_after_failure(state) is Decision.BLOCK:
            raise _fail(event, state, "an uncertain non-idempotent outcome must be BLOCKED, not FAILED")
        return replace(state, status=TaskStatus.FAILED, last_reason=str(event.payload["reason"]))

    if t is EventType.TASK_BLOCKED:
        if s not in (TaskStatus.RETRY_PENDING, TaskStatus.QUEUED):
            raise _fail(event, state, "only a queued or failed attempt can be blocked")
        return replace(state, status=TaskStatus.BLOCKED, last_reason=str(event.payload["reason"]))

    if t is EventType.TASK_CANCEL_REQUESTED:
        if state.cancel_requested:
            raise _fail(event, state, "cancellation already requested")
        return replace(state, cancel_requested=True)

    if t is EventType.TASK_CANCELLED:
        if not state.cancel_requested:
            raise _fail(event, state, "cancellation was not requested")
        if s in (TaskStatus.VERIFYING, TaskStatus.ACCEPTED):
            raise _fail(event, state, "a result is already being verified or accepted")
        if s is TaskStatus.RETRY_PENDING and decide_after_failure(state) is Decision.BLOCK:
            raise _fail(event, state, "an uncertain non-idempotent outcome must be BLOCKED before it can be cancelled")
        if s is TaskStatus.BLOCKED:
            # Cancelling does not make the unknown effect known: say so in the state.
            actor = event.payload.get("actor")
            if actor is None:
                raise _fail(event, state, "cancelling a blocked task is a human decision and needs an actor")
            return replace(state, status=TaskStatus.CANCELLED, resolution=RESOLVED_CANCELLED_EFFECT_UNKNOWN,
                           decided_by=actor)
        return replace(state, status=TaskStatus.CANCELLED, decided_by=event.payload.get("actor", state.decided_by))

    raise _fail(event, state, "unhandled event type")  # pragma: no cover - REQUIRED covers all types


def _human_decision(state: TaskState, event: Event) -> TaskState:
    if state.status is not TaskStatus.BLOCKED:
        raise _fail(event, state, "only a blocked task takes this human decision")
    if event.attempt != state.attempt:
        raise _fail(event, state, f"decision names attempt {event.attempt}, the blocked attempt is {state.attempt}")
    actor, reason = event.payload["actor"], str(event.payload["reason"])
    if event.type is EventType.EFFECT_CONFIRMED:
        return replace(state, status=TaskStatus.COMPLETE, resolution=RESOLVED_EFFECT_CONFIRMED, decided_by=actor,
                       last_reason=reason)
    if state.cancel_requested:
        raise _fail(event, state, "cancellation was requested; cancel or confirm the effect instead")
    if state.attempt >= MAX_ATTEMPTS_LIMIT:
        raise _fail(event, state, f"attempt limit {MAX_ATTEMPTS_LIMIT} reached")
    # The human grants exactly one fresh attempt, even if the automatic budget is spent.
    return replace(state, status=TaskStatus.QUEUED, max_attempts=max(state.max_attempts, state.attempt + 1),
                   dispatch_id=None, worker_id=None, started=False, failure_kind=None, retryable=None,
                   last_reason=reason, decided_by=actor)
