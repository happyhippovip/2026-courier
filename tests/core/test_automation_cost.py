from courier_core.automation_receipt import AutomationReceipt
from courier_core.cost_ledger import CostLedger

def test_automation_receipt_verification():
    receipt = AutomationReceipt(
        transaction_id="tx99",
        target_system="github",
        planned_steps=["auth", "push"],
        executed_steps=["auth", "push"],
        verification_success=True,
        evidence_refs=["hash:abc"]
    )
    assert receipt.is_complete_and_verified() is True
    
    # Missing execution
    receipt.executed_steps = ["auth"]
    assert receipt.is_complete_and_verified() is False

def test_cost_ledger():
    ledger = CostLedger()
    ledger.record_cost("MAC-14", "tokens", 5000, 0.05)
    ledger.record_cost("MAC-14", "compute", 10, 0.02)
    ledger.record_cost("MAC-15", "tokens", 1000, 0.01)
    
    assert ledger.get_total_for_workkey("MAC-14") == 0.07
    assert ledger.get_total_for_workkey("MAC-15") == 0.01
    assert ledger.get_total_project_cost() == 0.08
