import pytest
import os
import json
from pathlib import Path
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.run_context_sync import (
    UpdateSteward,
    get_git_head,
    compute_sha256
)

@pytest.fixture
def repo_env(tmp_path):
    repo_dir = tmp_path / "repo"
    memory_dir = tmp_path / "memory"
    godot_dir = tmp_path / "godot"
    
    repo_dir.mkdir()
    memory_dir.mkdir()
    godot_dir.mkdir()
    
    # Fake courier state dirs
    (repo_dir / "events" / "locks").mkdir(parents=True)
    (repo_dir / "events" / "chief-decisions").mkdir(parents=True)
    (repo_dir / "events" / "processed").mkdir(parents=True)
    (repo_dir / "events" / "approvals").mkdir(parents=True)
    (repo_dir / "events" / "agent-states").mkdir(parents=True)
    (repo_dir / "events" / "context-snapshots").mkdir(parents=True)
    
    return repo_dir, memory_dir, godot_dir

def test_get_git_head_not_connected(tmp_path):
    assert get_git_head(tmp_path) == "NOT_CONNECTED"

def test_get_git_head_valid(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main\n")
    
    (git_dir / "refs" / "heads").mkdir(parents=True)
    main_ref = git_dir / "refs" / "heads" / "main"
    main_ref.write_text("abcdef1234567890abcdef1234567890abcdef12\n")
    
    assert get_git_head(tmp_path) == "abcdef1234567890abcdef1234567890abcdef12"

def test_read_project_memory_truth(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    
    state_file = memory_dir / "PROJECT_STATE.md"
    state_file.write_text("- VERIFIED_CURRENT: Milestone 5\n")
    
    dec_file = memory_dir / "DECISIONS.md"
    dec_file.write_text("## D-001 Add new thing\nSome text\n## D-002 Remove old thing\n")
    
    idea_file = memory_dir / "IDEA_ARCHIVE.md"
    idea_file.write_text("### IDEA-001 Flying cars\n")
    
    truth = steward.read_project_memory_truth()
    
    assert truth["files_available"]["project_state"] is True
    assert truth["files_available"]["decisions"] is True
    assert truth["latest_verified_milestone"] == "VERIFIED_CURRENT: Milestone 5"
    assert truth["latest_decisions"] == ["D-001 Add new thing", "D-002 Remove old thing"]
    assert truth["relevant_ideas"] == ["IDEA-001 Flying cars"]

def test_read_courier_state(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    
    lock_file = repo_dir / "events" / "locks" / "wf-123.lock"
    lock_file.write_text(json.dumps({"correlation_id": "corr-1", "current_task_id": "task-1"}))
    
    state = steward.read_courier_state()
    assert state["workflow_id"] == "wf-123"
    assert state["correlation_id"] == "corr-1"
    assert state["current_task_id"] == "task-1"
    assert state["is_locked"] is True

def test_generate_context_snapshot_and_read(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    
    snap1 = steward.generate_context_snapshot()
    assert snap1["context_version"] == 1
    assert snap1["repositories"]["courier_head"] == "NOT_CONNECTED"
    assert "initial_snapshot" in snap1["changed_since_previous_snapshot"]
    
    # Generating again without changes should return same snapshot version
    snap2 = steward.generate_context_snapshot()
    assert snap2["context_version"] == 1
    
    # Introduce a change
    state_file = memory_dir / "PROJECT_STATE.md"
    state_file.write_text("- VERIFIED_CURRENT: Something new\n")
    
    dec_file = memory_dir / "DECISIONS.md"
    dec_file.write_text("## D-001 Add new thing\n")
    
    snap3 = steward.generate_context_snapshot()
    assert snap3["context_version"] == 2
    assert "decisions" in snap3["changed_since_previous_snapshot"]
    
    # Ensure current snapshot is readable
    current = steward.get_latest_snapshot()
    assert current["context_version"] == 2

def test_attach_and_check_task_staleness(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    
    task_data = {"id": "t1"}
    task_data = steward.attach_task_context(task_data)
    
    # Initially not stale
    stale, reason = steward.check_task_staleness(task_data)
    assert not stale
    
    # Change memory truth to bump version
    dec_file = memory_dir / "DECISIONS.md"
    dec_file.write_text("## D-001 New Decision\n")
    steward.generate_context_snapshot()
    
    # Now it should be stale
    stale2, reason2 = steward.check_task_staleness(task_data)
    assert stale2
    assert "CONTEXT_REFRESH_REQUIRED" in reason2

def test_get_git_head_packed_refs(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main\n")
    packed_refs = git_dir / "packed-refs"
    packed_refs.write_text("abcdef1234567890abcdef1234567890abcdef12 refs/heads/main\n")
    assert get_git_head(tmp_path) == "abcdef1234567890abcdef1234567890abcdef12"

def test_get_git_head_direct_sha(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("abcdef1234567890abcdef1234567890abcdef12")
    assert get_git_head(tmp_path) == "abcdef1234567890abcdef1234567890abcdef12"

def test_get_git_head_subprocess(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("broken")
    
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "sub-sha\n"
        assert get_git_head(tmp_path) == "sub-sha"

def test_get_git_head_subprocess_fail(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("broken")
    
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        assert get_git_head(tmp_path) == "UNKNOWN"

def test_read_courier_state_agent_states(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    
    state_file = repo_dir / "events" / "agent-states" / "some-agent.json"
    state_file.write_text(json.dumps({"id": "A1"}))
    state = steward.read_courier_state()
    assert len(state["agent_states"]) == 1
    
    # invalid state file
    bad_state = repo_dir / "events" / "agent-states" / "bad.json"
    bad_state.write_text("invalid json")
    steward.read_courier_state() # should ignore exception
    
    # processed dir count
    proc_file = repo_dir / "events" / "academy" / "adoptions" / "123.json"
    proc_file.parent.mkdir(parents=True, exist_ok=True)
    proc_file.write_text("{}")
    state = steward.read_courier_state()
    assert state["total_adoptions"] == 1

def test_check_task_staleness_no_version():
    steward = UpdateSteward()
    stale, reason = steward.check_task_staleness({})
    assert stale
    assert "missing context version" in reason

def test_refresh_snapshot_after_event(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    res = steward.refresh_snapshot_after_event("SOME_EVENT", "123")
    assert res["context_version"] == 1

def test_main_cli_refresh(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    from scripts.run_context_sync import main
    with mock.patch("sys.argv", ["run_context_sync.py", "--refresh"]):
        with mock.patch("scripts.run_context_sync.UpdateSteward", autospec=True) as mock_steward:
            mock_instance = mock_steward.return_value
            mock_instance.generate_context_snapshot.return_value = {
                "context_version": 1,
                "snapshot_hash": "hash123",
                "repositories": {"courier_head": "123", "memory_head": "123", "godot_head": "123"},
                "memory_truth": {"latest_decisions": []}
            }
            assert main() == 0
            mock_instance.generate_context_snapshot.assert_called_once()

def test_main_cli_inspect_exists(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    from scripts.run_context_sync import main
    with mock.patch("sys.argv", ["run_context_sync.py", "--inspect"]):
        with mock.patch("scripts.run_context_sync.UpdateSteward", autospec=True) as mock_steward:
            mock_instance = mock_steward.return_value
            mock_instance.get_latest_snapshot.return_value = {"context_version": 1}
            assert main() == 0
            mock_instance.get_latest_snapshot.assert_called_once()

def test_main_cli_inspect_missing(repo_env):
    from scripts.run_context_sync import main
    with mock.patch("sys.argv", ["run_context_sync.py", "--inspect"]):
        with mock.patch("scripts.run_context_sync.UpdateSteward", autospec=True) as mock_steward:
            mock_instance = mock_steward.return_value
            mock_instance.get_latest_snapshot.return_value = None
            assert main() == 0
            mock_instance.get_latest_snapshot.assert_called_once()

def test_write_snapshot_atomically_error(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    with mock.patch("os.replace", side_effect=PermissionError("boom")):
        with pytest.raises(PermissionError):
            steward._write_snapshot_atomically({"test": 1}, 1)

def test_read_project_memory_truth_empty_files(repo_env):
    repo_dir, memory_dir, godot_dir = repo_env
    steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir, godot_dir=godot_dir)
    
    # Write empty files or non-matching formats
    state_file = memory_dir / "PROJECT_STATE.md"
    state_file.write_text("random stuff\n")
    
    truth = steward.read_project_memory_truth()
    assert truth["latest_verified_milestone"] == "NOT_RECORDED"
