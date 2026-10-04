import pytest
from courier_core.state_machine import apply, TaskState, Decision, TaskStatus, _fail
from courier_core.events import Event, EventType

def test_non_idempotent_rejected_with_retryable_true_is_retried():
    """
    PROVES L01 gap:
    A non-idempotent task that reaches the worker (started=True),
    and is subsequently REJECTED with retryable=True,
    is currently blindly trusted and allowed to RETRY automatically,
    even though it might have caused partial side effects.
    """
    
    payload_created = {
        "effect_class": "non_idempotent",
        "adapter": "synthetic",
        "params": {},
        "max_attempts": 3,
        "lease_ttl_s": 60,
    }
    
    events = [
        Event(seq=1, type=EventType.TASK_CREATED, task_id="T1", attempt=1, payload=payload_created),
        Event(seq=2, type=EventType.TASK_CLAIMED, task_id="T1", attempt=1, dispatch_id="D1", worker_id="W1", payload={"ttl_s": 60}),
        Event(seq=3, type=EventType.TASK_STARTED, task_id="T1", attempt=1, dispatch_id="D1", worker_id="W1", payload={}),
        Event(seq=4, type=EventType.RESULT_READY, task_id="T1", attempt=1, dispatch_id="D1", worker_id="W1", result_id="R1", payload={"artifacts": [], "status": "FAILED"}),
        # The worker/adapter returns a failure but maliciously/incorrectly claims retryable=True
        Event(seq=5, type=EventType.RESULT_REJECTED, task_id="T1", attempt=1, dispatch_id="D1", result_id="R1", payload={"reason": "failed but try again", "retryable": True})
    ]
    
    state = None
    for e in events:
        state = apply(state, e)
        
    assert state.status == TaskStatus.RETRY_PENDING
    assert state.retryable is True
    
    # Check the decision logic
    from courier_core.state_machine import decide_after_failure
    decision = decide_after_failure(state)
    
    # GAP PROVED: The system decides to RETRY instead of BLOCK, 
    # fully trusting the worker's retryable=True on a non-idempotent task.
    assert decision == Decision.BLOCK

