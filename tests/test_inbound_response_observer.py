import pytest
import json
from pathlib import Path
from scripts.inbound_response_observer import InboundResponseObserver, ResponseClassification

def test_classify_message_text():
    observer = InboundResponseObserver()
    
    # Positive interest
    c, conf = observer.classify_message_text("Hello", "We would like to proceed and book a slot.")
    assert c == ResponseClassification.POSITIVE_INTEREST
    assert conf == 0.95
    
    # Bounce
    c, conf = observer.classify_message_text("Delivery status notification", "Failed to deliver")
    assert c == ResponseClassification.BOUNCE
    
    # Price objection
    c, conf = observer.classify_message_text("Re: Offer", "It is too expensive right now")
    assert c == ResponseClassification.PRICE_OBJECTION
    
    # Unknown
    c, conf = observer.classify_message_text("Random", "Just saying hi")
    assert c == ResponseClassification.UNKNOWN

def test_process_inbound_message_positive_interest(tmp_path, monkeypatch):
    # Setup mock experiment
    repo_dir = tmp_path
    exp_dir = repo_dir / "events" / "revenue-opportunities" / "market_intelligence"
    exp_dir.mkdir(parents=True)
    exp_file = exp_dir / "EXP_01.json"
    exp_file.write_text(json.dumps({
        "prospect_alias": "P-01",
        "price_eur": 500.0,
        "target_offering": "TEST-OFFERING"
    }))
    
    # Mock InvoiceGenerator
    class MockInvoiceGenerator:
        @classmethod
        def generate_invoice(cls, experiment_data, customer_email, customer_name):
            return {"invoice_id": "INV-123"}
            
    import scripts.inbound_response_observer as observer_module
    monkeypatch.setattr(observer_module, "InvoiceGenerator", MockInvoiceGenerator)
    
    observer = InboundResponseObserver(repo_dir=repo_dir)
    res = observer.process_inbound_message("EXP_01", "Hello", "Please send the invoice.", "test@test.com")
    
    assert res["classification"] == ResponseClassification.POSITIVE_INTEREST
    assert res["action_taken"] == "INVOICE_GENERATED"
    assert res["invoice_id"] == "INV-123"

def test_process_inbound_message_experiment_not_found(tmp_path):
    observer = InboundResponseObserver(repo_dir=tmp_path)
    res = observer.process_inbound_message("MISSING_EXP", "Hello", "Please send the invoice.", "test@test.com")
    
    assert res["classification"] == ResponseClassification.POSITIVE_INTEREST
    assert res["action_taken"] == "ERROR_EXPERIMENT_NOT_FOUND"

