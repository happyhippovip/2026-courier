"""P9-state_machine hardening: human-decision, record and fail-closed pins.

Covers courier_core.state_machine edges that the existing core suite does not
pin directly: may_auto_retry whitelist, decide_after_failure misuse guard,
system-event passthrough, creation field mapping, record round-trip, ACCEPTED
resolution value, EFFECT_CONFIRMED / RETRY_AUTHORIZED paths and their guards,
direct QUEUED -> FAILED / BLOCKED, progress seq bump, lease fencing on
non-lease states, and cancel-decision bookkeeping. Pure in-memory events only;
no network, no subprocesses.
"""

import pytest

from core_builders import Attempt, created, golden_path, stable, task_event
from courier_core.events import Event, EventType
from courier_core.state_machine import (
    RESOLVED_CANCELLED_EFFECT_UNKNOWN,
    RESOLVED_EFFECT_CONFIRMED,
    RESOLVED_VERIFIED,
    Decision,
    TaskState,
    TaskStatus,
    TransitionError,
    apply,
    decide_after_failure,
    may_auto_retry,
)


def run(events, state=None):
    for event in events:
        state = apply(state, event)
    return state


def human_decision(event_type, task_id="t1", attempt=1, actor="human:reviewer", reason="reviewed"):
    return Event(**stable(type=event_type, task_id=task_id, attempt=attempt,
                          payload={"actor": actor, "reason": reason}))


def blocked_non_idempotent(task_id="tb"):
    a = Attempt(task_id)
    lost = run([created(task_id, effect_class="non_idempotent"), a.claimed(),
                a.started(), a.lease_expired()])
    assert decide_after_failure(lost) is Decision.BLOCK
    return run([task_event(EventType.TASK_BLOCKED, task_id=task_id, reason="uncertain")], lost)


def test_may_auto_retry_allows_only_idempotent():
    assert may_auto_retry("idempotent") is True
    assert may_auto_retry("non_idempotent") is False
    assert may_auto_retry("unknown_class") is False
    assert may_auto_retry("") is False
    assert may_auto_retry("IDEMPOTENT") is False


def test_decide_after_failure_requires_retry_pending():
    queued = run([created("tq")])
    for state in (queued, run(golden_path("tg"))):
        with pytest.raises(ValueError, match="not RETRY_PENDING"):
            decide_after_failure(state)


def test_system_events_leave_state_untouched():
    running = run([created("ts"), Attempt("ts").claimed(), Attempt("ts").started()])
    for sys_type in (EventType.CONTROLLER_STARTED, EventType.CONTROLLER_STOPPED):
        event = Event(**stable(type=sys_type))
        assert apply(running, event) is running
    assert apply(None, Event(**stable(type=EventType.CONTROLLER_STARTED))) is None


def test_creation_maps_payload_fields():
    event = created("tc", effect_class="non_idempotent", max_attempts=2, lease_ttl_s=9)
    state = apply(None, event)
    assert state.status is TaskStatus.QUEUED
    assert (state.adapter, state.params) == ("synthetic", {"sleep_s": 1})
    assert state.effect_class == "non_idempotent"
    assert (state.max_attempts, state.lease_ttl_s) == (2, 9)
    assert state.timeout_s is None and state.attempt == 0
    assert state.created_seq == event.seq and state.updated_seq == event.seq


def test_record_round_trip_preserves_state():
    state = run(golden_path("tr"))
    record = state.to_record()
    assert record["status"] == "COMPLETE"
    assert TaskState.from_record(record) == state


def test_accepted_resolution_is_verified():
    a = Attempt("ta")
    accepted = run([created("ta"), a.claimed(), a.started(), a.result_ready(), a.accepted()])
    assert accepted.status is TaskStatus.ACCEPTED
    assert accepted.resolution == RESOLVED_VERIFIED == "verified"
    assert accepted.accepted_result_id == a.result_id and accepted.pending_result_id is None


