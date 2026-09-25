import pytest
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import invoice_generator

@pytest.fixture
def mock_invoice_dir(tmp_path):
    orig = invoice_generator.InvoiceGenerator.INVOICE_DIR
    invoice_generator.InvoiceGenerator.INVOICE_DIR = tmp_path / "invoices"
    yield invoice_generator.InvoiceGenerator.INVOICE_DIR
    invoice_generator.InvoiceGenerator.INVOICE_DIR = orig

def test_generate_invoice_success(mock_invoice_dir):
    experiment_data = {
        "prospect_alias": "P-TEST-123",
        "price_eur": 150.50,
        "target_offering": "REV-TEST-OFFERING"
    }
    
    # First invoice
    result1 = invoice_generator.InvoiceGenerator.generate_invoice(experiment_data, "test@example.com", "John Doe")
    assert result1["prospect_id"] == "P-TEST-123"
    assert result1["amount_eur"] == 150.50
    assert result1["customer_name"] == "John Doe"
    assert "INV-P-TEST-123" in result1["invoice_id"]
    assert result1["invoice_id"].endswith("01")
    
    # Check if saved to disk
    file_path = mock_invoice_dir / f"{result1['invoice_id']}.json"
    assert file_path.exists()
    disk_data = json.loads(file_path.read_text())
    assert disk_data["invoice_id"] == result1["invoice_id"]
    
    # Second invoice (sequence should increment)
    result2 = invoice_generator.InvoiceGenerator.generate_invoice(experiment_data, "test@example.com", "John Doe")
    assert result2["invoice_id"].endswith("02")

def test_generate_invoice_defaults(mock_invoice_dir):
    experiment_data = {} # Empty
    
    result = invoice_generator.InvoiceGenerator.generate_invoice(experiment_data, "test@example.com", "John Doe")
    assert result["prospect_id"] == "UNKNOWN-PROSPECT"
    assert result["amount_eur"] == 0.0
    assert result["opportunity_id"] == "UNKNOWN-OFFERING"

