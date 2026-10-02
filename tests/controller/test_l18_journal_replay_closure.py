import pytest
from pathlib import Path
from courier_core.events import EventType, Event
from courier_core.state_machine import TaskStatus, apply, TransitionError
from courier_core.journal import Journal

def test_l18_journal_replay_closure_prevents_illegal_transitions(tmp_path):
    # This proves that every state rejects inappropriate replay events
    
    # 1. Start with a created task
    t = Event(type=EventType.TASK_CREATED, task_id="t1", payload={"adapter": "dummy", "params": {}, "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 60})
    state = apply(None, t)
    
    # Prove that replaying creation fails
    with pytest.raises(TransitionError, match="task already exists"):
        apply(state, t)
        
    # 2. Claim it
    t_claim = Event(type=EventType.TASK_CLAIMED, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1", payload={"ttl_s": 60})
    state = apply(state, t_claim)
    
    # Prove that replaying claim fails
    with pytest.raises(TransitionError, match="only a queued task can be claimed"):
        apply(state, t_claim)
        
    # 3. Start it
    t_start = Event(type=EventType.TASK_STARTED, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1", payload={})
    state = apply(state, t_start)
    
    # Prove that replaying start fails
    with pytest.raises(TransitionError, match="only a claimed attempt can start"):
        apply(state, t_start)
        
    # 4. Result ready
    t_result = Event(type=EventType.RESULT_READY, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1", result_id="r1", payload={"outcome": "success", "artifacts": []})
    state = apply(state, t_result)
    
    # Prove that replaying result ready fails
    with pytest.raises(TransitionError, match="a result requires a running attempt"):
        apply(state, t_result)
        
    # 5. Accepted
    t_accepted = Event(type=EventType.RESULT_ACCEPTED, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1", result_id="r1", payload={"reason": "looks good", "verifier": {}})
    state = apply(state, t_accepted)
    
    # Prove that replaying accepted fails
    with pytest.raises(TransitionError, match="no result is being verified"):
        apply(state, t_accepted)
        
    # 6. Complete
    t_complete = Event(type=EventType.TASK_COMPLETE, task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1", result_id="r1", payload={})
    state = apply(state, t_complete)
    
    # Prove that replaying complete fails
    with pytest.raises(TransitionError, match="task is terminal"):
        apply(state, t_complete)
