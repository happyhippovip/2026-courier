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


def test_state_file_does_not_follow_a_symlink(capsys, tmp_path, monkeypatch):
    secret = {
        "goals": {
            "g-secret": {
                "status": "ACTIVE",
                "workflow_plan": [{"status": "UNASSIGNED"}],
            }
        }
    }

    file_root = tmp_path / "file-case"
    file_root.mkdir()
    monkeypatch.chdir(file_root)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(secret), encoding="utf-8")
    state = Path("server/state/central_state.json")
    state.parent.mkdir(parents=True)
    state.symlink_to(outside)
    try:
        status_main()
        file_err = None
    except ValueError as exc:
        file_err = str(exc)
    file_out = capsys.readouterr().out

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    monkeypatch.chdir(parent_root)
    outside_dir = tmp_path / "outside-state"
    outside_dir.mkdir()
    (outside_dir / "central_state.json").write_text(json.dumps(secret), encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    Path("server").mkdir()
    Path("server/state").symlink_to(outside_dir)
    try:
        status_main()
        parent_err = None
    except ValueError as exc:
        parent_err = str(exc)
    parent_out = capsys.readouterr().out
    names = sorted(path.name for path in outside_dir.iterdir())
    assert (
        file_err,
        "Unassigned P0 Tasks: 1" in file_out,
        parent_err,
        "Unassigned P0 Tasks: 1" in parent_out,
        names,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        ["central_state.json", "keep.txt"],
    )
