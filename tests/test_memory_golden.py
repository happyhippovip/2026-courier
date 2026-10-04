import sys
import os
import pytest
from pathlib import Path

scripts_dir = str(Path(__file__).parent.parent / "scripts")
sys.path.insert(0, scripts_dir)

from resolve_project_identity import resolve_project_identity
from checkpoint_backend import CheckpointManager, TaskCheckpoint, CheckpointState
from project_base_backend import ProjectBaseBackend
from readiness_derivation import ReadinessDerivationEngine, ReadinessNodeDefinition, Evidence, ReadinessState
from memory_boundary import MemoryBoundaryAuditor, CategorizedMemoryRecord, PrivacyCategory
from writer_ownership import WriterOwnershipManager
from verified_continuation import LiveEnvironmentProvider, verify_continuation_safety
from continuation_token import ContinuationToken, ContinuationContext

class MockDiskState:
    def __init__(self):
        pass
    def get_raw_safe_state(self): return "sha_golden"
    def get_completed_workkeys(self): return ["WK-PREV"]
    def get_active_writers(self): return ["writer_FRESH"]
    def get_raw_blockers(self): return ["AUTH"]
    def get_recent_recoveries(self): return []
    def get_next_executable_work(self): return ["WK-NEXT"]

class MockEnv(LiveEnvironmentProvider):
    def get_current_sha(self): return "sha_golden"
    def get_active_writers(self): return ["writer_FRESH"]
    def get_dirty_files(self): return []
    def get_dependencies_hash(self): return "dep123"
    def has_required_evidence(self, workkey): return True
    def get_last_checkpoint_state(self, workkey): return "started"

def test_memory_golden_integration(tmp_path):
    workspace = tmp_path / "2026-courier"
    workspace.mkdir()
    
    # 1. Project Resolution
    (workspace / "CHIEF_BRAIN_STATE.md").write_text("PROJECT: 2026-courier\nMODE: COURIER_SYMPHONY")
    identity = resolve_project_identity("courier symphony", str(workspace))
    assert identity["canonical_name"] == "Courier Symphony"
    assert identity["is_courier"] is True
    
    current_sha = "sha_golden"
    
    # 2. Active Writer Ownership (Stale detection)
    writers = WriterOwnershipManager(stale_timeout_seconds=0) 
    writers.acquire_ownership("build", "writer_A", str(workspace), "sha_old", 1000)
    assert writers.acquire_ownership("build", "writer_FRESH", str(workspace), current_sha, 2000) is True
    
    # 3. Checkpoint Backend
    ckpt_dir = workspace / "checkpoints"
    ckpt_manager = CheckpointManager(str(ckpt_dir))
    ckpt = TaskCheckpoint("WK-NEXT", CheckpointState.STARTED, {"some": "ctx"})
    ckpt_manager.save_checkpoint(ckpt)
    recovered_ckpt = ckpt_manager.load_checkpoint("WK-NEXT")
    assert recovered_ckpt.workkey == "WK-NEXT"
    
    # 4. Readiness Derivation (Current state verification)
    readiness_engine = ReadinessDerivationEngine(current_sha, 2000)
    node_def = ReadinessNodeDefinition("node1", ["build_success"], 3600, "windows", [])
    evidence = [Evidence("claim2", "build_success", current_sha, "windows", 1900)]
    assert readiness_engine.derive_status(node_def, evidence, {}) == ReadinessState.READY
    
    # 5. Privacy Boundary (Exporting Handoff safe data)
    auditor = MemoryBoundaryAuditor()
    auditor.add_record(CategorizedMemoryRecord("r1", PrivacyCategory.PUBLIC_PROJECT, "WK-NEXT is ready"))
    auditor.add_record(CategorizedMemoryRecord("r2", PrivacyCategory.SECRET, "token=123"))
    
    safe_export = auditor.filter_for_destination("handoff", PrivacyCategory.PRIVATE_PROJECT)
    assert len(safe_export) == 1
    assert "token" not in safe_export[0].payload
    
    # 6. Verified Continuation
    token = ContinuationToken(
        context=ContinuationContext(
            project="2026-courier",
            workkey="WK-NEXT",
            session_id="writer_FRESH",
            sha="sha_golden",
            checkpoint_state="started"
        )
    )
    env = MockEnv()
    assert verify_continuation_safety(token, env, "dep123") is True
    
    # 7. Project Base (Tracking state)
    disk = MockDiskState()
    
    base = ProjectBaseBackend(disk)
    state = base.get_project_base_state()
    assert "WK-PREV" in state.last_verified_progress
    assert state.what_is_ready_next == ["WK-NEXT"]

    print("GOLDEN TEST PASSED")

