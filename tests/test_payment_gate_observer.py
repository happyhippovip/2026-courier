#!/usr/bin/env python3
"""Test suite for PaymentGateObserver."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.payment_gate_observer import PaymentGateObserver


class TestPaymentGateObserver(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="pay_gate_test_"))
        gate_dir = self.test_dir / "events" / "approvals" / "human_fast_gates"
        gate_dir.mkdir(parents=True, exist_ok=True)
        self.gate_file = gate_dir / "gate_payment_destination_config.json"
        self.gate_file.write_text(json.dumps({"status": "AWAITING_HUMAN_ONE_TIME_SETUP"}))

        self.observer = PaymentGateObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_awaiting_authorization(self):
        """Initial check returns AWAITING_ONE_TIME_AUTHORIZATION when no config exists."""
        res = self.observer.check_and_activate()
        self.assertEqual(res["status"], "AWAITING_ONE_TIME_AUTHORIZATION")
        self.assertEqual(res["canonical_state"], "PAYMENT_SETUP_REQUIRED")
        self.assertFalse(res["auto_resumed"])

    def test_02_validate_and_save_stripe_link_auto_resumes(self):
        """Setting Stripe link validates format, saves local config, and auto-resumes."""
        res = self.observer.validate_and_save_config("https://buy.stripe.com/test_link_123")
        self.assertEqual(res["status"], "PAYMENT_DESTINATION_CONFIGURED")
        self.assertEqual(res["active_rail"], "STRIPE_PAYMENT_LINK")
        self.assertEqual(res["canonical_payment_state"], "PAYMENT_READY_HUMAN_RECEIPT_VERIFICATION")
        self.assertTrue(res["auto_resume_triggered"])

        # Check subsequent check_and_activate
        chk = self.observer.check_and_activate()
        self.assertEqual(chk["status"], "PAYMENT_READY_VERIFIED")
        self.assertTrue(chk["auto_resumed"])

    def test_03_validate_and_save_sepa_iban(self):
        """Setting valid IBAN masks sensitive details and configures SEPA rail."""
        res = self.observer.validate_and_save_config("DE89370400440532013000")
        self.assertEqual(res["status"], "PAYMENT_DESTINATION_CONFIGURED")
        self.assertEqual(res["active_rail"], "SEPA_DIRECT_IBAN")
        self.assertEqual(res["canonical_payment_state"], "PAYMENT_READY_HUMAN_RECEIPT_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
