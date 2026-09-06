#!/usr/bin/env python3
"""Test suite for launch_kibey_market_exposure."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.launch_kibey_market_exposure import KibeyMarketExposureLauncher


class TestLaunchKibeyMarketExposure(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="kibey_test_"))
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = ledger_dir / "canonical_revenue_ledger.json"
        self.ledger_file.write_text(json.dumps({
            "opportunities": {
                "REV-OPP-KIBEY-AI-MARKETPLACE": {"state": "OFFER_READY"}
            }
        }))
        self.launcher = KibeyMarketExposureLauncher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_dry_run_validation(self):
        """Verifies dry run generates fingerprint, correlation, and zero capital spend."""
        res = self.launcher.execute_market_exposure(dry_run=True)
        self.assertEqual(res["status"], "DRY_RUN_VALIDATED")
        self.assertEqual(res["prospect_id"], "P-KIBEY-01")
        self.assertEqual(res["capital_spent_eur"], 0.0)
        self.assertTrue(len(res["message_fingerprint"]) > 32)

    def test_02_duplicate_send_protection(self):
        """Verifies duplicate send is blocked when prospect has already been transmitted."""
        # Create tracker with already sent prospect
        tracker_dir = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "kibey_ai_marketplace"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = tracker_dir / "outreach_tracker.json"
        tracker_file.write_text(json.dumps({
            "prospects": [{
                "id": "P-KIBEY-01",
                "sent_at": "2026-09-01T16:40:00+00:00",
                "correlation_id": "CORR-KIBEY01-TEST"
            }]
        }))

        res = self.launcher.execute_market_exposure(dry_run=False)
        self.assertEqual(res["status"], "DUPLICATE_BLOCKED")


if __name__ == "__main__":
    unittest.main()
