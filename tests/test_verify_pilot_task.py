import sys
import json
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path
import runpy

from scripts.verify_pilot_task import verify_task

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_pilot_task.py"
    
    # We must patch sys.exit since the script uses it
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

def test_verify_pilot_task_success(capsys):
    dummy_task = {
        "workflow_plan": [
            {
                "task_id": "t1",
                "goal_id": "g1",
                "target_capability": "windows",
                "instruction": "Do something",
                "status": "QUEUED"
            }
        ]
    }
    mock_json = json.dumps(dummy_task)
    with patch("builtins.open", mock_open(read_data=mock_json)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "PILOT TASK VERIFIED - SCHEMA MATCHES" in captured.out
    m_exit.assert_not_called()

def test_verify_pilot_task_missing_plan(capsys):
    dummy_task = {}
    mock_json = json.dumps(dummy_task)
    with patch("builtins.open", mock_open(read_data=mock_json)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "FAILED: Missing or empty workflow_plan" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_pilot_task_missing_fields(capsys):
    dummy_task = {
        "workflow_plan": [
            {
                "task_id": "t1"
            }
        ]
    }
    mock_json = json.dumps(dummy_task)
    with patch("builtins.open", mock_open(read_data=mock_json)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "FAILED: Missing fields" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_pilot_task_wrong_status(capsys):
    dummy_task = {
        "workflow_plan": [
            {
                "task_id": "t1",
                "goal_id": "g1",
                "target_capability": "windows",
                "instruction": "Do something",
                "status": "IN_PROGRESS"
            }
        ]
    }
    mock_json = json.dumps(dummy_task)
    with patch("builtins.open", mock_open(read_data=mock_json)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "FAILED: status should be QUEUED, got IN_PROGRESS" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_pilot_task_exception(capsys):
    with patch("builtins.open", side_effect=Exception("Disk broken")):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "FAILED: Disk broken" in captured.out
    m_exit.assert_called_once_with(1)


def test_pilot_task_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    task = {
        "workflow_plan": [{
            "task_id": "t1",
            "goal_id": "SECRET-PILOT",
            "target_capability": "windows",
            "instruction": "outside",
            "status": "QUEUED",
        }]
    }

    def run(root):
        monkeypatch.chdir(root)
        try:
            verify_task()
            err = None
        except ValueError as exc:
            err = str(exc)
        return err, capsys.readouterr().out

    file_root = tmp_path / "file-case"
    file_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(task), encoding="utf-8")
    path = file_root / "ops" / "ai" / "PILOT_DUMMY_TASK.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(outside)
    file_err, file_out = run(file_root)

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    outside_dir = tmp_path / "outside-ai"
    outside_dir.mkdir()
    (outside_dir / "PILOT_DUMMY_TASK.json").write_text(json.dumps(task), encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    ai = parent_root / "ops" / "ai"
    ai.parent.mkdir(parents=True)
    ai.symlink_to(outside_dir)
    parent_err, parent_out = run(parent_root)
    names = sorted(path.name for path in outside_dir.iterdir())
    assert (
        file_err,
        "PILOT TASK VERIFIED" in file_out,
        parent_err,
        "PILOT TASK VERIFIED" in parent_out,
        "SECRET-PILOT" in outside.read_text(encoding="utf-8"),
        names,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        True,
        ["PILOT_DUMMY_TASK.json", "keep.txt"],
    )
