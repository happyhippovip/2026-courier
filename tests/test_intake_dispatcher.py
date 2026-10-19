import pytest
import os
import json
import subprocess
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import intake_dispatcher

@pytest.fixture(autouse=True)
def clean_central_state(tmp_path, monkeypatch):
    # dispatch_intake writes central_state.json in the CWD: keep it in tmp_path.
    monkeypatch.chdir(tmp_path)
    yield

def test_dispatch_intake_success(tmp_path):
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test_owner",
        "target_repo": "test_repo",
        "target_sha": "123456",
        "customer_reference": "CUST-001"
    }))
    
    # Run binding (exactly one new run after dispatch, else UNBOUND) is pinned by
    # the M05 dispatcher tests; here the dispatch binds to run 9999.
    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run, \
         mock.patch("scripts.intake_dispatcher.resolve_execution_ref", return_value="9999"), \
         mock.patch("scripts.intake_dispatcher.time.sleep"):

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
            
        # M05-Q3: the task id is a stable fingerprint of the intake, not a random uuid.
        task_id = intake_dispatcher.fingerprint_task_id(json.loads(intake_file.read_text()))
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

def test_failed_durable_write_does_not_report_dispatch_success(tmp_path, capsys):
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "target_owner": "test_owner",
        "target_repo": "test_repo",
        "target_sha": "123456",
        "customer_reference": "CUST-001"
    }))
    real_save = intake_dispatcher.save_central_state
    calls = {"n": 0}

    def fail_final_save(path, state):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OSError("durable write failed")
        real_save(path, state)

    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run, \
         mock.patch("scripts.intake_dispatcher.resolve_execution_ref", return_value="9999"), \
         mock.patch("scripts.intake_dispatcher.time.sleep"), \
         mock.patch("scripts.intake_dispatcher.save_central_state", side_effect=fail_final_save):
        mock_run.return_value = mock.Mock(stdout="dispatched")
        with pytest.raises(OSError, match="durable write failed"):
            intake_dispatcher.dispatch_intake(str(intake_file))

    captured = capsys.readouterr().out
    assert "Successfully dispatched" not in captured
    assert "fully connected" not in captured
    assert calls["n"] >= 2


def test_dispatch_intake_corrupt_state_fails_closed(tmp_path):
    # M05-Q2: a corrupt central state is never reset-and-overwritten (that would
    # silently wipe every recorded task); the dispatch exits non-zero, unrecorded.
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
         mock.patch("scripts.intake_dispatcher.time.sleep"):
        mock_run.return_value = mock.Mock(stdout="9999")
        with pytest.raises(SystemExit) as exc:
            intake_dispatcher.dispatch_intake(str(intake_file))
        assert exc.value.code == 1

    with open(state_file, "r") as f:
        assert f.read() == "not a valid json"
