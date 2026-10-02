import pytest
import datetime
import os
import copy
from scripts.provider_circuit import ProviderState, ProviderCircuitBreaker
from scripts.automation_wake_coalescing import AutoState, Wakeup
from scripts.provider_survival import (
    CourierScheduler, TaskContext, WorkState, Provider
)

def test_1_provider_quota_exhausted():
    scheduler = CourierScheduler()
    scheduler.simulate_error = True
    scheduler.simulate_error_provider = "muse"
    scheduler.simulate_error_code = 429
    scheduler.simulate_error_message = "subscription quota exhausted"
    
    reset_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
    scheduler.simulate_reset_time = reset_time
    
    # We pass a task that only muse could handle (no fallbacks)
    scheduler.providers = [Provider("muse", True, ["completion"])]
    
    task = TaskContext("task-1")
    scheduler.handle_wake("wake-1", [task])
    
    # Circuit opens
    assert scheduler.breaker.is_open("muse", "completion") is True
    circuit = scheduler.breaker.get_circuit("muse", "completion")
    assert circuit.state == ProviderState.QUOTA_EXHAUSTED
    assert circuit.reset_time == reset_time
    assert "task-1" not in scheduler.completed_tasks

def test_2_100_duplicate_wakes_coalesce():
    scheduler = CourierScheduler()
    # Manually open the circuit
    scheduler.breaker.record_failure("muse", "completion", 429, "quota exhausted")
    scheduler.providers = [Provider("muse", True, ["completion"])]
    
    task = TaskContext("task-1")
    
    # Enqueue 100 wakes before execution
    for i in range(100):
        scheduler.automation_ctx.enqueue_wake(Wakeup(trigger_id=f"wake-{i}"))
        
    assert scheduler.automation_ctx.recheck_needed is False
    
    call_count = 0
    original_exec = scheduler.execute_with_provider
    def mock_exec(*args):
        nonlocal call_count
        call_count += 1
        return original_exec(*args)
    scheduler.execute_with_provider = mock_exec
    
    for i in range(100):
        scheduler.handle_wake(f"wake-x-{i}", [task])
        
    assert call_count == 0

def test_3_provider_unavailable_but_local_work_proceeds():
    scheduler = CourierScheduler()
    scheduler.breaker.record_failure("muse", "completion", 503, "Unavailable")
    scheduler.providers = [Provider("muse", True, ["completion"])]
    
    t_provider = TaskContext("t-prov", is_deterministic=False)
    t_local = TaskContext("t-loc", is_deterministic=True)
    
    scheduler.handle_wake("wake-1", [t_provider, t_local])
    
    assert "t-prov" not in scheduler.completed_tasks
    assert "t-loc" in scheduler.completed_tasks

def test_4_authorized_fallback_exists():
    scheduler = CourierScheduler()
    scheduler.breaker.record_failure("muse", "completion", 429, "quota")
    # Both authorized
    scheduler.providers = [
        Provider("muse", True, ["completion"]),
        Provider("gemini", True, ["completion"])
    ]
    
    t_provider = TaskContext("t-prov")
    scheduler.handle_wake("wake-1", [t_provider])
    
    # Handoff created, but task is NOT complete until fallback executes
    assert "t-prov" not in scheduler.completed_tasks
    assert any(h[1] == "t-prov" for h in scheduler.pending_handoffs)

def test_5_no_authorized_fallback_exists():
    scheduler = CourierScheduler()
    scheduler.breaker.record_failure("muse", "completion", 429, "quota")
    # Gemini NOT authorized
    scheduler.providers = [
        Provider("muse", True, ["completion"]),
        Provider("gemini", False, ["completion"])
    ]
    
    t_provider = TaskContext("t-prov")
    t_local = TaskContext("t-loc", is_deterministic=True)
    
    scheduler.handle_wake("wake-1", [t_provider, t_local])
    
    assert "t-prov" not in scheduler.completed_tasks
    assert "t-loc" in scheduler.completed_tasks

def test_6_human_desk_not_bypassed():
    scheduler = CourierScheduler()
    scheduler.breaker.record_failure("muse", "completion", 429, "quota")
    scheduler.providers = [
        Provider("muse", True, ["completion"]),
        Provider("gemini", True, ["completion"])
    ]
    
    t_human = TaskContext("t-hum", requires_human_gate=True)
    
    scheduler.handle_wake("wake-1", [t_human])
    
    # It evaluates to WAITING_AUTHORITY and does not fallback or complete
    assert "t-hum" not in scheduler.completed_tasks

def test_7_external_effect_uncertain_no_retry():
    scheduler = CourierScheduler()
    scheduler.breaker.record_failure("muse", "completion", 502, "Bad Gateway")
    scheduler.providers = [
        Provider("muse", True, ["completion"]),
        Provider("gemini", True, ["completion"])
    ]
    
    t_uncertain = TaskContext("t-eff", effect_uncertain=True)
    
    scheduler.handle_wake("wake-1", [t_uncertain])
    
    assert "t-eff" not in scheduler.completed_tasks

def test_8_restart_preserves_circuit():
    breaker = ProviderCircuitBreaker()
    breaker.record_failure("muse", "completion", 429, "quota")
    
    # Restart
    breaker2 = copy.deepcopy(breaker)
    assert breaker2.is_open("muse", "completion") is True
    assert breaker2.get_circuit("muse", "completion").state == ProviderState.QUOTA_EXHAUSTED

def test_9_provider_reset_time_arrives_recovery_probe():
    scheduler = CourierScheduler()
    scheduler.providers = [Provider("muse", True, ["completion"])]
    
    # Time in the past
    reset = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    scheduler.breaker.record_failure("muse", "completion", 429, "quota", reset_time=reset)
    
    circuit = scheduler.breaker.get_circuit("muse", "completion")
    
    # First check opens it for probe
    assert scheduler.breaker.is_open("muse", "completion") is False
    assert circuit.state == ProviderState.RECOVERY_PROBE_DUE
    
    # Second check still allows probe, keeps it RECOVERY_PROBE_DUE until success or failure is recorded
    assert scheduler.breaker.is_open("muse", "completion") is False

def test_10_provider_recovers_exactly_one_continuation():
    scheduler = CourierScheduler()
    scheduler.providers = [Provider("muse", True, ["completion"])]
    
    reset = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    scheduler.breaker.record_failure("muse", "completion", 429, "quota", reset_time=reset)
    
    t_prov = TaskContext("t-prov")
    
    # Simulate success
    scheduler.handle_wake("wake-1", [t_prov])
    
    # Probe re-arms the circuit but task is NOT complete
    assert "t-prov" not in scheduler.completed_tasks
    assert scheduler.breaker.get_circuit("muse", "completion").state == ProviderState.AVAILABLE
    
    # Second wake: now circuit is AVAILABLE, task actually executes
    scheduler.handle_wake("wake-2", [t_prov])
    assert scheduler.completed_tasks.count("t-prov") == 1

def test_11_emfile_resource_pause():
    scheduler = CourierScheduler()
    
    def fail_local(task):
        raise OSError(24, "Too many open files")
        
    scheduler.execute_local = fail_local
    
    t_local = TaskContext("t-loc", is_deterministic=True)
    
    scheduler.handle_wake("wake-1", [t_local])
    
    # It should catch EMFILE and transition to RESOURCE_PAUSE
    assert scheduler.automation_ctx.state == AutoState.RESOURCE_PAUSE

