from courier_core.replay_protection import ReplayProtectionGuard
from courier_core.automation_scheduler import DurableScheduler

def test_replay_protection():
    guard = ReplayProtectionGuard()
    # First execution is safe
    assert guard.check_and_record("send_payment", "amount=100") is True
    # Replay is rejected
    assert guard.check_and_record("send_payment", "amount=100") is False
    # Different payload is safe
    assert guard.check_and_record("send_payment", "amount=200") is True

def test_automation_scheduler():
    scheduler = DurableScheduler()
    scheduler.schedule("t1", 10.0, "do_work", "data")
    
    # Not due yet
    assert len(scheduler.get_due_tasks(current_time=time.time())) == 0
    
    # Fast forward time
    due = scheduler.get_due_tasks(current_time=time.time() + 15.0)
    assert len(due) == 1
    assert due[0].task_id == "t1"
    
    # Task removed after retrieval
    assert len(scheduler.get_due_tasks(current_time=time.time() + 15.0)) == 0

import time
