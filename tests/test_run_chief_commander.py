import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

def test_formulate_workflow_plan(tmp_path, monkeypatch):
    import scripts.run_chief_commander as script
    
    chief = script.ChiefCommander()
    
    # Mock Steward
    class MockSteward:
        def get_latest_snapshot(self):
            return {"context_version": 1, "snapshot_hash": "hash"}
        def generate_context_snapshot(self, context_delta=None):
            return {"context_version": 1, "snapshot_hash": "hash"}
        def attach_task_context(self, task, snap):
            task["attached"] = True
    
    chief.steward = MockSteward()
    
    # We don't want to actually hit the filesystem in SmartResourceRouter, but it just parses strings
    workflow_id, plan = chief.formulate_workflow_plan(
        idea_text="Refactor test logic",
        idea_type="IDEA",
        context_delta={"some": "delta"},
        correlation_id="c-123"
    )
    
    assert workflow_id.startswith("WF-CHIEF-")
    assert len(plan) == 3
    assert plan[0]["target_agent"] in ["codex", "antigravity"]
    assert plan[0]["attached"] is True

def test_execute_human_idea_blocked(tmp_path, monkeypatch):
    import scripts.run_chief_commander as script
    
    chief = script.ChiefCommander()
    
    class MockCurator:
        def curate_idea(self, text, type):
            return {
                "classification": "CONFLICT",
                "conflicts": [{"rule": "No breaking changes"}],
                "idea_id": "idea-1"
            }
    
    chief.curator = MockCurator()
    
    class MockStateTracker:
        def update_state(self, *args, **kwargs):
            pass
            
    chief.chief_state_tracker = MockStateTracker()
    
    res = chief.execute_human_idea("Break things", dry_run=True)
    
    assert res["status"] == "BLOCKED_POLICY_CONFLICT"
    assert len(res["workflow_plan"]) == 0

