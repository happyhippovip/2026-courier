import json
import pytest
from pathlib import Path
from scripts.run_thought_curator import ThoughtCurator, main


@pytest.fixture
def curator_env(tmp_path):
    repo_dir = tmp_path / "repo"
    memory_dir = tmp_path / "memory"
    repo_dir.mkdir(parents=True)
    memory_dir.mkdir(parents=True)

    # Populate canonical memory files
    (memory_dir / "DECISIONS.md").write_text(
        "## D-002 — Crypto and speculative recovery blocked\nCrypto speculation is strictly prohibited.\n\n"
        "## D-004 — No paid or irreversible action by default\nPaid actions require human approval.\n\n"
        "## D-022 — Scoped permissions and safe cleanup\nDestructive cleanup commands are blocked.\n",
        encoding="utf-8"
    )
    (memory_dir / "IDEA_ARCHIVE.md").write_text(
        "- **Automated Video Cache:** Pre-render static background assets for 3D videos.\n"
        "- **Continuous Benchmarks:** Run daily local benchmarks for pipeline performance.\n",
        encoding="utf-8"
    )
    (memory_dir / "PROJECT_STATE.md").write_text(
        "# Project State\n"
        "- **VERIFIED Milestone:** Zero-chat handoff verified.\n",
        encoding="utf-8"
    )
    return repo_dir, memory_dir


def test_thought_curator_initialization(curator_env):
    repo_dir, memory_dir = curator_env
    curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)

    assert curator.thoughts_dir.exists()
    assert curator.states_dir.exists()
    assert curator.sources_available["decisions"] is True
    assert curator.sources_available["ideas"] is True
    assert curator.sources_available["project_state"] is True
    assert len(curator.memory_index["decisions"]) == 3


def test_thought_curator_crypto_policy_conflict(curator_env):
    repo_dir, memory_dir = curator_env
    curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)

    delta = curator.curate_idea("Launch new crypto memecoin trading strategy", idea_type="STRATEGY")

    assert delta["classification"] == "CONFLICT"
    assert delta["recommended_next_action"] == "STOP_ON_POLICY_CONFLICT"
    assert delta["target_agent_recommendation"] == "chief_gate"
    assert any("D-002" in c["rule"] for c in delta["conflicts"])

    # State file check
    state_file = curator.states_dir / "agent-thought-curator.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["state"] == "BLOCKED"
    assert state["blocked"] is True
    assert state["human_gate"] == "REQUIRE_EXPLICIT_HUMAN_APPROVAL"

    # Thought record file exists in instance thoughts_dir
    thought_file = curator.thoughts_dir / f"{delta['idea_id']}.json"
    assert thought_file.exists()


def test_thought_curator_destructive_command_conflict(curator_env):
    repo_dir, memory_dir = curator_env
    curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)

    delta = curator.curate_idea("Run rm -rf on old logs to clean up disk space", idea_type="IDEA")
    assert delta["classification"] == "CONFLICT"
    assert any("D-022" in c["rule"] for c in delta["conflicts"])


def test_thought_curator_qa_routing(curator_env):
    repo_dir, memory_dir = curator_env
    curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)

    delta = curator.curate_idea("Add strict syntax audit and unit test validation for queue payloads", idea_type="TASK")
    assert delta["classification"] != "CONFLICT"
    assert delta["recommended_next_action"] == "ROUTE_TO_CODEX_QA"
    assert delta["target_agent_recommendation"] == "codex"
    assert "codex" in delta["affected_agents"]


def test_thought_curator_3d_media_routing(curator_env):
    repo_dir, memory_dir = curator_env
    curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)

    delta = curator.curate_idea("Create new 3D Godot movie render for strawberry animation", idea_type="IDEA")
    assert delta["classification"] != "CONFLICT"
    assert "antigravity" in delta["affected_agents"]
    assert any("3D Shorts Pipeline" in wf for wf in delta["affected_workflows"])


def test_thought_curator_related_ideas(curator_env):
    repo_dir, memory_dir = curator_env
    curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)

    # In IDEA_ARCHIVE we have "Pre-render static background assets for 3D videos"
    delta = curator.curate_idea("Pre-render background assets for videos", idea_type="IDEA")
    assert len(delta["memory_references"]) >= 1
    assert any(ref.get("type") in ("ARCHIVED_IDEA", "PROJECT_STATE") for ref in delta["memory_references"])


def test_thought_curator_cli(curator_env, capsys):
    repo_dir, memory_dir = curator_env

    code = main([
        "--idea", "Improve deterministic benchmark performance",
        "--type", "IDEA",
        "--repo-dir", str(repo_dir),
        "--memory-dir", str(memory_dir),
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "idea_id" in data
    assert data["classification"] in ("NEW", "RELATED")
    assert data["idea_status"] == "PROPOSED"
