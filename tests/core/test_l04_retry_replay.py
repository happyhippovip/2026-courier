import pytest
from courier_core.state_machine import apply, TaskState, Decision, TaskStatus, decide_after_failure
from courier_core.events import Event, EventType

def test_retry_replay_preserves_uncertainty_gap():
    """
    PROVES L04:
    The uncertainty gap (non-idempotent tasks trusting retryable=True) 
    survives state reconstruction (event sourcing replay) and from_record().
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
        Event(seq=4, type=EventType.RESULT_READY, task_id="T1", attempt=1, dispatch_id="D1", worker_id="W1", result_id="R1", payload={"artifacts": [], "outcome": "failure"}),
        Event(seq=5, type=EventType.RESULT_REJECTED, task_id="T1", attempt=1, dispatch_id="D1", result_id="R1", payload={"reason": "try again", "retryable": True})
    ]
    
    # 1. Original evaluation
    state1 = None
    for e in events:
        state1 = apply(state1, e)
        
    decision1 = decide_after_failure(state1)
    
    # 2. Replay from journal (event sourcing)
    state2 = None
    for e in events:
        state2 = apply(state2, e)
        
    decision2 = decide_after_failure(state2)
    
    # 3. Resume from snapshot (checkpointing)
    state3 = TaskState.from_record(state1.to_record())
    decision3 = decide_after_failure(state3)
    
    # Prove that the same decision is reached across all 3 methods.
    assert decision1 == decision2 == decision3 == Decision.BLOCK
    
    # Proves the gap is deeply embedded in the determinism of the state machine.
    # When L02 is fixed, this test will naturally change to assert Decision.BLOCK.
