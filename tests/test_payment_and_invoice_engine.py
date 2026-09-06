#!/usr/bin/env python3
"""Test suite for PaymentAndInvoiceEngine."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.payment_and_invoice_engine import PaymentAndInvoiceEngine
from scripts.money_machine_pipeline import OpportunityState


class TestPaymentAndInvoiceEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="payment_test_"))

        # Setup ledger directory and file
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = ledger_dir / "canonical_revenue_ledger.json"
        self.ledger_file.write_text(json.dumps({
            "opportunities": {
                "REV-OPP-B2B-AUTONOMY-AUDIT": {
                    "opportunity_id": "REV-OPP-B2B-AUTONOMY-AUDIT",
                    "title": "B2B Autonomous System Determinism & Crash-Safety Audit Blueprint",
                    "state": OpportunityState.EXPOSURE.value,
                    "evidence_confidence": 0.9,
                    "real_revenue_received_eur": 0.0,
                    "result": "EXPOSURE",
                }
            }
        }))

        self.engine = PaymentAndInvoiceEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_generate_invoice(self):
        """Generates structured Markdown and JSON invoice with unique reference token."""
        res = self.engine.generate_invoice(
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            prospect_id="P-01",
            amount_eur=99.0,
            customer_name="Test Founder",
            customer_email="founder@example.com",
        )
        self.assertEqual(res["status"], "INVOICE_GENERATED")
        self.assertEqual(res["amount_eur"], 99.0)
        self.assertTrue(res["payment_reference"].startswith("REF-INV-P-01-"))

        inv_md = self.test_dir / res["invoice_file"]
        self.assertTrue(inv_md.exists())
        self.assertIn("€99.00 EUR", inv_md.read_text(encoding="utf-8"))

    def test_02_verify_payment_and_advance_revenue(self):
        """Validates real bank funds receipt and advances canonical ledger to REVENUE_RECEIVED."""
        res = self.engine.generate_invoice(
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            prospect_id="P-01",
            amount_eur=99.0,
            customer_name="Test Founder",
            customer_email="founder@example.com",
        )
        invoice_id = res["invoice_id"]

        # Verify payment
        pay_res = self.engine.verify_payment_and_advance_revenue(
            invoice_id=invoice_id,
            bank_tx_reference="SEPA-TX-20260901-DE89370400440532013000",
            amount_received_eur=99.0,
        )
        self.assertEqual(pay_res["status"], "REVENUE_VERIFIED")
        self.assertEqual(pay_res["new_state"], OpportunityState.REVENUE_RECEIVED.value)

        # Check ledger
        ledger_data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
        op = ledger_data["opportunities"]["REV-OPP-B2B-AUTONOMY-AUDIT"]
        self.assertEqual(op["state"], OpportunityState.REVENUE_RECEIVED.value)
        self.assertEqual(op["real_revenue_received_eur"], 99.0)


if __name__ == "__main__":
    unittest.main()
