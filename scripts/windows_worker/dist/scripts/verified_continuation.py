from typing import List, Dict, Any
from continuation_token import ContinuationToken, ContinuationContext

class VerifiedContinuationError(Exception):
    """Raised when a continuation context no longer matches reality."""
    pass

class LiveEnvironmentProvider:
    """Mock interface for fetching current ground truth before resuming."""
    def get_current_sha(self) -> str:
        raise NotImplementedError
        
    def get_active_writers(self) -> List[str]:
        raise NotImplementedError
        
    def get_dirty_files(self) -> List[str]:
        raise NotImplementedError
        
    def get_dependencies_hash(self) -> str:
        raise NotImplementedError
        
    def has_required_evidence(self, workkey: str) -> bool:
        raise NotImplementedError
        
    def get_last_checkpoint_state(self, workkey: str) -> str:
        raise NotImplementedError

def verify_continuation_safety(token: ContinuationToken, env: LiveEnvironmentProvider, expected_deps_hash: str):
    """
    Courier MUST call this before resuming any mutation after a restart or session migration.
    Throws VerifiedContinuationError if reality has drifted from the token's context.
    """
    ctx = token.context
    
    # 1. SHA check
    if ctx.sha != env.get_current_sha():
        raise VerifiedContinuationError(f"Codebase SHA drifted. Expected {ctx.sha}, found {env.get_current_sha()}")
        
    # 2. Writer ownership
    writers = env.get_active_writers()
    if writers and ctx.session_id not in writers:
        if len(writers) > 0:
            raise VerifiedContinuationError(f"Writer ownership lost or collision. Active writers: {writers}")
            
    # 3. Dirty files
    dirty = env.get_dirty_files()
    if dirty:
        raise VerifiedContinuationError(f"Cannot safely continue. Dirty files present: {dirty}")
        
    # 4. Dependencies
    if expected_deps_hash != env.get_dependencies_hash():
        raise VerifiedContinuationError(f"Dependencies have changed since this token was generated.")
        
    # 5. Previous checkpoint sync
    actual_checkpoint = env.get_last_checkpoint_state(ctx.workkey)
    if ctx.checkpoint_state != actual_checkpoint:
        raise VerifiedContinuationError(f"Checkpoint state mismatch. Token expected {ctx.checkpoint_state}, but reality is {actual_checkpoint}")
        
    # 6. Required evidence (if we claim to be verified, the evidence better actually exist)
    if ctx.checkpoint_state in ["VERIFIED", "COMMITTED", "PUSHED"]:
        if not env.has_required_evidence(ctx.workkey):
            raise VerifiedContinuationError(f"Missing required evidence for workkey {ctx.workkey} in state {ctx.checkpoint_state}")
            
    return True
