import json
import sys
from pathlib import Path
import pytest

from scripts.invoice_generator import InvoiceGenerator, main


def test_invoice_generator_dry_run():
    exp = {
        "prospect_alias": "P-TEST-01",
        "price_eur": 149.0,
        "target_offering": "REV-AUDIT-V1",
    }
    doc = InvoiceGenerator.generate_invoice(
        exp,
        customer_email="buyer@test.corp",
        customer_name="Buyer Alice",
        dry_run=True,
    )
    assert doc["prospect_id"] == "P-TEST-01"
    assert doc["amount_eur"] == 149.0
    assert doc["currency"] == "EUR"
    assert "INV-P-TEST-01-" in doc["invoice_id"]
    assert "REF-" in doc["payment_reference"]


def test_invoice_generator_file_creation(tmp_path: Path):
    exp = {
        "prospect_alias": "P-FILE-02",
        "price_eur": 250.0,
        "target_offering": "REV-OFFERING-FULL",
    }
    doc1 = InvoiceGenerator.generate_invoice(
        exp,
        customer_email="corp@test.org",
        customer_name="Corp Bob",
        repo_dir=tmp_path,
        quiet=True,
    )
    inv_dir = tmp_path / "events" / "invoices"
    assert inv_dir.is_dir()

    inv_path1 = inv_dir / f"{doc1['invoice_id']}.json"
    assert inv_path1.is_file()
    saved = json.loads(inv_path1.read_text(encoding="utf-8"))
    assert saved["invoice_id"] == doc1["invoice_id"]
    assert saved["amount_eur"] == 250.0

    # Second invoice for same prospect should increment sequence
    doc2 = InvoiceGenerator.generate_invoice(
        exp,
        customer_email="corp@test.org",
        customer_name="Corp Bob",
        repo_dir=tmp_path,
        quiet=True,
    )
    assert doc1["invoice_id"] != doc2["invoice_id"]
    assert doc2["invoice_id"].endswith("-02")


def test_invoice_generator_cli(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "invoice_generator.py",
            "--prospect-alias", "P-CLI",
            "--price-eur", "79.5",
            "--customer-email", "cli@user.io",
            "--customer-name", "CLI User",
            "--repo-dir", str(tmp_path),
            "--dry-run",
            "--json",
        ],
    )
    main()
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["prospect_id"] == "P-CLI"
    assert res["amount_eur"] == 79.5
