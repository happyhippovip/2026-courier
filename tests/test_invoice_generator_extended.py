import json
from datetime import datetime, timezone
import pytest

from scripts.invoice_generator import InvoiceGenerator

def test_invoice_generator_due_date_calculation(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    doc = InvoiceGenerator.generate_invoice(
        {"prospect_alias": "P-DUE-TEST", "price_eur": 1200.0, "target_offering": "REV-ENTERPRISE"},
        "client@corp.de",
        "Enterprise Corp"
    )
    created = datetime.fromisoformat(doc["created_at"])
    due = datetime.fromisoformat(doc["due_date"])
    diff = due - created
    # Due date should be 7 days after created date
    assert diff.days == 7
    assert doc["currency"] == "EUR"
    assert doc["payment_status"] == "UNCONFIGURED"
    assert doc["destination_verified"] is False
    assert doc["payment_reference"].startswith("REF-INV-P-DUE-TEST-")

def test_invoice_generator_special_characters_handling(tmp_path, monkeypatch):
    monkeypatch.setattr(InvoiceGenerator, "INVOICE_DIR", tmp_path / "invoices")
    doc = InvoiceGenerator.generate_invoice(
        {"prospect_alias": "P-SPECIAL-ÄÖÜ", "price_eur": 750.50},
        "kontakt@münchen-gmbh.de",
        "München Solutions GmbH & Co. KG"
    )
    assert doc["customer_name"] == "München Solutions GmbH & Co. KG"
    assert doc["customer_email"] == "kontakt@münchen-gmbh.de"
    assert doc["amount_eur"] == 750.50
    out_file = tmp_path / "invoices" / f"{doc['invoice_id']}.json"
    assert out_file.exists()
