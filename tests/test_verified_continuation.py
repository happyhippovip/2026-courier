import sys
import pytest
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from continuation_token import ContinuationToken, ContinuationContext
from verified_continuation import LiveEnvironmentProvider, verify_continuation_safety, VerifiedContinuationError

class MockEnv(LiveEnvironmentProvider):
    def __init__(self):
        self.sha = "a1b2c3d"
        self.writers = []
        self.dirty = []
        self.deps = "deps-hash-123"
        self.evidence = True
        self.checkpoint = "VERIFIED"
        
    def get_current_sha(self) -> str: return self.sha
    def get_active_writers(self) -> List[str]: return self.writers
    def get_dirty_files(self) -> List[str]: return self.dirty
    def get_dependencies_hash(self) -> str: return self.deps
    def has_required_evidence(self, workkey: str) -> bool: return self.evidence
    def get_last_checkpoint_state(self, workkey: str) -> str: return self.checkpoint

def get_token():
    ctx = ContinuationContext(
        project="Courier",
        workkey="H1",
        sha="a1b2c3d",
        session_id="session-999",
        checkpoint_state="VERIFIED"
    )
    return ContinuationToken(ctx)

def test_safe_continuation():
    env = MockEnv()
    token = get_token()
    # Should not raise
    assert verify_continuation_safety(token, env, "deps-hash-123") == True

def test_fails_on_sha_drift():
    env = MockEnv()
    env.sha = "a1b2c3e" # Drift!
    token = get_token()
    
    with pytest.raises(VerifiedContinuationError, match="Codebase SHA drifted"):
        verify_continuation_safety(token, env, "deps-hash-123")

def test_fails_on_writer_collision():
    env = MockEnv()
    env.writers = ["other-session"] # Someone else has the lock
    token = get_token()
    
    with pytest.raises(VerifiedContinuationError, match="Writer ownership lost or collision"):
        verify_continuation_safety(token, env, "deps-hash-123")

def test_fails_on_dirty_files():
    env = MockEnv()
    env.dirty = ["src/main.py"]
    token = get_token()
    
    with pytest.raises(VerifiedContinuationError, match="Dirty files present"):
        verify_continuation_safety(token, env, "deps-hash-123")

def test_fails_on_deps_drift():
    env = MockEnv()
    token = get_token()
    
    with pytest.raises(VerifiedContinuationError, match="Dependencies have changed"):
        verify_continuation_safety(token, env, "deps-hash-456") # Expected deps changed

def test_fails_on_missing_evidence():
    env = MockEnv()
    env.evidence = False # We claim VERIFIED, but evidence is missing!
    token = get_token()
    
    with pytest.raises(VerifiedContinuationError, match="Missing required evidence"):
        verify_continuation_safety(token, env, "deps-hash-123")
