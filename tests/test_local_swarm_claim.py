import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import local_swarm_claim

@pytest.fixture
def temp_swarm_dir(tmp_path):
    # Override the module-level paths to point to tmp_path
    original_BANK = local_swarm_claim.BANK
    original_STATE = local_swarm_claim.STATE
    original_CLAIMS = local_swarm_claim.CLAIMS
    original_DONE = local_swarm_claim.DONE
    original_BLOCKED = local_swarm_claim.BLOCKED
    original_LOCKS = local_swarm_claim.LOCKS
    original_STOP = local_swarm_claim.STOP
    
    bank_path = tmp_path / "BANK.json"
    state_path = tmp_path / ".courier_swarm"
    
    local_swarm_claim.BANK = bank_path
    local_swarm_claim.STATE = state_path
    local_swarm_claim.CLAIMS = state_path / "claims"
    local_swarm_claim.DONE = state_path / "done"
    local_swarm_claim.BLOCKED = state_path / "blocked"
    local_swarm_claim.LOCKS = state_path / "locks"
    local_swarm_claim.STOP = state_path / "STOP"
    
    local_swarm_claim.ensure()
    
    # Write a dummy bank file
    bank_data = {
        "tasks": [
            {"id": "T1", "pool": "windows-google"},
            {"id": "T2", "pool": "mac-google"},
            {"id": "T3", "pool": "windows-google", "exclusive_group": "group_a"}
        ]
    }
    bank_path.write_text(json.dumps(bank_data))
    
    yield
    
    local_swarm_claim.BANK = original_BANK
    local_swarm_claim.STATE = original_STATE
    local_swarm_claim.CLAIMS = original_CLAIMS
    local_swarm_claim.DONE = original_DONE
    local_swarm_claim.BLOCKED = original_BLOCKED
    local_swarm_claim.LOCKS = original_LOCKS
    local_swarm_claim.STOP = original_STOP

@patch("scripts.local_swarm_claim.emit")
def test_claim_success(mock_emit, temp_swarm_dir):
    ret = local_swarm_claim.claim("windows-google")
    assert ret == 0
    mock_emit.assert_called_once()
    args = mock_emit.call_args[0][0]
    assert args["status"] == "CLAIMED"
    assert args["task"]["id"] == "T1"

@patch("scripts.local_swarm_claim.emit")
def test_claim_no_task(mock_emit, temp_swarm_dir):
    ret = local_swarm_claim.claim("muse-windows") # Not in the mock bank
    assert ret == 2
    mock_emit.assert_called_once()
    args = mock_emit.call_args[0][0]
    assert args["status"] == "NO_TASK"

@patch("scripts.local_swarm_claim.emit")
def test_stop_resume(mock_emit, temp_swarm_dir):
    local_swarm_claim.STOP.write_text("Test stop")
    
    ret = local_swarm_claim.claim("windows-google")
    assert ret == 3
    args = mock_emit.call_args[0][0]
    assert args["status"] == "STOPPED"
    
    # Resume
    mock_emit.reset_mock()
    local_swarm_claim.STOP.unlink()
    ret = local_swarm_claim.claim("windows-google")
    assert ret == 0

@patch("scripts.local_swarm_claim.emit")
def test_complete_task(mock_emit, temp_swarm_dir):
    # First claim T1
    local_swarm_claim.claim("windows-google")
    
    claim_file = local_swarm_claim.CLAIMS / "T1" / "claim.json"
    claim_data = json.loads(claim_file.read_text())
    token = claim_data["token"]
    
    mock_emit.reset_mock()
    ret = local_swarm_claim.finish("complete", "T1", token, "Done!")
    assert ret == 0
    assert (local_swarm_claim.DONE / "T1.json").exists()
    assert not claim_file.exists()

@patch("scripts.local_swarm_claim.emit")
def test_release_task(mock_emit, temp_swarm_dir):
    # First claim T1
    local_swarm_claim.claim("windows-google")
    
    claim_file = local_swarm_claim.CLAIMS / "T1" / "claim.json"
    claim_data = json.loads(claim_file.read_text())
    token = claim_data["token"]
    
    mock_emit.reset_mock()
    # release requires calling main or simulating it. We can just test unlock logic
    local_swarm_claim.unlock(claim_data)
    assert not claim_file.exists()
