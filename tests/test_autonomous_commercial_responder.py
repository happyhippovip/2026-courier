#!/usr/bin/env python3
"""Test suite for AutonomousCommercialResponder."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_commercial_responder import AutonomousCommercialResponder
from scripts.money_machine_pipeline import OpportunityState


class TestAutonomousCommercialResponder(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="responder_test_"))

        # Setup ledger directory and file
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = ledger_dir / "canonical_revenue_ledger.json"
        self.ledger_file.write_text(json.dumps({
            "opportunities": {
                "REV-OPP-B2B-AUTONOMY-AUDIT": {
                    "opportunity_id": "REV-OPP-B2B-AUTONOMY-AUDIT",
                    "title": "B2B Autonomous System Determinism & Crash-Safety Audit Blueprint",
                    "state": OpportunityState.RESPONSE.value,
                    "evidence_confidence": 0.9,
                    "result": "RESPONSE",
                }
            }
        }))

        self.responder = AutonomousCommercialResponder(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_handle_positive_interest(self):
        """Generates invoice, reference token, pre-approved reply copy, and advances to PAYMENT_DISCUSSION."""
        res = self.responder.handle_positive_interest(
            prospect_id="P-01",
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            customer_name="Test Founder",
            customer_email="founder@example.com",
        )
        self.assertEqual(res["status"], "QUALIFIED_PAYMENT_DISCUSSION_STAGED")
        self.assertEqual(res["new_state"], OpportunityState.PAYMENT_DISCUSSION.value)
        self.assertEqual(res["amount_eur"], 99.0)
        self.assertIn("€99.00 EUR", res["reply_copy"])
        self.assertIn("zero production secrets", res["reply_copy"])

        # Check ledger
        ledger_data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
        op = ledger_data["opportunities"]["REV-OPP-B2B-AUTONOMY-AUDIT"]
        self.assertEqual(op["state"], OpportunityState.PAYMENT_DISCUSSION.value)


if __name__ == "__main__":
    unittest.main()
