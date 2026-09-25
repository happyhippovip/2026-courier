import os
import json
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
sys.modules['windows_worker'] = mock.Mock()

from scripts import account_switch

def test_trigger_account_switch(tmp_path):
    # Setup state
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "goals": {
            "g1": {
                "workflow_plan": [
                    {"task_id": "T1", "status": "RUNNING"}
                ]
            }
        }
    }))
    
    # Mock worker
    mock_worker = mock.Mock()
    mock_worker.current_task = {"task_id": "T1"}
    mock_worker.owned_pids = {9999}
    
    # Patch paths
    with mock.patch("scripts.account_switch.os.path.exists", return_value=True):
        original_open = open
        def mock_open(path, mode='r', **kwargs):
            path_str = str(path)
            if 'central_state.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(state_file), mode, **kwargs)
            if 'account_session.json' in path_str and not os.path.isabs(path_str):
                return original_open(str(tmp_path / "account_session.json"), mode, **kwargs)
            return original_open(path_str, mode, **kwargs)
            
        with mock.patch("builtins.open", mock_open):
            mock_proc = mock.Mock()
            mock_proc.children.return_value = []
            
            with mock.patch("scripts.account_switch.psutil.Process", return_value=mock_proc) as mock_psutil:
                account_switch.trigger_account_switch(mock_worker, "TEST_ACCOUNT")
                
    # Process should be terminated
    mock_psutil.assert_called_once_with(9999)
    mock_proc.terminate.assert_called_once()
    
    # Pids should be cleared
    assert len(mock_worker.owned_pids) == 0
    
    # Account should be saved
    account_data = json.loads((tmp_path / "account_session.json").read_text())
    assert account_data["active_account"] == "TEST_ACCOUNT"
    
    # Task should end up in RUNNING because the script transitions it to WAITING_PROVIDER and then resumes it to RUNNING
    final_state = json.loads(state_file.read_text())
    assert final_state["goals"]["g1"]["workflow_plan"][0]["status"] == "RUNNING"

def test_trigger_account_switch_no_current_task(tmp_path):
    mock_worker = mock.Mock()
    mock_worker.current_task = None
    mock_worker.owned_pids = set()
    
    original_open = open
    def mock_open(path, mode='r', **kwargs):
        path_str = str(path)
        if 'account_session.json' in path_str and not os.path.isabs(path_str):
            return original_open(str(tmp_path / "account_session.json"), mode, **kwargs)
        return original_open(path_str, mode, **kwargs)
        
    with mock.patch("builtins.open", mock_open):
        account_switch.trigger_account_switch(mock_worker, "TEST_ACCOUNT_2")
        
    account_data = json.loads((tmp_path / "account_session.json").read_text())
    assert account_data["active_account"] == "TEST_ACCOUNT_2"

