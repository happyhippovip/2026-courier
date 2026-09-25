import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import export_data

def test_export_customer_data_no_state(tmp_path, capsys):
    export_path = tmp_path / "out.json"
    
    with mock.patch("scripts.export_data.os.path.exists", return_value=False):
        export_data.export_customer_data(str(export_path))
        
    captured = capsys.readouterr()
    assert "No state file found" in captured.out
    assert not export_path.exists()

def test_export_customer_data_invalid_json(tmp_path, capsys):
    state_file = tmp_path / "central_state.json"
    state_file.write_text("invalid json")
    export_path = tmp_path / "out.json"
    
    with mock.patch("scripts.export_data.os.path.exists", return_value=True):
        original_open = open
        def mock_open(path, mode='r', **kwargs):
            if 'central_state.json' in str(path):
                return original_open(str(state_file), mode, **kwargs)
            return original_open(path, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            export_data.export_customer_data(str(export_path))
            
    captured = capsys.readouterr()
    assert "Failed to decode state file." in captured.out
    assert not export_path.exists()

def test_export_customer_data_success(tmp_path, capsys):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "goals": {
            "g1": {
                "description": "Goal 1",
                "status": "DONE",
                "created_at": "123",
                "completed_at": "456",
                "secret_info": "shhh"
            }
        },
        "tasks": {
            "t1": {
                "type": "audit",
                "status": "QUEUED",
                "artifacts": ["file.txt"],
                "chain_of_thought": "bla bla",
                "secret_key": "123"
            }
        }
    }))
    
    export_path = tmp_path / "out.json"
    
    with mock.patch("scripts.export_data.os.path.exists", return_value=True):
        original_open = open
        def mock_open(path, mode='r', **kwargs):
            path_str = str(path)
            if 'central_state.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(state_file), mode, **kwargs)
            return original_open(path_str, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            export_data.export_customer_data(str(export_path))
            
    captured = capsys.readouterr()
    assert "Customer data successfully exported" in captured.out
    assert export_path.exists()
    
    exported = json.loads(export_path.read_text())
    assert "exported_at" in exported
    
    # Check goal redaction
    assert len(exported["goals"]) == 1
    g = exported["goals"][0]
    assert g["goal_id"] == "g1"
    assert "secret_info" not in g
    
    # Check task redaction
    assert len(exported["tasks"]) == 1
    t = exported["tasks"][0]
    assert t["task_id"] == "t1"
    assert t["artifacts"] == ["file.txt"]
    assert "chain_of_thought" not in t
    assert "secret_key" not in t

