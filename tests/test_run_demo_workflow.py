import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.run_demo_workflow import DemoOrchestrator, save_json, load_json, main

@pytest.fixture
def repo_dir(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "events").mkdir()
    (repo / "events/dispatch").mkdir()
    (repo / "events/processed").mkdir()
    (repo / "events/chief-decisions").mkdir()
    (repo / "events/approvals").mkdir()
    return repo

def test_reset_demo_environment(repo_dir):
    evidence_dir = repo_dir / "events/demo"
    orchestrator = DemoOrchestrator(repo_dir=repo_dir, evidence_dir=evidence_dir)
    
    # Create some dummy files to simulate previous run
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "old_file.txt").write_text("old")
    
    orchestrator.reset_demo_environment()
    
    assert evidence_dir.exists()
    assert not (evidence_dir / "old_file.txt").exists()
    assert (evidence_dir / "approvals").exists()
    assert (evidence_dir / "tasks").exists()
    assert (evidence_dir / "results").exists()
    assert (evidence_dir / "decisions").exists()

@patch("scripts.run_demo_workflow.AutonomousLevel6Loop")
@patch("scripts.run_demo_workflow.ChiefCommander")
@patch("scripts.run_demo_workflow.ThoughtCurator")
def test_run_live_demo(mock_curator_cls, mock_chief_cls, mock_loop_cls, repo_dir):
    # Setup mocks
    mock_curator = mock_curator_cls.return_value
    mock_curator.curate_idea.return_value = {
        "idea_id": "idea-123",
        "classification": "NEW",
        "sources_indexed": {"a": "b"}
    }
    
    mock_chief = mock_chief_cls.return_value
    mock_chief.formulate_workflow_plan.return_value = (
        "wf-123",
        [
            {"target_agent": "antigravity", "task_id": "task-1", "routing_reason": "r1"},
            {"target_agent": "codex", "task_id": "task-2", "routing_reason": "r2"}
        ]
    )
    
    mock_loop = mock_loop_cls.return_value
    mock_loop.run_multi_round_workflow.return_value = {
        "status": "BLOCKED_HUMAN_GATE",
        "stop_reason": "Needs human",
        "history": [{"round": 1}]
    }
    mock_loop.resume_workflow.return_value = {
        "status": "COMPLETED",
        "stop_reason": "All tasks done",
        "history": [{"round": 2}]
    }
    
    # Setup files so shutil.copy doesn't crash if they exist (or it skips if they don't, but let's make them exist)
    (repo_dir / "events/dispatch/task-1-worker-job.json").write_text("{}")
    (repo_dir / "events/processed/task-1-result.json").write_text("{}")
    (repo_dir / "events/chief-decisions/task-1-chief-decision.json").write_text("{}")
    (repo_dir / "events/dispatch/task-2-worker-job.json").write_text("{}")
    
    evidence_dir = repo_dir / "events/demo"
    orchestrator = DemoOrchestrator(repo_dir=repo_dir, evidence_dir=evidence_dir)
    orchestrator.reset_demo_environment()
    
    manifest = orchestrator.run_live_demo("Test idea", "IDEA")
    
    # Assertions
    assert manifest["status"] == "COMPLETED"
    assert manifest["human_input"]["raw_idea"] == "Test idea"
    assert manifest["human_input"]["type"] == "IDEA"
    assert manifest["human_gate"]["decision"] == "APPROVE"
    
    # Verify files were copied
    assert (evidence_dir / "tasks/task-1-worker-job.json").exists()
    assert (evidence_dir / "results/task-1-result.json").exists()
    assert (evidence_dir / "decisions/task-1-chief-decision.json").exists()
    assert (evidence_dir / "tasks/task-2-worker-job.json").exists()
    
    # Verify approvals event created
    approval_files = list((evidence_dir / "approvals").glob("appr-demo-*.json"))
    assert len(approval_files) == 1
    
    # Check manifest exists
    assert (evidence_dir / "demo_evidence_manifest.json").exists()

@patch("sys.argv", ["run_demo_workflow.py", "--reset", "--idea", "Test idea", "--type", "GOAL"])
@patch("scripts.run_demo_workflow.DemoOrchestrator")
def test_main(mock_orchestrator_cls):
    mock_instance = mock_orchestrator_cls.return_value
    mock_instance.run_live_demo.return_value = {"status": "COMPLETED"}
    
    exit_code = main()
    
    assert exit_code == 0
    mock_instance.reset_demo_environment.assert_called_once()
    mock_instance.run_live_demo.assert_called_once_with(raw_idea="Test idea", idea_type="GOAL")

@patch("sys.argv", ["run_demo_workflow.py", "--idea", "Fail idea"])
@patch("scripts.run_demo_workflow.DemoOrchestrator")
def test_main_failure(mock_orchestrator_cls):
    mock_instance = mock_orchestrator_cls.return_value
    mock_instance.run_live_demo.return_value = {"status": "FAILED"}
    
    exit_code = main()
    
    assert exit_code == 1
    mock_instance.reset_demo_environment.assert_not_called()
    mock_instance.run_live_demo.assert_called_once_with(raw_idea="Fail idea", idea_type="GOAL")

def test_save_load_json(tmp_path):
    test_file = tmp_path / "test.json"
    data = {"key": "value"}
    save_json(test_file, data)
    assert test_file.exists()
    
    loaded = load_json(test_file)
    assert loaded == data
