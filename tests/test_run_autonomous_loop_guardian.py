import pytest
from scripts.run_autonomous_loop import AutonomousLevel6Loop
from scripts.host_guardian import HostState, AdmissionState

def test_autonomous_loop_respects_guardian_admission():
    loop = AutonomousLevel6Loop(max_iterations=1)
    
    # Force admission CLOSED
    loop.host_guardian.evaluate_admission = lambda: AdmissionState.CLOSED
    
    plan = [{"task_id": "test", "target_agent": "codex", "instruction": "do something"}]
    
    result = loop.run_multi_round_workflow("wf-test-1", plan)
    
    assert result["status"] == "RESOURCE_PAUSE"
    assert "Host admission is CLOSED" in result["stop_reason"]

def test_autonomous_loop_requests_heavy_lease():
    loop = AutonomousLevel6Loop(max_iterations=1)
    
    loop.host_guardian.evaluate_admission = lambda: AdmissionState.OPEN
    loop.host_guardian.request_heavy_lease = lambda: False
    
    plan = [{"task_id": "test", "target_agent": "codex", "instruction": "do something"}]
    
    result = loop.run_multi_round_workflow("wf-test-2", plan)
    
    assert result["status"] == "RESOURCE_PAUSE"
    assert "MAX_HEAVY_LOCAL_JOBS" in result["stop_reason"]

