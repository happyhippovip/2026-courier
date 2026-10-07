import pytest
from datetime import datetime, timezone
import tempfile
import os
from courier_overlay.state_machine import OverlayStateMachine
from courier_overlay.event_bus import emit

def test_state_machine_folds_events():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        emit(bus, "agent1", "taskA", "WORKER_CLAIMED", "Claiming task")
        emit(bus, "agent1", "taskA", "WORKER_PROGRESS", "Doing work")
        emit(bus, "agent2", "taskB", "WORKER_CLAIMED", "Claiming B")
        
        sm = OverlayStateMachine(bus)
        sm.sync()
        
        snap = sm.get_snapshot()
        assert len(snap) == 2
        
        w1 = next(w for w in snap if w.agent_id == "agent1")
        assert w1.status == "WORKING"
        assert w1.current_task == "taskA"
        
        w2 = next(w for w in snap if w.agent_id == "agent2")
        assert w2.status == "ASSIGNED"
        
        emit(bus, "agent1", "taskA", "TASK_COMPLETE", "Done")
        sm.sync()
        w1_done = next(w for w in sm.get_snapshot() if w.agent_id == "agent1")
        assert w1_done.status == "IDLE"
        assert w1_done.current_task is None
