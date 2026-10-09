import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.courier_status import main as status_main

def test_courier_status_no_ledger(capsys, tmp_path, monkeypatch):
    # Change current working directory to a temp path so state_file doesn't exist
    monkeypatch.chdir(tmp_path)
    status_main()
    captured = capsys.readouterr()
    assert "Courier Symphony: No ledger found." in captured.out

def test_courier_status_with_ledger_green(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    
    state_data = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {"status": "COMPLETED"}
                ]
            }
        }
    }
    
    state_file = state_dir / "central_state.json"
    with open(state_file, "w") as f:
        json.dump(state_data, f)
        
    status_main()
    captured = capsys.readouterr()
    assert "Health: GREEN" in captured.out
    assert "Unassigned P0 Tasks: 0" in captured.out
    assert "Active Goals: 1" in captured.out

def test_courier_status_with_ledger_yellow(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    
    state_data = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {"status": "UNASSIGNED"},
                    {"status": "COMPLETED"}
                ]
            }
        }
    }
    
    state_file = state_dir / "central_state.json"
    with open(state_file, "w") as f:
        json.dump(state_data, f)
        
    status_main()
    captured = capsys.readouterr()
    assert "Health: YELLOW" in captured.out
    assert "Unassigned P0 Tasks: 1" in captured.out
    assert "Active Goals: 1" in captured.out
