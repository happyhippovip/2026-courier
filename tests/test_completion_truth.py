import pytest
from scripts.provider_survival import CourierScheduler, TaskContext, WorkState

def test_local_task_requires_accepted_result():
    sched = CourierScheduler()
    task = TaskContext("t-local", is_deterministic=True)
    sched.handle_wake("wake-1", [task])
    # Task should not be complete just because it's local. 
    # It must have evidence of execution.
    assert "t-local" not in sched.completed_tasks

def test_provider_task_requires_accepted_result():
    sched = CourierScheduler()
    task = TaskContext("t-prov")
    sched.handle_wake("wake-1", [task])
    # Calling the provider doesn't magically complete the task.
    # We must explicitly accept a result.
    assert "t-prov" not in sched.completed_tasks
