import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from session_handoff import SessionHandoff, generate_handoff, HandoffValidationError, validate_handoff

def get_valid_handoff():
    return SessionHandoff(
        project_identity="Courier Symphony",
        current_gate="REAL_CODING_E2E_CLEAN_VERIFIED",
        current_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        completed_work=["H1", "H2"],
        accepted_evidence=["memory/WINDOWS_VERIFICATION_LEDGER.md"],
        active_writers=["Worker 1"],
        dirty_worktrees=[],
        blocked_paths=["PROVIDER_QUOTA"],
        human_decisions=["Use explicit provenance metadata."],
        next_executable_work=["H3"],
        artifacts=["handoff_v1.json"],
        safe_continuation_instructions="Read CHIEF_BRAIN_STATE.md and resume from H3."
    )

def test_valid_handoff_generation():
    handoff = get_valid_handoff()
    json_str = generate_handoff(handoff)
    
    data = json.loads(json_str)
    assert data["project_identity"] == "Courier Symphony"
    assert data["current_sha"] == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

def test_missing_required_fields():
    handoff = get_valid_handoff()
    data = handoff.to_dict()
    del data["completed_work"]
    
    with pytest.raises(HandoffValidationError, match="completed_work"):
        validate_handoff(data)

def test_invalid_sha_format():
    handoff = get_valid_handoff()
    data = handoff.to_dict()
    data["current_sha"] = "invalid_sha_format"
    
    with pytest.raises(HandoffValidationError, match="invalid_sha_format"):
        validate_handoff(data)
