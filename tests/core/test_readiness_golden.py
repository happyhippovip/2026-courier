from courier_core.readiness_tree import ReadinessNode
from courier_core.readiness import ReadinessState
from courier_core.golden_receipt import GoldenEvidenceReceipt

def test_readiness_tree_rollup():
    root = ReadinessNode("root", ReadinessState.SHIPPING_READY)
    
    child1 = ReadinessNode("backend", ReadinessState.EVIDENCE_VERIFIED)
    child2 = ReadinessNode("frontend", ReadinessState.IMPLEMENTED)
    
    root.add_child(child1)
    root.add_child(child2)
    
    # Root is ready, but child2 is only implemented. Result should be IMPLEMENTED.
    assert root.compute_state() == ReadinessState.IMPLEMENTED

def test_golden_evidence_receipt():
    receipt = GoldenEvidenceReceipt(
        target_sha="abc1234",
        suite_name="mac-e2e",
        duration_sec=45.2,
        passed=True,
        environment="macos-14"
    )
    
    payload = receipt.to_payload()
    assert payload["type"] == "GOLDEN_RECEIPT"
    assert payload["passed"] is True
    assert payload["target_sha"] == "abc1234"
    assert payload["proof_hash"] is not None
