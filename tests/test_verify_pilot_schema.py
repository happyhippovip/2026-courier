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
