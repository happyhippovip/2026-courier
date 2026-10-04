import os
import json
import pytest
from pathlib import Path
from scripts.run_thought_curator import ThoughtCurator


@pytest.fixture
def memory_dir(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    
    decisions = mem_dir / "DECISIONS.md"
    decisions.write_text(
        "## D-001 — First Decision\nBody of first.\n"
        "## D-002 — Crypto\nBlocked.\n",
        encoding="utf-8"
    )
    
    ideas = mem_dir / "IDEA_ARCHIVE.md"
    ideas.write_text(
        "- **IDEA-1:** Some old idea about rendering fruitki\n"
        "- **IDEA-2:** Another thought",
        encoding="utf-8"
    )
    
    state = mem_dir / "PROJECT_STATE.md"
    state.write_text(
        "## Core Principles\n"
        "- **P-1:** VERIFIED the system works\n"
        "Normal text is ignored.",
        encoding="utf-8"
    )
    
    return mem_dir

def test_thought_curator_indexing(memory_dir, tmp_path):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    assert curator.sources_available["decisions"] is True
    assert curator.sources_available["ideas"] is True
    assert curator.sources_available["project_state"] is True
    
    assert len(curator.memory_index["decisions"]) == 2
    assert curator.memory_index["decisions"][0]["id"] == "D-001"
    assert curator.memory_index["decisions"][0]["title"] == "First Decision"
    
    assert len(curator.memory_index["ideas"]) == 2
    assert len(curator.memory_index["project_state"]) == 2

def test_curate_idea_crypto_conflict(memory_dir, tmp_path):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    res = curator.curate_idea("Let's add a memecoin trading bot")
    assert res["classification"] == "CONFLICT"
    assert any(c["rule"].startswith("D-002") for c in res["conflicts"])
    assert res["recommended_next_action"] == "STOP_ON_POLICY_CONFLICT"
    assert res["target_agent_recommendation"] == "chief_gate"

def test_curate_idea_paid_conflict(memory_dir, tmp_path):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    res = curator.curate_idea("Please pay for a new subscription")
    assert res["classification"] == "CONFLICT"
    assert any(c["rule"].startswith("D-004") for c in res["conflicts"])

def test_curate_idea_cleanup_conflict(memory_dir, tmp_path):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    res = curator.curate_idea("Delete all files with rm -rf")
    assert res["classification"] == "CONFLICT"
    assert any(c["rule"].startswith("D-022") for c in res["conflicts"])

def test_curate_idea_related_idea(memory_dir, tmp_path):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    res = curator.curate_idea("rendering fruitki idea")
    assert res["classification"] == "RELATED"
    assert len(res["related_ideas"]) > 0
    assert "antigravity" in res["target_agent_recommendation"]

def test_curate_idea_qa_routing(memory_dir, tmp_path):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    res = curator.curate_idea("Please write a unit test and run lint")
    assert res["classification"] == "NEW"
    assert res["target_agent_recommendation"] == "codex"
    assert "codex" in res["affected_agents"]
