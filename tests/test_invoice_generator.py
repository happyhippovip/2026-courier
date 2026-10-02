import json
import runpy
from pathlib import Path
from scripts.invoice_generator import InvoiceGenerator

def test_invoice_generator_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    InvoiceGenerator.setup()
    assert (tmp_path / "invoices").exists()
    assert (tmp_path / "invoices").is_dir()

def test_generate_invoice_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    
    doc = InvoiceGenerator.generate_invoice({}, "test@example.com", "John Doe")
    
    assert doc["customer_email"] == "test@example.com"
    assert doc["customer_name"] == "John Doe"
    assert doc["prospect_id"] == "UNKNOWN-PROSPECT"
    assert doc["amount_eur"] == 0.0
    assert doc["opportunity_id"] == "UNKNOWN-OFFERING"
    assert "INV-UNKNOWN-PROSPECT-" in doc["invoice_id"]
    
    out_file = tmp_path / "invoices" / f"{doc['invoice_id']}.json"
    assert out_file.exists()
    with open(out_file, "r") as f:
        saved_doc = json.load(f)
    assert saved_doc == doc

def test_generate_invoice_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    
    exp_data = {
        "prospect_alias": "P-TEST-01",
        "price_eur": 500.0,
        "target_offering": "REV-TEST-OFFERING"
    }
    
    doc1 = InvoiceGenerator.generate_invoice(exp_data, "1@example.com", "Test1")
    doc2 = InvoiceGenerator.generate_invoice(exp_data, "2@example.com", "Test2")
    
    assert doc1["invoice_id"].endswith("-01")
    assert doc2["invoice_id"].endswith("-02")
    assert doc1["amount_eur"] == 500.0
    assert doc1["opportunity_id"] == "REV-TEST-OFFERING"

import subprocess
import sys

def test_main_execution(tmp_path):
    # Run the module to cover the __main__ block
    result = subprocess.run([sys.executable, "-m", "scripts.invoice_generator"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Generated Invoice: " in result.stdout
