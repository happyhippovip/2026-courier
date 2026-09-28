import pytest
import json
from pathlib import Path
from scripts.invoice_generator import InvoiceGenerator

def test_generate_invoice(tmp_path, monkeypatch):
    # Override INVOICE_DIR
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path)
    
    experiment_data = {
        "prospect_alias": "P-TEST-01",
        "price_eur": 150.0,
        "target_offering": "TEST-OFFERING-123"
    }
    
    doc = InvoiceGenerator.generate_invoice(experiment_data, "test@customer.com", "Test Corp")
    
    assert doc["amount_eur"] == 150.0
    assert doc["prospect_id"] == "P-TEST-01"
    assert doc["opportunity_id"] == "TEST-OFFERING-123"
    assert doc["customer_email"] == "test@customer.com"
    assert doc["customer_name"] == "Test Corp"
    assert "payment_reference" in doc
    
    invoice_id = doc["invoice_id"]
    out_file = tmp_path / f"{invoice_id}.json"
    assert out_file.exists()
    
    with open(out_file, "r") as f:
        saved_doc = json.load(f)
        
    assert saved_doc == doc

def test_generate_invoice_missing_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path)
    
    # Empty data should use defaults
    doc = InvoiceGenerator.generate_invoice({}, "test@customer.com", "Test Corp")
    
    assert doc["prospect_id"] == "UNKNOWN-PROSPECT"
    assert doc["amount_eur"] == 0.0
    assert doc["opportunity_id"] == "UNKNOWN-OFFERING"
