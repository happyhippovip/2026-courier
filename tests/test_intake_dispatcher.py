import pytest
import os
import json
import subprocess
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import intake_dispatcher

@pytest.fixture(autouse=True)
def clean_central_state():
    # Setup
    state_file = 'central_state.json'
    if os.path.exists(state_file):
        os.remove(state_file)
    yield
    # Teardown
    if os.path.exists(state_file):
        os.remove(state_file)

def test_dispatch_intake_success(tmp_path):
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test_owner",
        "target_repo": "test_repo",
        "target_sha": "123456",
        "customer_reference": "CUST-001"
    }))
    
    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run, \
         mock.patch("time.sleep"):
         
        def fake_run(cmd, *args, **kwargs):
            if cmd[1] == "workflow":
                return mock.Mock(stdout="dispatched")
            elif cmd[1] == "run":
                # Ensure the created time is strictly > 0 so it matches since_epoch
                return mock.Mock(stdout='[{"databaseId": 9999, "createdAt": "2030-01-01T00:00:00Z"}]')
            return mock.Mock()
        mock_run.side_effect = fake_run
        
        intake_dispatcher.dispatch_intake(str(intake_file))
        
        state_file = "central_state.json"
        assert os.path.exists(state_file)
        
        with open(state_file, "r") as f:
            state = json.load(f)
            
        task_id = "task-revenue-16c00b0f"
        assert task_id in state["tasks"]
        assert state["tasks"][task_id]["execution_ref"] == "9999"

def test_dispatch_intake_missing_key(tmp_path):
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test_owner"
        # missing target_repo
    }))
    
    with pytest.raises(KeyError):
        intake_dispatcher.dispatch_intake(str(intake_file))

def test_dispatch_intake_subprocess_error(tmp_path):
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test_owner",
        "target_repo": "test_repo",
        "target_sha": "123456",
        "customer_reference": "CUST-001"
    }))
    
    with mock.patch("scripts.intake_dispatcher.subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd", stderr="error")):
        with pytest.raises(SystemExit) as exc:
            intake_dispatcher.dispatch_intake(str(intake_file))
        assert exc.value.code == 1

def test_dispatch_intake_corrupt_state_wiped(tmp_path):
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test_owner",
        "target_repo": "test_repo",
        "target_sha": "123456",
        "customer_reference": "CUST-001"
    }))
    
    state_file = "central_state.json"
    with open(state_file, "w") as f:
        f.write("not a valid json")
        
    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run, \
         mock.patch("time.sleep"):
         
        mock_run.return_value = mock.Mock(stdout="9999")
        
        with pytest.raises(SystemExit) as exc:
            intake_dispatcher.dispatch_intake(str(intake_file))
        assert exc.value.code == 1
