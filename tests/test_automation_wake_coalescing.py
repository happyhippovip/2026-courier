import pytest
from scripts.automation_wake_coalescing import AutoState, AutomationContext, Wakeup

def test_100_duplicate_wakeups_bounded_queue():
    ctx = AutomationContext()
    
    # 1. First wakeup transitions to PENDING
    ctx.enqueue_wake(Wakeup(trigger_id="t1"))
    assert ctx.state == AutoState.PENDING
    
    # 2. Start running
    assert ctx.start_execution() is True
    assert ctx.state == AutoState.RUNNING
    
    # 3. 100 identical wakeups arrive while running
    for _ in range(100):
        ctx.enqueue_wake(Wakeup(trigger_id="t1"))
        
    # Queue is bounded: only one boolean flag is flipped
    assert ctx.state == AutoState.RUNNING
    assert ctx.recheck_needed is True
    
    # 4. Finish execution -> transitions back to PENDING (bounded)
    ctx.finish_execution()
    assert ctx.state == AutoState.PENDING
    assert ctx.recheck_needed is False

def test_different_meaningful_instruction_while_running():
    ctx = AutomationContext()
    ctx.enqueue_wake(Wakeup(trigger_id="t1", instruction="base_work"))
    ctx.start_execution()
    
    # Human sends a meaningful override instruction
    ctx.enqueue_wake(Wakeup(trigger_id="t1", instruction="super_work"))
    assert ctx.recheck_needed is True
    assert ctx.pending_instruction == "super_work"
    
    ctx.finish_execution()
    assert ctx.state == AutoState.PENDING
    assert ctx.pending_instruction == "super_work"

def test_cancel_while_running_wins():
    ctx = AutomationContext()
    ctx.enqueue_wake(Wakeup(trigger_id="t1"))
    ctx.start_execution()
    
    ctx.enqueue_wake(Wakeup(trigger_id="t1", is_cancel=True))
    assert ctx.cancel_requested is True
    
    ctx.finish_execution()
    assert ctx.state == AutoState.IDLE
    assert ctx.recheck_needed is False

def test_restart_with_pending_recheck():
    # Simulate a crash and restart. The journal replays the events.
    # WAKEUP -> START -> WAKEUP(recheck) -> [CRASH]
    ctx = AutomationContext()
    # Replayed event 1
    ctx.enqueue_wake(Wakeup(trigger_id="t1"))
    ctx.start_execution()
    # Replayed event 2
    ctx.enqueue_wake(Wakeup(trigger_id="t1"))
    
    # At restart, we see RUNNING state with recheck_needed.
    # A crash means RUNNING was interrupted. Usually, the execution is dead.
    # A recovery mechanism would mark the crashed execution failed and we should handle the recheck.
    # Here, we can simulate recovery by "finishing" the broken execution.
    ctx.finish_execution()
    assert ctx.state == AutoState.PENDING

def test_resource_pause_semantics():
    ctx = AutomationContext()
    ctx.enqueue_wake(Wakeup(trigger_id="t1"))
    ctx.start_execution()
    
    # Hit EMFILE / spawn exhaustion
    ctx.resource_exhausted()
    assert ctx.state == AutoState.RESOURCE_PAUSE
    
    # While paused, another wakeup comes
    ctx.enqueue_wake(Wakeup(trigger_id="t1"))
    assert ctx.recheck_needed is True
    
    # Start execution recovers from pause
    assert ctx.start_execution() is True
    assert ctx.state == AutoState.RUNNING

def test_no_double_external_effect_for_duplicate_wakes():
    ctx = AutomationContext()
    # 5 wakeups before execution even starts
    for _ in range(5):
        ctx.enqueue_wake(Wakeup(trigger_id="t1"))
        
    assert ctx.state == AutoState.PENDING
    assert ctx.start_execution() is True
    assert ctx.state == AutoState.RUNNING
    
    # 0 pending rechecks since they all arrived before RUNNING
    assert ctx.recheck_needed is False
    
    ctx.finish_execution()
    assert ctx.state == AutoState.IDLE
