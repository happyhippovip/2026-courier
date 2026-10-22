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


def _point_swarm(state_path, bank_path):
    saved = {
        "BANK": local_swarm_claim.BANK,
        "STATE": local_swarm_claim.STATE,
        "CLAIMS": local_swarm_claim.CLAIMS,
        "DONE": local_swarm_claim.DONE,
        "BLOCKED": local_swarm_claim.BLOCKED,
        "LOCKS": local_swarm_claim.LOCKS,
        "STOP": local_swarm_claim.STOP,
    }
    local_swarm_claim.BANK = bank_path
    local_swarm_claim.STATE = state_path
    local_swarm_claim.CLAIMS = state_path / "claims"
    local_swarm_claim.DONE = state_path / "done"
    local_swarm_claim.BLOCKED = state_path / "blocked"
    local_swarm_claim.LOCKS = state_path / "locks"
    local_swarm_claim.STOP = state_path / "STOP"
    return saved


def _restore_swarm(saved):
    for name, value in saved.items():
        setattr(local_swarm_claim, name, value)


@patch("scripts.local_swarm_claim.emit")
def test_claim_does_not_follow_a_symlink(mock_emit, tmp_path):
    bank_path = tmp_path / "BANK.json"
    bank_path.write_text(json.dumps({"tasks": [{"id": "T1", "pool": "windows-google"}]}), encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-swarm"
    linked.symlink_to(outside)
    claims_outside = tmp_path / "claims-outside"
    claims_outside.mkdir()
    (claims_outside / "keep.txt").write_text("keep", encoding="utf-8")
    real_state = tmp_path / "real-swarm"
    real_state.mkdir()
    linked_claims = real_state / "claims"
    linked_claims.symlink_to(claims_outside)
    plain = tmp_path / "plain-swarm"

    def run(state):
        saved = _point_swarm(state, bank_path)
        try:
            try:
                return local_swarm_claim.claim("windows-google")
            except SystemExit as exc:
                return str(exc)
        finally:
            _restore_swarm(saved)

    err_state = run(linked)
    err_claims = run(real_state)
    err_plain = run(plain)
    leaked_state = sorted(p.name for p in outside.iterdir())
    leaked_claims = sorted(p.name for p in claims_outside.iterdir())
    plain_claims = sorted(p.name for p in (plain / "claims").iterdir()) if (plain / "claims").exists() else []
    refused = "refusing to follow a symlink"
    assert (
        err_state == refused
        and leaked_state == ["keep.txt"]
        and err_claims == refused
        and leaked_claims == ["keep.txt"]
        and err_plain == 0
        and plain_claims == ["T1"]
        and linked.is_symlink()
        and linked_claims.is_symlink()
    ), (
        err_state, leaked_state, err_claims, leaked_claims,         err_plain, plain_claims,
    )


@patch("scripts.local_swarm_claim.emit")
def test_bank_does_not_follow_a_symlink(mock_emit, tmp_path):
    outside = tmp_path / "outside-bank.json"
    outside.write_text(
        json.dumps({"tasks": [{"id": "SECRET-TASK", "pool": "windows-google"}]}),
        encoding="utf-8",
    )
    linked = tmp_path / "linked-bank.json"
    linked.symlink_to(outside)
    parent_real = tmp_path / "parent-real"
    parent_real.mkdir()
    (parent_real / "bank.json").write_text(
        json.dumps({"tasks": [{"id": "SECRET-PARENT", "pool": "windows-google"}]}),
        encoding="utf-8",
    )
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(parent_real)
    plain_bank = tmp_path / "plain-bank.json"
    plain_bank.write_text(
        json.dumps({"tasks": [{"id": "T1", "pool": "windows-google"}]}),
        encoding="utf-8",
    )

    def run(bank, tag):
        state = tmp_path / f"state-{tag}"
        saved = _point_swarm(state, bank)
        mock_emit.reset_mock()
        try:
            try:
                err = local_swarm_claim.claim("windows-google")
            except SystemExit as exc:
                err = str(exc)
        finally:
            _restore_swarm(saved)
        names = sorted(p.name for p in (state / "claims").iterdir()) if (state / "claims").exists() else []
        claimed = None
        if mock_emit.called and mock_emit.call_args[0][0].get("status") == "CLAIMED":
            claimed = mock_emit.call_args[0][0]["task"]["id"]
        return err, names, claimed

    err_link, names_link, claimed_link = run(linked, "link")
    err_parent, names_parent, claimed_parent = run(parent_link / "bank.json", "parent")
    err_plain, names_plain, claimed_plain = run(plain_bank, "plain")
    refused = "refusing to follow a symlink"
    assert (
        err_link == refused and names_link == [] and claimed_link is None
        and err_parent == refused and names_parent == [] and claimed_parent is None
        and err_plain == 0 and names_plain == ["T1"] and claimed_plain == "T1"
        and linked.is_symlink() and parent_link.is_symlink()
        and outside.read_text(encoding="utf-8").startswith("{")
    ), (
        err_link, names_link, claimed_link,
        err_parent, names_parent, claimed_parent,
        err_plain, names_plain, claimed_plain,
    )
