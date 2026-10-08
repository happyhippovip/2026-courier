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
    
    # It should fallback to gemini and complete
    assert "t-prov" in scheduler.completed_tasks

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
    
    # completed_tasks only has 1
    assert scheduler.completed_tasks.count("t-prov") == 1
    assert scheduler.breaker.get_circuit("muse", "completion").state == ProviderState.AVAILABLE

def test_11_emfile_resource_pause():
    scheduler = CourierScheduler()
    
    def fail_local(task):
        raise OSError(24, "Too many open files")
        
    scheduler.execute_local = fail_local
    
    t_local = TaskContext("t-loc", is_deterministic=True)
    
    scheduler.handle_wake("wake-1", [t_local])
    
    # It should catch EMFILE and transition to RESOURCE_PAUSE
    assert scheduler.automation_ctx.state == AutoState.RESOURCE_PAUSE

def test_12_multi_capability_hibernation_refused_when_one_circuit_available():
    from scripts.provider_hibernation import ContinuationCheckpoint, LaneHibernator, LaneState
    scheduler = CourierScheduler()
    # Muse handles both completion and embedding, no fallbacks
    scheduler.providers = [Provider("muse", True, ["completion", "embedding"])]

    # Open completion circuit only
    scheduler.breaker.record_failure("muse", "completion", 429, "completion quota exhausted")
    assert scheduler.breaker.is_open("muse", "completion") is True
    assert scheduler.breaker.is_open("muse", "embedding") is False

    lane = LaneHibernator()
    checkpoint = ContinuationCheckpoint(task_id="t-1", workkey="W1", mutable_scope="S1")

    t_completion = TaskContext("t-completion", required_capability="completion")
    t_embedding = TaskContext("t-embedding", required_capability="embedding")

    # Order 1: completion first, embedding second.
    # Because embedding is still available on primary, the lane is NOT quota-blocked/idle!
    result = scheduler.hibernate_if_quota_blocked_idle(
        lane, checkpoint, [], [t_completion, t_embedding]
    )
    assert result is None
    assert lane.state == LaneState.ACTIVE

    # Order 2: embedding first, completion second.
    result2 = scheduler.hibernate_if_quota_blocked_idle(
        lane, checkpoint, [], [t_embedding, t_completion]
    )
    assert result2 is None
    assert lane.state == LaneState.ACTIVE

    # Now open embedding circuit as well: ALL provider circuits are OPEN
    scheduler.breaker.record_failure("muse", "embedding", 429, "embedding quota exhausted")
    assert scheduler.breaker.is_open("muse", "embedding") is True

    result3 = scheduler.hibernate_if_quota_blocked_idle(
        lane, checkpoint, [], [t_completion, t_embedding]
    )
    assert result3 is not None
    assert lane.state == LaneState.HIBERNATED

def test_13_customer_state_edge_cases():
    scheduler = CourierScheduler()
    # Empty task list returns DONE
    assert scheduler.customer_state([]) == "DONE"

    # Completed tasks return DONE
    scheduler.completed_tasks = ["task-1"]
    assert scheduler.customer_state([TaskContext("task-1")]) == "DONE"

    # Pending task returns WORKING
    assert scheduler.customer_state([TaskContext("task-2")]) == "WORKING"

    # Needs connection flag returns NEEDS YOU
    assert scheduler.customer_state([TaskContext("task-2")], needs_connection=True) == "NEEDS YOU"

    # Human gated task returns NEEDS YOU
    assert scheduler.customer_state([TaskContext("task-3", requires_human_gate=True)]) == "NEEDS YOU"

    # Dict-based tasks do not crash customer_state
    dict_task = {"task_id": "task-4", "requires_human_gate": True}
    assert scheduler.customer_state([dict_task]) == "NEEDS YOU"

def test_14_load_checkpoint_validation_and_workkey_mismatch(tmp_path):
    from scripts.provider_hibernation import ContinuationCheckpoint, LaneHibernator
    state_file = tmp_path / "state.json"
    scheduler = CourierScheduler(primary_provider="muse", state_path=state_file)

    # Empty file or missing workkey raises ValueError
    cp_invalid = ContinuationCheckpoint(task_id="t-1", workkey="")
    with pytest.raises(ValueError, match="durable workkey/checkpoint is required"):
        scheduler._load(checkpoint=cp_invalid)

    # Valid checkpoint initializes properly
    cp_valid = ContinuationCheckpoint(task_id="t-1", workkey="W-1", mutable_scope="S-1")
    scheduler._load(checkpoint=cp_valid)
    assert scheduler.lane.checkpoint.workkey == "W-1"
    scheduler._save()

    # Mismatched workkey raises ValueError
    cp_different = ContinuationCheckpoint(task_id="t-1", workkey="W-2", mutable_scope="S-1")
    with pytest.raises(ValueError, match="checkpoint belongs to another workkey"):
        scheduler._load(checkpoint=cp_different)


