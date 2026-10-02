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


def test_autonomous_loop_stabilization_trigger():
    loop = AutonomousLevel6Loop(max_iterations=1)
    
    stabilize_called = False
    def mock_stabilize(resources):
        nonlocal stabilize_called
        stabilize_called = True
        return HostState.RESTART_RECOMMENDED
        
    loop.host_guardian.stabilize = mock_stabilize
    loop.host_guardian.evaluate_admission = lambda: AdmissionState.CLOSED
    loop.host_guardian.state = HostState.RESTART_RECOMMENDED
    
    plan = [{"task_id": "test", "target_agent": "codex", "instruction": "do something"}]
    result = loop.run_multi_round_workflow("wf-test-3", plan)
    
    assert stabilize_called is True
    assert result["status"] == "RESOURCE_PAUSE"
    assert "RESTART_RECOMMENDED" in result["stop_reason"]

def test_autonomous_loop_cleanup_unknown_honest_reporting():
    loop = AutonomousLevel6Loop(max_iterations=1)
    
    loop.host_guardian.evaluate_admission = lambda: AdmissionState.LIGHT_ONLY
    loop.host_guardian.request_heavy_lease = lambda: False
    loop.host_guardian.cleanup_unknown = True
    
    def mock_stabilize(resources):
        return HostState.LIGHT_ONLY
    loop.host_guardian.stabilize = mock_stabilize
    
    plan = [{"task_id": "test", "target_agent": "codex", "instruction": "do something heavy"}]
    result = loop.run_multi_round_workflow("wf-test-4", plan)
    
    assert result["status"] == "RESOURCE_PAUSE"
    assert "UNCLEAN previous shutdown" in result["stop_reason"]
    assert "cleanup UNKNOWN" in result["stop_reason"]

