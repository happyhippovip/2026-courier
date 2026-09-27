import pytest
import json
from pathlib import Path
from src.ledger import Ledger, LedgerError

def test_ledger_append_preserves_records(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    
    e1 = ledger.append_event({"event_type": "GOAL_CREATED", "goal_id": "g1"})
    e2 = ledger.append_event({"event_type": "TASK_QUEUED", "goal_id": "g1", "task_id": "t1"})
    
    events = ledger.read_events()
    assert len(events) == 2
    assert events[0]["event_id"] == e1["event_id"]
    assert events[1]["event_id"] == e2["event_id"]

def test_ledger_reload_preserves_records(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger1 = Ledger(path)
    ledger1.append_event({"event_type": "GOAL_CREATED", "goal_id": "g1"})
    
    ledger2 = Ledger(path)
    events = ledger2.read_events()
    assert len(events) == 1
    assert events[0]["goal_id"] == "g1"

def test_ledger_malformed_event_rejected(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(LedgerError):
        ledger.append_event({"event_type": "INVALID_TYPE", "goal_id": "g1"})
        
    with pytest.raises(LedgerError):
        ledger.append_event({"event_type": "GOAL_CREATED"}) # Missing goal_id

def test_ledger_read_does_not_mutate(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append_event({"event_type": "GOAL_CREATED", "goal_id": "g1"})
    
    before = path.read_text()
    ledger.read_events()
    after = path.read_text()
    assert before == after

def test_ledger_multiple_tasks_ordered(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append_event({"event_type": "TASK_QUEUED", "goal_id": "g1", "task_id": "t1"})
    ledger.append_event({"event_type": "TASK_QUEUED", "goal_id": "g1", "task_id": "t2"})
    
    events = ledger.events_for_goal("g1")
    assert events[0]["task_id"] == "t1"
    assert events[1]["task_id"] == "t2"

def test_ledger_distinct_attempts(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append_event({"event_type": "WORK_STARTED", "goal_id": "g1", "task_id": "t1", "attempt_id": "a1"})
    ledger.append_event({"event_type": "WORK_STARTED", "goal_id": "g1", "task_id": "t1", "attempt_id": "a2"})
    
    events = ledger.events_for_task("t1")
    assert len(events) == 2
    assert events[0]["attempt_id"] == "a1"
    assert events[1]["attempt_id"] == "a2"

def test_ledger_event_integrity(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    e = ledger.append_event({"event_type": "GOAL_CREATED", "goal_id": "g1"})
    
    # Manually tamper with the file
    content = path.read_text()
    tampered = content.replace('"g1"', '"g2"')
    path.write_text(tampered)
    
    # Should be rejected during read (returns empty list if all are invalid)
    events = ledger.read_events()
    assert len(events) == 0


def test_ledger_duplicate_event_explicit(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    e1 = ledger.append_event({"event_type": "GOAL_CREATED", "goal_id": "g1"})
    
    # Should probably reject or handle explicit duplicate
    # We will just append it again and it should get a new event_id but identical payload
    e2 = ledger.append_event({"event_type": "GOAL_CREATED", "goal_id": "g1"})
    assert e1["event_id"] != e2["event_id"]
    

def test_ledger_verification_evidence_bound(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append_event({"event_type": "VERIFICATION_PASS", "goal_id": "g1", "task_id": "t1", "result_id": "r1", "verification_reference": "v1"})
    
    events = ledger.events_for_task("t1")
    assert events[0]["result_id"] == "r1"
    assert events[0]["verification_reference"] == "v1"

