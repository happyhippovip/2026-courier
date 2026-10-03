from courier_core.ledger_acceptance import LedgerAcceptanceEngine, EvidenceSubmission

def test_acceptance_valid():
    sub = EvidenceSubmission("ev1", 0.99, "v1", True, {"key": "val"})
    assert LedgerAcceptanceEngine.evaluate(sub) is True

def test_acceptance_invalid_signature():
    sub = EvidenceSubmission("ev2", 0.99, "v1", False, {"key": "val"})
    assert LedgerAcceptanceEngine.evaluate(sub) is False

def test_acceptance_low_confidence():
    sub = EvidenceSubmission("ev3", 0.90, "v1", True, {"key": "val"})
    assert LedgerAcceptanceEngine.evaluate(sub) is False
