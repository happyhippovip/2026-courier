import pytest
import sys
import runpy
from unittest.mock import patch, mock_open
from pathlib import Path

def test_verify_pilot_schema_success(capsys):
    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    dummy_task = {
        "goal_id": "test_goal",
        "workflow_plan": [
            {
                "task_id": "task_1",
                "goal_id": "test_goal",
                "target_capability": "windows",
                "instruction": "Test instruction"
            }
        ]
    }
    
    import json
    mock_json = json.dumps(dummy_task)
    
    # We must patch open specifically for the ops/ai/PILOT_DUMMY_TASK.json file
    with patch("builtins.open", mock_open(read_data=mock_json)) as m_open:
        # Patch prepare_task just in case, or let it run. It's from integration_contract which has no side effects.
        # But we need to ensure target_capability exists in WORKER_IDS.
        # Wait, the script imports WORKER_IDS and uses it.
        # Let's import it to check what it has.
        from scripts.integration_contract import WORKER_IDS
        
        runpy.run_path(str(Path(repo_root) / "scripts" / "verify_pilot_schema.py"), run_name="__main__")
        
        out, _ = capsys.readouterr()
        assert "Task task_1 prepared successfully" in out
        assert "PILOT_DUMMY_SCHEMA_VERIFIED=PASS" in out
        
def test_verify_pilot_schema_missing_goal_id():
    repo_root = str(Path(__file__).resolve().parent.parent)
    dummy_task = {
        "workflow_plan": [
            {
                "task_id": "task_1",
                "target_capability": "antigravity",
                "instruction": "Test instruction"
            }
        ]
    }
    
    import json
    mock_json = json.dumps(dummy_task)
    
    with patch("builtins.open", mock_open(read_data=mock_json)):
        with pytest.raises(AssertionError, match="goal_id required"):
            runpy.run_path(str(Path(repo_root) / "scripts" / "verify_pilot_schema.py"), run_name="__main__")

def test_verify_pilot_schema_missing_workflow():
    repo_root = str(Path(__file__).resolve().parent.parent)
    dummy_task = {
        "goal_id": "test_goal",
        "workflow_plan": []
    }
    
    import json
    mock_json = json.dumps(dummy_task)
    
    with patch("builtins.open", mock_open(read_data=mock_json)):
        with pytest.raises(AssertionError, match="workflow_plan required"):
            runpy.run_path(str(Path(repo_root) / "scripts" / "verify_pilot_schema.py"), run_name="__main__")


def test_pilot_schema_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    import json
    script = Path(__file__).resolve().parent.parent / "scripts" / "verify_pilot_schema.py"
    task = {
        "goal_id": "SECRET-PILOT",
        "workflow_plan": [{
            "task_id": "task_1",
            "goal_id": "SECRET-PILOT",
            "target_capability": "windows",
            "instruction": "outside",
        }],
    }

    def run(root):
        monkeypatch.chdir(root)
        try:
            runpy.run_path(str(script), run_name="__main__")
            err = None
        except ValueError as exc:
            err = str(exc)
        return err, capsys.readouterr().out

    file_root = tmp_path / "file-case"
    ai = file_root / "ops" / "ai"
    ai.mkdir(parents=True)
    outside = tmp_path / "outside-task.json"
    outside.write_text(json.dumps(task), encoding="utf-8")
    (ai / "PILOT_DUMMY_TASK.json").symlink_to(outside)
    file_err, file_out = run(file_root)

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    outside_dir = tmp_path / "outside-ai"
    outside_dir.mkdir()
    (outside_dir / "PILOT_DUMMY_TASK.json").write_text(json.dumps(task), encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (parent_root / "ops").mkdir()
    (parent_root / "ops" / "ai").symlink_to(outside_dir)
    parent_err, parent_out = run(parent_root)
    names = sorted(path.name for path in outside_dir.iterdir())
    assert (
        file_err,
        "PILOT_DUMMY_SCHEMA_VERIFIED=PASS" in file_out,
        parent_err,
        "PILOT_DUMMY_SCHEMA_VERIFIED=PASS" in parent_out,
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
