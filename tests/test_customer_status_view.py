import json
import sys
from pathlib import Path
import pytest

from scripts.customer_status_view import map_internal_to_customer_status, get_customer_view, main
from scripts.customer_status import get_customer_status


def test_status_mappings():
    assert map_internal_to_customer_status("NEW") == "QUEUED"
    assert map_internal_to_customer_status("QUEUED") == "QUEUED"
    assert map_internal_to_customer_status("RUNNING") == "RUNNING"
    assert map_internal_to_customer_status("IN_PROGRESS") == "RUNNING"
    assert map_internal_to_customer_status("WAITING") == "WAITING"
    assert map_internal_to_customer_status("NEEDS_APPROVAL") == "NEEDS_APPROVAL"
    assert map_internal_to_customer_status("DONE") == "DONE"
    assert map_internal_to_customer_status("COMPLETED") == "DONE"
    assert map_internal_to_customer_status("FAILED") == "FAILED"
    assert map_internal_to_customer_status("UNKNOWN_VAL") == "WAITING"

    assert get_customer_status("EXECUTING") == "RUNNING"
    assert get_customer_status("ORPHANED") == "QUEUED"
    assert get_customer_status("COMPLETED") == "DONE"
    assert get_customer_status("WAIT_FOR_GITHUB_PR") == "WAITING"


def test_get_customer_view_missing_file(tmp_path: Path):
    nonexistent = tmp_path / "central_state.json"
    view = get_customer_view("task-123", state_file=str(nonexistent))
    assert "error" in view
    assert "No tasks found" in view["error"]


def test_get_customer_view_task_found_and_admin(tmp_path: Path):
    state_file = tmp_path / "central_state.json"
    data = {
        "tasks": {
            "task-456": {
                "task_id": "task-456",
                "customer_reference": "CUST-REF-99",
                "state": "IN_PROGRESS",
                "worker_id": "WIN-WORKER-01",
                "dispatch_ref": "DISPATCH-1",
                "execution_ref": "EXEC-1",
                "real_wall": 1.25,
            }
        }
    }
    state_file.write_text(json.dumps(data), encoding="utf-8")

    # Regular customer view
    reg_view = get_customer_view("task-456", is_admin=False, state_file=str(state_file))
    assert reg_view["task_id"] == "task-456"
    assert reg_view["customer_reference"] == "CUST-REF-99"
    assert reg_view["status"] == "RUNNING"
    assert "_internal_state" not in reg_view

    # Admin view
    admin_view = get_customer_view("task-456", is_admin=True, state_file=str(state_file))
    assert admin_view["task_id"] == "task-456"
    assert admin_view["_internal_state"] == "IN_PROGRESS"
    assert admin_view["_worker_id"] == "WIN-WORKER-01"


def test_customer_status_view_cli(tmp_path: Path, capsys, monkeypatch):
    state_file = tmp_path / "central_state.json"
    data = {
        "tasks": {
            "task-cli": {
                "task_id": "task-cli",
                "customer_reference": "CUST-CLI",
                "state": "DONE",
            }
        }
    }
    state_file.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["customer_status_view.py", "task-cli", "--state-file", str(state_file), "--json"],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["task_id"] == "task-cli"
    assert res["status"] == "DONE"
