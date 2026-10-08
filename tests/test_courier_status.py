import json
import pytest
from pathlib import Path
from unittest.mock import patch

from scripts.courier_status import main


def test_courier_status_no_ledger(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main()
    out, err = capsys.readouterr()
    assert "Courier Symphony: No ledger found." in out


def test_courier_status_green_all_assigned(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "central_state.json"

    state_content = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {"step_id": "s1", "status": "IN_PROGRESS"},
                    {"step_id": "s2", "status": "COMPLETED"}
                ]
            },
            "g2": {
                "status": "COMPLETED",
                "workflow_plan": [
                    {"step_id": "s3", "status": "UNASSIGNED"}
                ]
            }
        }
    }
    state_file.write_text(json.dumps(state_content))

    main()
    out, err = capsys.readouterr()
    assert "Health: GREEN" in out
    assert "Unassigned P0 Tasks: 0" in out
    assert "Active Goals: 1" in out


def test_courier_status_yellow_unassigned_tasks(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "server" / "state"
    state_dir.mkdir(parents=True)
    state_file = state_dir / "central_state.json"

    state_content = {
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {"step_id": "s1", "status": "UNASSIGNED"},
                    {"step_id": "s2", "status": "UNASSIGNED"}
                ]
            },
            "g2": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {"step_id": "s3", "status": "IN_PROGRESS"}
                ]
            }
        }
    }
    state_file.write_text(json.dumps(state_content))

    main()
    out, err = capsys.readouterr()
    assert "Health: YELLOW" in out
    assert "Unassigned P0 Tasks: 2" in out
    assert "Active Goals: 2" in out
