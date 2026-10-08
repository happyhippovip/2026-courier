import pytest
from datetime import datetime
from courier_overlay.state_machine import OverlayStateMachine, WorkerState

def test_event_to_animation_mapping():
    # We use a dummy bus path; we will just push events manually
    sm = OverlayStateMachine("dummy_path")
    
    # 1. TASK_ASSIGNED
    sm.process_event({
        "agent_id": "W11",
        "event_type": "TASK_ASSIGNED",
        "task_id": "t-1",
        "short_summary": "Assigned task",
        "timestamp": datetime.now().isoformat()
    })
    
    workers = sm.get_snapshot()
    assert len(workers) == 1
    assert workers[0].agent_id == "W11"
    assert workers[0].status == "ASSIGNED"
    assert workers[0].current_task == "t-1"
    
    # 2. WORKER_STARTED -> WORKING
    sm.process_event({
        "agent_id": "W11",
        "event_type": "WORKER_STARTED",
        "task_id": "t-1",
        "short_summary": "Started working",
        "timestamp": datetime.now().isoformat()
    })
    assert sm.workers["W11"].status == "WORKING"
    
    # 3. TASK_BLOCKED -> BLOCKED
    sm.process_event({
        "agent_id": "W11",
        "event_type": "TASK_BLOCKED",
        "task_id": "t-1",
        "short_summary": "Hit a wall",
        "timestamp": datetime.now().isoformat()
    })
    assert sm.workers["W11"].status == "BLOCKED"
    
    # 4. TASK_COMPLETE -> IDLE
    sm.process_event({
        "agent_id": "W11",
        "event_type": "TASK_COMPLETE",
        "task_id": "t-1",
        "short_summary": "Done",
        "timestamp": datetime.now().isoformat()
    })
    assert sm.workers["W11"].status == "IDLE"
    assert sm.workers["W11"].current_task is None

