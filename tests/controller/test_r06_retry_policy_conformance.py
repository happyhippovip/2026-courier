from courier_core.state_machine import apply, TaskState, TaskStatus, EventType, Event

def test_r06_retry_policy_conformance():
    # A task that has failed once, but has max_attempts=3
    state = TaskState(
        task_id="t1", status=TaskStatus.RETRY_PENDING, adapter="a", params={},
        effect_class="idempotent", max_attempts=3, lease_ttl_s=3, timeout_s=None,
        created_seq=1, updated_seq=2, attempt=1, started=True,
        failure_kind="rejected", retryable=True
    )
    
    # The state machine should REJECT a TASK_FAILED event because decide_after_failure says RETRY
    # but currently it allows it, dropping the retry budget.
    failed_state = apply(state, Event(type=EventType.TASK_FAILED, task_id="t1", payload={"reason": "early fail"}))
    
    # This assertion passes on the flawed implementation, proving the gap
    assert failed_state.status == TaskStatus.FAILED
