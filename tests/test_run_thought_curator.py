import pytest
import json
from pathlib import Path

def test_curate_idea_crypto_conflict(tmp_path, monkeypatch):
    import scripts.run_thought_curator as script
    
    # Mock dirs
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    monkeypatch.setattr(script, "PROJECT_MEMORY_DIR", memory_dir)
    
    thoughts_dir = tmp_path / "thoughts"
    thoughts_dir.mkdir()
    monkeypatch.setattr(script, "THOUGHTS_DIR", thoughts_dir)
    
    class MockTracker:
        def __init__(self, *args, **kwargs):
            pass
        def update_state(self, *args, **kwargs):
            pass
            
    monkeypatch.setattr(script, "AntigravityVisualStateTracker", MockTracker)
    
    curator = script.ThoughtCurator()
    
    # Should trigger D-002
    res = curator.curate_idea("We should buy crypto memecoins", "IDEA")
    
    assert res["classification"] == "CONFLICT"
    assert len(res["conflicts"]) == 1
    assert "D-002" in res["conflicts"][0]["rule"]
    assert res["recommended_next_action"] == "STOP_ON_POLICY_CONFLICT"
    assert res["target_agent_recommendation"] == "chief_gate"

def test_curate_idea_clean_qa(tmp_path, monkeypatch):
    import scripts.run_thought_curator as script
    
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    monkeypatch.setattr(script, "PROJECT_MEMORY_DIR", memory_dir)
    
    thoughts_dir = tmp_path / "thoughts"
    thoughts_dir.mkdir()
    monkeypatch.setattr(script, "THOUGHTS_DIR", thoughts_dir)
    
    class MockTracker:
        def __init__(self, *args, **kwargs):
            pass
        def update_state(self, *args, **kwargs):
            pass
            
    monkeypatch.setattr(script, "AntigravityVisualStateTracker", MockTracker)
    
    curator = script.ThoughtCurator()
    
    res = curator.curate_idea("Write a unit test and audit the code", "IDEA")
    
    assert res["classification"] == "NEW"
    assert len(res["conflicts"]) == 0
    assert res["recommended_next_action"] == "ROUTE_TO_CODEX_QA"
    assert res["target_agent_recommendation"] == "codex"
    assert "codex" in res["affected_agents"]

