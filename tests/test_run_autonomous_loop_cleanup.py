import pytest
from scripts.run_autonomous_loop import AutonomousLevel6Loop
from scripts.host_guardian import HostState, AdmissionState

def test_autonomous_loop_crashes_yield_unproven_cleanup():
    loop = AutonomousLevel6Loop(max_iterations=1)
    
    # Mock to allow lease
    loop.host_guardian.evaluate_admission = lambda: AdmissionState.OPEN
    
    # Track what is passed to release_heavy_lease
    cleanup_calls = []
    
    def mock_release(cleanup_proven):
        cleanup_calls.append(cleanup_proven)
        
    loop.host_guardian.release_heavy_lease = mock_release
    
    # Force a crash in the middle of the loop (e.g., during subprocess or hook)
    # The loop calls self._build_context_package... let's just make `self.steward` raise an exception.
    class MockSteward:
        def refresh_snapshot_after_event(self, *args, **kwargs):
            raise RuntimeError("Unexpected OS crash during loop execution")
            
    loop.steward = MockSteward()
    
    plan = [{"task_id": "test_crash", "target_agent": "codex", "instruction": "do something"}]
    
    # Normally this would raise, but we want to ensure the finally block fires
    with pytest.raises(RuntimeError, match="Unexpected OS crash"):
        loop.run_multi_round_workflow("wf-crash", plan)
        
    assert len(cleanup_calls) == 1, "Should have released lease exactly once"
    assert cleanup_calls[0] is False, "A crashed physical execution MUST NOT claim cleanup is proven"

