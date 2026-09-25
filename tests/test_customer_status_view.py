import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import customer_status_view

def test_map_internal_to_customer_status():
    assert customer_status_view.map_internal_to_customer_status("NEW") == "QUEUED"
    assert customer_status_view.map_internal_to_customer_status("DISPATCHED_TO_EXTERNAL") == "RUNNING"
    assert customer_status_view.map_internal_to_customer_status("WAITING_FOR_CHIEF_COMMAND") == "WAITING"
    assert customer_status_view.map_internal_to_customer_status("HUMAN_REVIEW_REQUIRED_ON_PR") == "NEEDS_APPROVAL"
    assert customer_status_view.map_internal_to_customer_status("SUCCESS") == "DONE"
    assert customer_status_view.map_internal_to_customer_status("SYSTEM_FAILURE") == "FAILED"
    assert customer_status_view.map_internal_to_customer_status("RANDOM_STATE") == "WAITING"

def test_get_customer_view_missing_file(tmp_path):
    with mock.patch("scripts.customer_status_view.os.path.exists", return_value=False):
        view = customer_status_view.get_customer_view("T1")
        assert "error" in view

def test_get_customer_view_missing_task(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({"tasks": {}}))
    
    with mock.patch("scripts.customer_status_view.os.path.exists", return_value=True):
        original_open = open
        def mock_open(path, mode='r', **kwargs):
            if 'central_state.json' in str(path):
                return original_open(str(state_file), mode, **kwargs)
            return original_open(path, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            view = customer_status_view.get_customer_view("T1")
            assert "error" in view

def test_get_customer_view_success_user(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "tasks": {
            "T1": {
                "task_id": "T1",
                "customer_reference": "CUST-1",
                "state": "IN_PROGRESS",
                "worker_id": "W1"
            }
        }
    }))
    
    with mock.patch("scripts.customer_status_view.os.path.exists", return_value=True):
        original_open = open
        def mock_open(path, mode='r', **kwargs):
            if 'central_state.json' in str(path):
                return original_open(str(state_file), mode, **kwargs)
            return original_open(path, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            view = customer_status_view.get_customer_view("T1", is_admin=False)
            
    assert view["task_id"] == "T1"
    assert view["customer_reference"] == "CUST-1"
    assert view["status"] == "RUNNING"
    assert "_worker_id" not in view

def test_get_customer_view_success_admin(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "tasks": {
            "T1": {
                "task_id": "T1",
                "state": "SYSTEM_FAILURE",
                "worker_id": "W1",
                "execution_ref": "EXEC-123"
            }
        }
    }))
    
    with mock.patch("scripts.customer_status_view.os.path.exists", return_value=True):
        original_open = open
        def mock_open(path, mode='r', **kwargs):
            if 'central_state.json' in str(path):
                return original_open(str(state_file), mode, **kwargs)
            return original_open(path, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            view = customer_status_view.get_customer_view("T1", is_admin=True)
            
    assert view["status"] == "FAILED"
    assert view["customer_reference"] == "N/A"
    assert view["_internal_state"] == "SYSTEM_FAILURE"
    assert view["_worker_id"] == "W1"
    assert view["_execution_ref"] == "EXEC-123"

