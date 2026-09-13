"""
test_synthetic_customer_conversion.py - Test Suite for TASK-WIN-81:
Automated Synthetic Customer Conversion Rehearsal & E2E Revenue Smoke Trial.
"""

import os
import sys
import json
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PM_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
MF_DIR = os.path.join(PM_DIR, "money_factory")
DIST_ACP_DIR = os.path.join(PM_DIR, "data", "distribution_ready", "agent_control_plane")

if MF_DIR not in sys.path:
    sys.path.insert(0, MF_DIR)
if DIST_ACP_DIR not in sys.path:
    sys.path.insert(0, DIST_ACP_DIR)

from synthetic_conversion_trial import SyntheticCustomerConversionTrial


class TestSyntheticCustomerConversion(unittest.TestCase):

    def setUp(self):
        self.trial = SyntheticCustomerConversionTrial(workspace_dir=WORKSPACE_ROOT)

    def test_01_full_e2e_conversion_cycle_succeeds(self):
        """Test complete 6-stage prospective buyer conversion flow."""
        receipt = self.trial.run_e2e_rehearsal(
            buyer_name="Nova Synthetics LLC",
            buyer_email="billing@nova-synth.invalid",
            buyer_country="DE",
            buyer_vat_id="DE987654321",
            tier="PRO"
        )
        self.assertTrue(receipt["all_stages_complete"], "All 6 funnel stages must complete successfully")
        self.assertEqual(len(receipt["stages_passed"]), 6)
        self.assertEqual(receipt["real_spend_eur"], 0.00, "Spend must remain strictly 0.00 EUR")
        self.assertEqual(receipt["proof_debt"], 0.00, "Proof debt must remain strictly 0.00")
        self.assertTrue(receipt["adapter_verified"], "Drop-in adapter must verify under purchased license")
        self.assertIn("ACP-PRO-", receipt["issued_license_key"])

    def test_02_strict_commercial_invariants_enforced(self):
        """Verify zero external spend, deterministic hashes, and non-empty receipts."""
        receipt = self.trial.run_e2e_rehearsal(
            buyer_name="Zero Spend Labs",
            buyer_email="dev@zero-spend.invalid"
        )
        self.assertEqual(receipt["price_eur"], 19.99)
        self.assertIn("AGENT-CONTROL-PLANE-PRO", receipt["sku"])
        self.assertIsNotNone(receipt["proof_signature"])
        self.assertEqual(len(receipt["proof_signature"]), 64, "SHA-256 proof must be 64 hex characters")

    def test_03_vat_invoice_integration_in_conversion(self):
        """Verify EU B2B reverse-charge is correctly calculated and referenced in trial."""
        receipt = self.trial.run_e2e_rehearsal(
            buyer_name="Paris Autonomous SAS",
            buyer_email="finance@paris-auto.invalid",
            buyer_country="FR",
            buyer_vat_id="FR12345678901"
        )
        self.assertIsNotNone(receipt["invoice_number"])
        self.assertTrue(receipt["invoice_number"].startswith("INV-"))

    def test_04_binary_zip_integrity_matches_distribution_manifest(self):
        """Verify distribution zip SHA-256 matches the manifest expectations."""
        manifest_path = os.path.join(DIST_ACP_DIR, "DISTRIBUTION_MANIFEST_PRO.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        expected_sha = manifest["zip_sha256"]

        receipt = self.trial.run_e2e_rehearsal()
        self.assertEqual(receipt["binary_verified_sha256"], expected_sha)

    def test_05_durable_ledger_append_integrity(self):
        """Verify synthetic trial appends tamper-evident audit record to disk ledger."""
        self.trial.run_e2e_rehearsal()
        ledger_path = os.path.join(PM_DIR, "data", "commercial", "synthetic_conversion_ledger.json")
        self.assertTrue(os.path.exists(ledger_path), "Ledger file must exist on disk")

        with open(ledger_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        self.assertIsInstance(entries, list)
        self.assertGreaterEqual(len(entries), 1)

        latest = entries[-1]
        self.assertIn("trial_id", latest)
        self.assertIn("proof_signature", latest)
        self.assertIn("issued_license_key", latest)
        self.assertIn("rehearsal_timestamp_utc", latest)
if __name__ == "__main__":
    unittest.main()