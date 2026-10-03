from courier_core.snapshot_identity import IdentityBoundSnapshot
from courier_core.snapshot_level_0 import SnapshotLevel0
from courier_core.screenshot_truth import ScreenshotObservation, TruthBoundary

def test_identity_binding():
    l0 = SnapshotLevel0("macos", [1], 1024.0, [80], 123.45)
    bound = IdentityBoundSnapshot("WK-11", "sess-1", 1, l0)
    
    assert bound.verify_binding("WK-11", "sess-1") is True
    assert bound.verify_binding("WK-11", "sess-2") is False

def test_screenshot_truth_boundary():
    # A perfect screenshot claiming the task is done/green
    pixels = ScreenshotObservation("hashA", "GREEN", 0.99)
    
    # Fails if system evidence (logs, receipts) is not verified
    assert TruthBoundary.evaluate_readiness(pixels, system_evidence_verified=False) is False
    
    # Passes if system evidence correlates with the pixels
    assert TruthBoundary.evaluate_readiness(pixels, system_evidence_verified=True) is True
