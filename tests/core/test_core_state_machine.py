"""L2 invariants: the task state machine (pure, no database)."""

import random

import pytest

from core_builders import (
    Attempt, created, golden_path, task_event, transient_twice_then_success, worker_killed_then_retried,
)
from courier_core.events import EventType
from courier_core.projection import fold
from courier_core.state_machine import Decision, TaskStatus, TransitionError, apply, decide_after_failure


def run(events, state=None):
    for event in events:
        state = apply(state, event)
    return state


def test_decide_after_failure_requires_retry_pending():
    state = run([created()])
    with pytest.raises(ValueError, match="not RETRY_PENDING"):
        decide_after_failure(state)


def test_apply_requires_matching_task_id():
    state = run([created("task_a")])
    with pytest.raises(TransitionError, match="event belongs to another task"):
        apply(state, task_event(EventType.TASK_CANCEL_REQUESTED, task_id="task_b"))


def test_golden_path_statuses():
    statuses = []
    state = None
    for event in golden_path():
        state = apply(state, event)
        statuses.append(state.status)
    assert statuses == [TaskStatus.QUEUED, TaskStatus.CLAIMED, TaskStatus.RUNNING, TaskStatus.VERIFYING,
                        TaskStatus.ACCEPTED, TaskStatus.COMPLETE]
    assert state.attempt == 1 and state.accepted_result_id == "r-t1-1"


def test_task_is_created_once_and_events_need_an_existing_task():
    with pytest.raises(TransitionError, match="already exists"):
        run([created(), created()])
    with pytest.raises(TransitionError, match="unknown task"):
        apply(None, Attempt().claimed())


def test_attempts_are_claimed_in_order_and_bounded():
    queued = run([created(max_attempts=1)])
    with pytest.raises(TransitionError, match="next attempt must be 1"):
        apply(queued, Attempt(attempt=2).claimed())
    a = Attempt()
    failed_once = run([a.claimed(), a.started(), a.lease_expired()], queued)
    assert decide_after_failure(failed_once) is Decision.FAIL
    with pytest.raises(TransitionError, match="retry forbidden"):
        apply(failed_once, a.retry_scheduled())


@pytest.mark.parametrize("bad", ["other_dispatch", "other_worker", "other_attempt"])
def test_dispatch_fencing(bad):
    a = Attempt()
    claimed = run([created(), a.claimed()])
    intruder = Attempt(worker_id="intruder") if bad == "other_worker" else Attempt()
    if bad == "other_dispatch":
        intruder.dispatch_id = "d-forged"
    if bad == "other_attempt":
        intruder.attempt = 2
    with pytest.raises(TransitionError):
        apply(claimed, intruder.started())


def test_result_requires_a_started_attempt_and_completion_requires_acceptance():
    a = Attempt()
    claimed = run([created(), a.claimed()])
    with pytest.raises(TransitionError, match="running attempt"):
        apply(claimed, a.result_ready())
    verifying = run([a.started(), a.result_ready()], claimed)
    with pytest.raises(TransitionError, match="accepted result"):
        apply(verifying, a.complete())
    with pytest.raises(TransitionError, match="another result"):
        apply(verifying, a._ev(EventType.RESULT_ACCEPTED, result_id="other"))


def test_terminal_states_are_final_and_completion_is_exactly_once():
    a = Attempt()
    done = run(golden_path())
    for event in (a.complete(), a.claimed(), task_event(EventType.TASK_CANCEL_REQUESTED)):
        with pytest.raises(TransitionError, match="terminal"):
            apply(done, event)


def test_transient_rejections_retry_until_success():
    state = run(transient_twice_then_success("t2"))
    assert state.status is TaskStatus.COMPLETE and state.attempt == 3


def test_non_retryable_rejection_fails_the_task():
    a = Attempt()
    rejected = run([created(), a.claimed(), a.started(), a.result_ready(), a.rejected(retryable=False)])
    assert decide_after_failure(rejected) is Decision.FAIL
    with pytest.raises(TransitionError):
        apply(rejected, a.retry_scheduled())
    assert apply(rejected, task_event(EventType.TASK_FAILED, reason="rejected")).status is TaskStatus.FAILED


def test_lease_loss_of_idempotent_task_is_retried():
    state = run(worker_killed_then_retried("t3"))
    assert state.status is TaskStatus.COMPLETE and state.attempt == 2 and state.late_results == 1


