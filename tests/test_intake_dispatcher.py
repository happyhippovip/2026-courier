import pytest
import os
import sys
import json
import subprocess
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import intake_dispatcher

def test_dispatch_intake_success(tmp_path, capsys):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        intake_file = tmp_path / "intake.json"
        intake_file.write_text(json.dumps({
            "target_owner": "org",
            "target_repo": "repo",
            "target_sha": "sha123",
            "customer_reference": "cust1"
        }))
        
        with mock.patch("subprocess.run") as mock_run:
            with mock.patch("time.sleep"):
                mock_run.side_effect = [
                    mock.Mock(stdout="", stderr=""),
                    mock.Mock(stdout="12345\n", stderr="")
                ]
                
                intake_dispatcher.dispatch_intake(str(intake_file))
                
        state_file = tmp_path / "central_state.json"
        assert state_file.exists()
        
        state = json.loads(state_file.read_text())
        assert len(state["tasks"]) == 1
        
        task_id = list(state["tasks"].keys())[0]
        t = state["tasks"][task_id]
        
        assert "task-revenue-" in task_id
        assert t["execution_ref"] == "12345"
        assert t["state"] == "DISPATCHED_TO_EXTERNAL"
        assert t["platform"] == "github"
        
        captured = capsys.readouterr()
        assert "Successfully dispatched" in captured.out
    finally:
        os.chdir(original_cwd)


def test_dispatch_intake_fail(tmp_path, capsys):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        intake_file = tmp_path / "intake.json"
        intake_file.write_text(json.dumps({
            "target_owner": "org",
            "target_repo": "repo",
            "target_sha": "sha123",
            "customer_reference": "cust1"
        }))
        
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "gh", stderr="gh error")):
            with pytest.raises(SystemExit) as exc:
                intake_dispatcher.dispatch_intake(str(intake_file))
                
            assert exc.value.code == 1
            
        captured = capsys.readouterr()
        assert "Failed to dispatch: gh error" in captured.out
    finally:
        os.chdir(original_cwd)

