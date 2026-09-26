"""Tests for invoice_generator.py

Covers:
  - Generation logic and deterministic IDs
"""

import json
from pathlib import Path
import pytest
import sys
from unittest.mock import patch, MagicMock

REPO = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))

from invoice_generator import InvoiceGenerator


def test_generate_invoice_creates_file(tmp_path):
    # Patch the INVOICE_DIR so we don't write to the real repo
    InvoiceGenerator.INVOICE_DIR = tmp_path / "invoices"

    experiment = {
        "prospect_alias": "P-TEST-01",
        "price_eur": 1500.0,
        "target_offering": "TEST-OFFERING"
    }

    doc = InvoiceGenerator.generate_invoice(experiment, "test@example.com", "Test Customer")

    assert doc["prospect_id"] == "P-TEST-01"
    assert doc["amount_eur"] == 1500.0
    assert doc["customer_email"] == "test@example.com"
    assert doc["artifact_status"] == "DRAFT_SIMULATION"
    assert "INV-P-TEST-01-" in doc["invoice_id"]

    # Verify file was written
    out_file = tmp_path / "invoices" / f"{doc['invoice_id']}.json"
    assert out_file.exists()

    with open(out_file, "r") as f:
        saved_doc = json.load(f)
        assert saved_doc == doc


def test_generate_invoice_increments_sequence(tmp_path):
    InvoiceGenerator.INVOICE_DIR = tmp_path / "invoices"

    experiment = {"prospect_alias": "P-TEST-SEQ", "price_eur": 100.0}

    doc1 = InvoiceGenerator.generate_invoice(experiment, "test@example.com", "Test")
    doc2 = InvoiceGenerator.generate_invoice(experiment, "test@example.com", "Test")

    assert doc1["invoice_id"] != doc2["invoice_id"]
    assert doc1["invoice_id"].endswith("-01")
    assert doc2["invoice_id"].endswith("-02")