def test_uncertain_non_idempotent_outcome_is_blocked_never_retried():
    a = Attempt()
    lost = run([created(effect_class="non_idempotent"), a.claimed(), a.started(), a.lease_expired()])
    assert decide_after_failure(lost) is Decision.BLOCK
    for forbidden in (a.retry_scheduled(), task_event(EventType.TASK_FAILED, reason="x")):
        with pytest.raises(TransitionError):
            apply(lost, forbidden)
    blocked = apply(lost, task_event(EventType.TASK_BLOCKED, reason="uncertain non-idempotent outcome"))
    assert blocked.status is TaskStatus.BLOCKED
    with pytest.raises(TransitionError, match="human decision"):
        apply(blocked, Attempt(attempt=2).claimed())
    with pytest.raises(TransitionError, match="needs an actor"):
        run([task_event(EventType.TASK_CANCEL_REQUESTED), task_event(EventType.TASK_CANCELLED)], blocked)
    cancelled = run([task_event(EventType.TASK_CANCEL_REQUESTED),
                     task_event(EventType.TASK_CANCELLED, actor="desk:ana")], blocked)
    assert cancelled.status is TaskStatus.CANCELLED
    assert cancelled.resolution == "cancelled_effect_unknown" and cancelled.decided_by == "desk:ana"


def test_non_idempotent_attempt_that_never_started_may_be_retried():
    a = Attempt()
    lost = run([created(effect_class="non_idempotent"), a.claimed(), a.lease_expired()])
    assert decide_after_failure(lost) is Decision.RETRY
    assert apply(lost, a.retry_scheduled()).status is TaskStatus.QUEUED


def test_restart_grace_expiry_is_a_lease_loss():
    a = Attempt()
    lost = run([created(), a.claimed(), a.started(), a.lease_expired(reason="restart_grace")])
    assert lost.status is TaskStatus.RETRY_PENDING and lost.last_reason == "lease_expired:restart_grace"


def test_cancellation():
    a = Attempt()
    running = run([created(), a.claimed(), a.started()])
    requested = apply(running, task_event(EventType.TASK_CANCEL_REQUESTED))
    assert requested.status is TaskStatus.RUNNING and requested.cancel_requested
    with pytest.raises(TransitionError, match="already requested"):
        apply(requested, task_event(EventType.TASK_CANCEL_REQUESTED))
    assert apply(requested, task_event(EventType.TASK_CANCELLED)).status is TaskStatus.CANCELLED
    queued = run([created("tq"), task_event(EventType.TASK_CANCEL_REQUESTED, task_id="tq")])
    with pytest.raises(TransitionError, match="cancellation was requested"):
        apply(queued, Attempt("tq").claimed())
    with pytest.raises(TransitionError, match="not requested"):
        apply(run([created("tx")]), task_event(EventType.TASK_CANCELLED, task_id="tx"))


def test_late_results_never_change_the_outcome():
    a = Attempt()
    running = run([created(), a.claimed(), a.started()])
    with pytest.raises(TransitionError, match="not late"):
        apply(running, a.late_result())
    with pytest.raises(TransitionError, match="not late"):
        apply(running, a._ev(EventType.LATE_RESULT_DISCARDED, dispatch_id=running.dispatch_id, result_id="r1", payload={"reason": "x"}))
    done = run(golden_path())
    after = apply(done, a.late_result())
    assert after.status is TaskStatus.COMPLETE and after.late_results == 1


def test_task_blocked_requires_queued_or_retry_pending():
    a = Attempt()
    running = run([created(), a.claimed(), a.started()])
    with pytest.raises(TransitionError, match="only a queued or failed attempt can be blocked"):
        apply(running, task_event(EventType.TASK_BLOCKED, reason="reason"))


