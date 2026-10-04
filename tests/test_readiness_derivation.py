import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from readiness_derivation import ReadinessDerivationEngine, ReadinessNodeDefinition, Evidence, ReadinessState

def get_node():
    return ReadinessNodeDefinition(
        node_id="installer",
        required_evidence_types=["build_success", "test_success"],
        max_age_seconds=3600,
        required_os="windows",
        dependencies=[]
    )

def test_ready_valid_evidence():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=1000)
    node = get_node()
    
    evidence = [
        Evidence("e1", "build_success", "sha1", "windows", 900),
        Evidence("e2", "test_success", "sha1", "windows", 950)
    ]
    
    assert engine.derive_status(node, evidence, {}) == ReadinessState.READY

def test_missing_evidence():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=1000)
    node = get_node()
    
    # Empty evidence list
    assert engine.derive_status(node, [], {}) == ReadinessState.UNKNOWN

def test_partial_evidence():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=1000)
    node = get_node()
    
    evidence = [
        Evidence("e1", "build_success", "sha1", "windows", 900)
        # Missing test_success
    ]
    
    assert engine.derive_status(node, evidence, {}) == ReadinessState.UNKNOWN

def test_stale_evidence_time():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=5000) # Time far advanced
    node = get_node()
    
    evidence = [
        Evidence("e1", "build_success", "sha1", "windows", 900), # 5000 - 900 = 4100 > 3600
        Evidence("e2", "test_success", "sha1", "windows", 950)
    ]
    
    assert engine.derive_status(node, evidence, {}) == ReadinessState.DEGRADED

def test_wrong_os():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=1000)
    node = get_node()
    
    evidence = [
        Evidence("e1", "build_success", "sha1", "linux", 900), # Wrong OS
        Evidence("e2", "test_success", "sha1", "windows", 950)
    ]
    
    # Because build_success for windows is missing, it will be UNKNOWN
    assert engine.derive_status(node, evidence, {}) == ReadinessState.UNKNOWN

def test_wrong_sha():
    engine = ReadinessDerivationEngine(current_sha="sha_NEW", current_time=1000)
    node = get_node()
    
    evidence = [
        Evidence("e1", "build_success", "sha_OLD", "windows", 900),
        Evidence("e2", "test_success", "sha_OLD", "windows", 950)
    ]
    
    assert engine.derive_status(node, evidence, {}) == ReadinessState.DEGRADED

def test_superseded_evidence():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=1000)
    node = get_node()
    
    evidence = [
        Evidence("e1", "build_success", "sha1", "windows", 900, is_superseded=True), # Superseded!
        Evidence("e2", "test_success", "sha1", "windows", 950)
    ]
    
    assert engine.derive_status(node, evidence, {}) == ReadinessState.DEGRADED

def test_dependency_degraded():
    engine = ReadinessDerivationEngine(current_sha="sha1", current_time=1000)
    node = get_node()
    node.dependencies = ["core_compile"]
    
    evidence = [
        Evidence("e1", "build_success", "sha1", "windows", 900),
        Evidence("e2", "test_success", "sha1", "windows", 950)
    ]
    
    # Valid evidence for this node, BUT dependency is DEGRADED
    deps = {"core_compile": ReadinessState.DEGRADED}
    
    assert engine.derive_status(node, evidence, deps) == ReadinessState.DEGRADED
