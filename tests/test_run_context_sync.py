from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.run_context_sync as rcs
from scripts.run_context_sync import UpdateSteward, compute_sha256, get_git_head


def test_compute_sha256():
    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    assert compute_sha256(d1) == compute_sha256(d2)


def test_get_git_head_not_connected(tmp_path: Path):
    assert get_git_head(tmp_path / "nonexistent") == "NOT_CONNECTED"
    assert get_git_head(tmp_path) == "NOT_CONNECTED"


def test_get_git_head_standard_and_worktree(tmp_path: Path):
    # 1. Standard repo with HEAD pointing to ref
    repo1 = tmp_path / "repo1"
    git_dir = repo1 / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    heads_dir = git_dir / "refs" / "heads"
    heads_dir.mkdir(parents=True)
    (heads_dir / "main").write_text("1111222233334444555566667777888899990000\n", encoding="utf-8")

    assert get_git_head(repo1) == "1111222233334444555566667777888899990000"

    # 2. Worktree with .git file pointing to gitdir
    repo2 = tmp_path / "worktree"
    repo2.mkdir(parents=True)
    wt_gitdir = tmp_path / "actual_gitdir"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "HEAD").write_text("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", encoding="utf-8")

    (repo2 / ".git").write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")
    assert get_git_head(repo2) == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_update_steward_snapshot_lifecycle(tmp_path: Path):
    repo_dir = tmp_path / "courier"
    memory_dir = tmp_path / "memory"
    godot_dir = tmp_path / "godot"
    repo_dir.mkdir(parents=True)
    memory_dir.mkdir(parents=True)
    godot_dir.mkdir(parents=True)

    # Populate sample memory files
    (memory_dir / "PROJECT_STATE.md").write_text("- VERIFIED_CURRENT: Milestone 1\n", encoding="utf-8")
    (memory_dir / "DECISIONS.md").write_text("## D-001 First Architectural Choice\n", encoding="utf-8")
    (memory_dir / "IDEA_ARCHIVE.md").write_text("### IDEA-001 Next Generation Dispatcher\n", encoding="utf-8")

    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)

    # 1. Generate first snapshot
    snap1 = steward.generate_context_snapshot()
    assert snap1["context_version"] == 1
    assert "snapshot_hash" in snap1
    assert (repo_dir / "events" / "context-snapshots" / "snapshot-v1.json").exists()
    assert (repo_dir / "events" / "context-snapshots" / "snapshot-current.json").exists()
    assert snap1["memory_truth"]["latest_verified_milestone"] == "VERIFIED_CURRENT: Milestone 1"
    assert "D-001 First Architectural Choice" in snap1["memory_truth"]["latest_decisions"]

    # 2. Attach task context
    task = {"task_id": "test-task"}
    enriched = steward.attach_task_context(task, snapshot=snap1)
    assert enriched["context_version"] == 1
    assert enriched["context_snapshot_hash"] == snap1["snapshot_hash"]

    # 3. Check staleness (not stale)
    stale, reason = steward.check_task_staleness(enriched, current_snapshot=snap1)
    assert stale is False
    assert reason == "CONTEXT_CURRENT"

    # 4. Modify memory and regenerate snapshot
    (memory_dir / "DECISIONS.md").write_text("## D-001 First Choice\n## D-002 Second Choice\n", encoding="utf-8")
    snap2 = steward.generate_context_snapshot()
    assert snap2["context_version"] == 2
    assert "decisions" in snap2["changed_since_previous_snapshot"]

    # 5. Check staleness against older task
    stale, reason = steward.check_task_staleness(enriched, current_snapshot=snap2)
    assert stale is True
    assert "CONTEXT_REFRESH_REQUIRED" in reason


def test_main_cli(tmp_path: Path, capsys):
    repo_dir = tmp_path / "courier"
    repo_dir.mkdir(parents=True)
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)

    code = rcs.main(["--refresh", "--repo-dir", str(repo_dir), "--memory-dir", str(memory_dir), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["context_version"] == 1