def test_effect_confirmed_completes_blocked_task():
    blocked = blocked_non_idempotent("te")
    done = apply(blocked, human_decision(EventType.EFFECT_CONFIRMED, task_id="te"))
    assert done.status is TaskStatus.COMPLETE
    assert done.resolution == RESOLVED_EFFECT_CONFIRMED == "effect_confirmed"
    assert done.decided_by == "human:reviewer"


def test_retry_authorized_requeues_with_one_fresh_attempt():
    a = Attempt("tr2")
    blocked = run([created("tr2", max_attempts=1), a.claimed(), a.started(),
                   a.lease_expired(),
                   task_event(EventType.TASK_BLOCKED, task_id="tr2", reason="uncertain")])
    assert blocked.max_attempts == 1 and blocked.attempt == 1
    queued = apply(blocked, human_decision(EventType.RETRY_AUTHORIZED, task_id="tr2"))
    assert queued.status is TaskStatus.QUEUED
    assert queued.max_attempts == 2
    assert queued.dispatch_id is None and queued.worker_id is None
    assert queued.decided_by == "human:reviewer"


def test_human_decision_names_the_blocked_attempt():
    blocked = blocked_non_idempotent("tw")
    assert blocked.attempt == 1
    with pytest.raises(TransitionError, match="blocked attempt is 1"):
        apply(blocked, human_decision(EventType.EFFECT_CONFIRMED, task_id="tw", attempt=2))
    running = run([created("tn"), Attempt("tn").claimed(), Attempt("tn").started()])
    with pytest.raises(TransitionError, match="only a blocked task"):
        apply(running, human_decision(EventType.EFFECT_CONFIRMED, task_id="tn"))


def test_retry_authorized_refused_while_cancel_requested():
    blocked = blocked_non_idempotent("tc2")
    requested = apply(blocked, task_event(EventType.TASK_CANCEL_REQUESTED, task_id="tc2"))
    assert requested.cancel_requested is True and requested.status is TaskStatus.BLOCKED
    with pytest.raises(TransitionError, match="cancellation was requested"):
        apply(requested, human_decision(EventType.RETRY_AUTHORIZED, task_id="tc2"))


def test_queued_task_can_fail_or_block_directly():
    failed = apply(run([created("tf")]), task_event(EventType.TASK_FAILED, task_id="tf", reason="bad input"))
    assert failed.status is TaskStatus.FAILED and failed.last_reason == "bad input"
    blocked = apply(run([created("tk")]), task_event(EventType.TASK_BLOCKED, task_id="tk", reason="needs a person"))
    assert blocked.status is TaskStatus.BLOCKED and blocked.last_reason == "needs a person"


def test_progress_bumps_seq_but_keeps_state():
    a = Attempt("tp")
    running = run([created("tp"), a.claimed(), a.started()])
    event = a.progress()
    after = apply(running, event)
    assert after.status is TaskStatus.RUNNING and after.attempt == running.attempt
    assert after.updated_seq == event.seq


def test_lease_expiry_needs_an_active_lease():
    a = Attempt("tl")
    queued = run([created("tl")])
    with pytest.raises(TransitionError, match="no active lease"):
        apply(queued, a.lease_expired())
    verifying = run([created("tv"), Attempt("tv").claimed(), Attempt("tv").started(),
                     Attempt("tv").result_ready()])
    with pytest.raises(TransitionError, match="no active lease"):
        apply(verifying, Attempt("tv").lease_expired())


def test_cancel_without_actor_leaves_decider_empty():
    a = Attempt("tx")
    running = run([created("tx"), a.claimed(), a.started()])
    requested = apply(running, task_event(EventType.TASK_CANCEL_REQUESTED, task_id="tx"))
    cancelled = apply(requested, task_event(EventType.TASK_CANCELLED, task_id="tx"))
    assert cancelled.status is TaskStatus.CANCELLED
    assert cancelled.decided_by is None
    assert cancelled.resolution != RESOLVED_CANCELLED_EFFECT_UNKNOWN
