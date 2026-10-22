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

def test_memory_file_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside-decisions.md"
    outside.write_text("## D-9 — SECRET-DECISION\nsecret body\n", encoding="utf-8")
    memory = tmp_path / "memory"
    memory.mkdir()
    (memory / "DECISIONS.md").symlink_to(outside)

    parent_outside = tmp_path / "memory-parent"
    parent_outside.mkdir()
    (parent_outside / "DECISIONS.md").write_text("## D-8 — SECRET-PARENT\nsecret body\n", encoding="utf-8")
    linked_parent = tmp_path / "linked-memory"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    plain = tmp_path / "plain-memory"
    plain.mkdir()
    (plain / "DECISIONS.md").write_text("## D-1 — Plain Decision\nbody\n", encoding="utf-8")

    def start(folder):
        try:
            curator = ThoughtCurator(repo_dir=tmp_path / "repo", memory_dir=folder)
        except ValueError as exc:
            return str(exc), None
        return "loaded", [item["title"] for item in curator.memory_index["decisions"]]

    err_file, titles_file = start(memory)
    err_parent, titles_parent = start(linked_parent)
    err_plain, titles_plain = start(plain)
    assert (
        err_file,
        titles_file,
        "SECRET-DECISION" in outside.read_text(encoding="utf-8"),
        err_parent,
        titles_parent,
        "SECRET-PARENT" in (parent_outside / "DECISIONS.md").read_text(encoding="utf-8"),
        err_plain,
        titles_plain,
    ) == (
        "refusing to follow a symlink",
        None,
        True,
        "refusing to follow a symlink",
        None,
        True,
        "loaded",
        ["Plain Decision"],
    )

def test_thoughts_dir_does_not_follow_a_symlink(memory_dir, tmp_path, monkeypatch):
    curator = ThoughtCurator(repo_dir=tmp_path, memory_dir=memory_dir)
    outside = tmp_path / "outside-thoughts"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-thoughts"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = tmp_path / "thoughts-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "thoughts-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(folder):
        monkeypatch.setattr("scripts.run_thought_curator.THOUGHTS_DIR", folder)
        try:
            curator.curate_idea("SECRET-IDEA about a checklist")
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "thoughts")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = tmp_path / "plain-thoughts"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    leaked_body = ""
    for name in leaked:
        if name.endswith(".json"):
            leaked_body = (outside / name).read_text(encoding="utf-8")
    assert (
        err_link,
        "SECRET-IDEA" in leaked_body,
        err_parent,
        parent_names,
        err_plain,
        any(name.endswith(".json") for name in plain_names),
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        ["keep.txt"],
        "wrote",
        True,
    )
