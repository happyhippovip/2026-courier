import pytest
from pathlib import Path

def test_run_live_demo(tmp_path, monkeypatch):
    import scripts.run_demo_workflow as script
    
    # Mocking a lot of dependencies since this is an integration script
    class MockCurator:
        def curate_idea(self, text, type):
            return {
                "idea_id": "idea-1",
                "classification": "NEW",
                "sources_indexed": {"memory": True}
            }
            
    class MockChief:
        def formulate_workflow_plan(self, idea_text, idea_type, context_delta, correlation_id):
            return "wf-1", [{"target_agent": "antigravity", "task_id": "t-1", "routing_reason": "test"}, {"target_agent": "codex", "task_id": "t-2", "routing_reason": "test"}]
            
    class MockLoop:
        def run_multi_round_workflow(self, workflow_id, workflow_plan, correlation_id):
            return {"status": "BLOCKED_HUMAN_GATE", "stop_reason": "HUMAN_APPROVAL_REQUIRED", "history": [{"round": 1}]}
            
        def resume_workflow(self, workflow_id, correlation_id, workflow_plan, from_round_index):
            return {"status": "COMPLETED", "stop_reason": "ALL_STEPS_ACCEPTED", "history": [{"round": 2}]}
            
    monkeypatch.setattr(script.ThoughtCurator, "__new__", lambda cls, *args, **kwargs: MockCurator())
    monkeypatch.setattr(script.ChiefCommander, "__new__", lambda cls, *args, **kwargs: MockChief())
    monkeypatch.setattr(script.AutonomousLevel6Loop, "__new__", lambda cls, *args, **kwargs: MockLoop())
    
    orchestrator = script.DemoOrchestrator(repo_dir=tmp_path)
    manifest = orchestrator.run_live_demo("Test Idea", "GOAL")
    
    assert manifest["status"] == "COMPLETED"
    assert manifest["human_input"]["raw_idea"] == "Test Idea"
    assert (orchestrator.evidence_dir / "demo_evidence_manifest.json").exists()

