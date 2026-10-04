import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from recovery_memory import RecoveryCapability, RecoveryMemoryStore

def test_terminal_host_failed_recovery():
    store = RecoveryMemoryStore()
    
    # Define a known, proven recovery capability
    term_crash_recovery = RecoveryCapability(
        fingerprint="TERMINAL_HOST_FAILED",
        preconditions=[
            "Process ID of the agent is no longer running",
            "Checkpoint lock file exists and is stale",
            "No uncommitted git changes outside of Courier's internal branch"
        ],
        safe_actions=[
            "Force-delete the stale checkpoint lock",
            "Resume execution from the exact last-known-good checkpoint SHA"
        ],
        forbidden_actions=[
            "Do not blindly 'git reset --hard' without checking for user-saved work",
            "Do not resume without first verifying the Continuation Token"
        ],
        verification="Agent successfully writes a new 'Started' checkpoint to disk",
        fallback="If lock deletion fails (e.g. Permission Denied), halt and prompt User.",
        evidence_links=["ev-terminal-crash-1", "ev-terminal-crash-2"]
    )
    
    store.register(term_crash_recovery)
    
    # Successful retrieval of explicit fingerprint
    recovered = store.get_capability("TERMINAL_HOST_FAILED")
    assert "Force-delete the stale checkpoint lock" in recovered.safe_actions
    
    # Strict failure on unrelated or unproven fingerprints (No generalization)
    with pytest.raises(KeyError, match="No proven recovery capability"):
        store.get_capability("NETWORK_HOST_FAILED")
        
    with pytest.raises(KeyError, match="Do not generalize automatically"):
        store.get_capability("TERMINAL_UNRESPONSIVE")
