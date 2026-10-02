import pytest
from scripts.automation_wake_coalescing import AutomationContext, AutoState, Wakeup

def test_automation_context_queue_awareness():
    ctx = AutomationContext()
    
    # Simulating a multi-turn batch where queue items remain
    # Wake 1 arrives
    ctx.enqueue_wake(Wakeup("wake-1"))
    
    # 2 more items are queued in advance
    ctx.enqueue_wake(Wakeup("wake-2"))
    ctx.enqueue_wake(Wakeup("wake-3"))
    
    assert ctx.start_execution() is True
    
    # After first execution turn completes, it should know rechecks are needed
    ctx.finish_execution()
    
    # Since there were more wakes, state should be PENDING, not IDLE
    assert ctx.state == AutoState.PENDING
    
    # Start next turn
    assert ctx.start_execution() is True
    ctx.finish_execution()
    
    # We don't have built-in exact queue exhaustion in AutomationContext (it just tracks recheck_needed).
    # But as long as it's not IDLE, it doesn't retire.
    
    # If we drain it fully
    ctx.enqueue_wake(Wakeup("wake-4"))
    ctx.start_execution()
    ctx.finish_execution()
    
    # Without another enqueue, finish_execution should put it to IDLE
    assert ctx.state == AutoState.IDLE