def test_retry_authorized_fails_if_cancel_requested_or_max_attempts_limit():
    from courier_core.events import MAX_ATTEMPTS_LIMIT
    a = Attempt()
    lost = run([created(effect_class="non_idempotent"), a.claimed(), a.started(), a.lease_expired()])
    blocked = apply(lost, task_event(EventType.TASK_BLOCKED, reason="uncertain"))
    
    # Cancel requested blocks RETRY_AUTHORIZED
    cancel_requested = apply(blocked, task_event(EventType.TASK_CANCEL_REQUESTED))
    with pytest.raises(TransitionError, match="cancellation was requested; cancel or confirm the effect instead"):
        apply(cancel_requested, a._ev(EventType.RETRY_AUTHORIZED, payload={"actor": "a", "reason": "r"}))
        
    # max attempts
    from dataclasses import replace
    exhausted_blocked = replace(blocked, attempt=MAX_ATTEMPTS_LIMIT)
    exhausted_attempt = Attempt(attempt=MAX_ATTEMPTS_LIMIT)
    with pytest.raises(TransitionError, match="attempt limit"):
        apply(exhausted_blocked, exhausted_attempt._ev(EventType.RETRY_AUTHORIZED, payload={"actor": "a", "reason": "r"}))


def test_fold_is_deterministic():
    events = worker_killed_then_retried("tf")
    assert fold(events) == fold(list(events))


def test_random_event_storm_never_breaks_invariants():
    """Throw random (mostly illegal) events at the machine; legal ones must keep the invariants."""
    rng = random.Random(20261001)
    for trial in range(200):
        task_id = f"r{trial}"
        effect = rng.choice(["idempotent", "non_idempotent"])
        max_attempts = rng.randint(1, 3)
        state = apply(None, created(task_id, effect_class=effect, max_attempts=max_attempts))
        completions = 0
        for _ in range(60):
            a = Attempt(task_id, rng.randint(1, 4), worker_id=rng.choice(["w1", "w2"]))
            if rng.random() < 0.3:
                a.dispatch_id = rng.choice([a.dispatch_id, "d-forged", f"d-{task_id}-1"])
            candidates = [a.claimed(), a.started(), a.progress(), a.result_ready(), a.accepted(), a.rejected(),
                          a.rejected(retryable=False), a.complete(), a.lease_expired(), a.retry_scheduled(),
                          a.late_result(), task_event(EventType.TASK_BLOCKED, task_id=task_id, reason="x"),
                          task_event(EventType.TASK_FAILED, task_id=task_id, reason="x"),
                          task_event(EventType.TASK_CANCEL_REQUESTED, task_id=task_id),
                          task_event(EventType.TASK_CANCELLED, task_id=task_id)]
            event = rng.choice(candidates)
            before = state
            try:
                state = apply(state, event)
            except TransitionError:
                continue
            if event.type is EventType.TASK_COMPLETE:
                completions += 1
            assert completions <= 1
            assert state.attempt <= state.max_attempts
            if state.status is TaskStatus.COMPLETE:
                assert state.accepted_result_id is not None
            if event.type is EventType.TASK_RETRY_SCHEDULED:
                assert not (before.failure_kind == "lease_lost" and before.started
                            and before.effect_class == "non_idempotent")
            if before.status in (TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED):
                assert event.type is EventType.LATE_RESULT_DISCARDED and state.status is before.status


def test_completion_must_name_the_accepted_result():
    a = Attempt()
    accepted = run([created(), a.claimed(), a.started(), a.result_ready(), a.accepted()])
    with pytest.raises(TransitionError, match="not accepted"):
        apply(accepted, a._ev(EventType.TASK_COMPLETE, result_id="r-other"))
    assert apply(accepted, a.complete()).status is TaskStatus.COMPLETE


def test_claim_beyond_max_attempts_is_refused_even_from_a_queued_state():
    """Defense in depth: the retry rule already keeps this state unreachable."""
    from dataclasses import replace
    exhausted = replace(run([created(max_attempts=2)]), attempt=2)
    with pytest.raises(TransitionError, match="max_attempts 2 exhausted"):
        apply(exhausted, Attempt(attempt=3).claimed())


def test_uncertain_non_idempotent_outcome_outranks_a_cancel_request():
    a = Attempt()
    lost = run([created(effect_class="non_idempotent"), a.claimed(), a.started(),
                task_event(EventType.TASK_CANCEL_REQUESTED), a.lease_expired()])
    assert decide_after_failure(lost) is Decision.BLOCK
    with pytest.raises(TransitionError, match="BLOCKED before it can be cancelled"):
        apply(lost, task_event(EventType.TASK_CANCELLED))
    blocked = apply(lost, task_event(EventType.TASK_BLOCKED, reason="uncertain"))
    cancelled = apply(blocked, task_event(EventType.TASK_CANCELLED, actor="desk:ana"))
    assert cancelled.status is TaskStatus.CANCELLED and cancelled.resolution == "cancelled_effect_unknown"
