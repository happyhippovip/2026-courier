#!/usr/bin/env python3
"""Test suite for ContentMarketingExposureDispatcher."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.launch_content_marketing_exposure import ContentMarketingExposureDispatcher
from scripts.money_machine_pipeline import OpportunityState


class TestContentMarketingExposureDispatcher(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="content_exp_test_"))
        prospects_dir = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "content_to_marketing_asset"
        prospects_dir.mkdir(parents=True, exist_ok=True)
        self.prospects_file = prospects_dir / "prospects_content_marketing.json"
        self.prospects_file.write_text(json.dumps({
            "prospects": [{"prospect_id": "CP-01", "economic_state": "DISCOVERED", "sent_at": None}]
        }))

        # Setup ledger directory and file
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = ledger_dir / "canonical_revenue_ledger.json"
        self.ledger_file.write_text(json.dumps({
            "opportunities": {
                "REV-OPP-CONTENT-TO-MARKETING-ASSET": {
                    "opportunity_id": "REV-OPP-CONTENT-TO-MARKETING-ASSET",
                    "title": "Raw Content to Finished Marketing Asset Fast-Turnaround Service",
                    "state": OpportunityState.MARKET_TEST_READY.value,
                    "evidence_confidence": 0.85,
                    "result": "MARKET_TEST_READY",
                }
            }
        }))

        self.dispatcher = ContentMarketingExposureDispatcher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_launch_exposure_cp01(self):
        """Prepares pre-populated mailto URL for CP-01 with zero human copy/paste."""
        res = self.dispatcher.launch_exposure_cp01()
        self.assertEqual(res["status"], "COMPOSE_LAUNCHED")
        self.assertEqual(res["human_copy_paste_count"], 0)
        self.assertIn("mailto:", res["mailto_url"])
        self.assertIn("Raw%20Technical%20Notes", res["mailto_url"])

    def test_02_execute_cp01_send_dry_run_and_duplicate_guard(self):
        """Executes controlled simulated CP-01 send and verifies duplicate send fencing."""
        res1 = self.dispatcher.execute_cp01_send(dry_run=True)
        self.assertEqual(res1["status"], "EXPOSURE_TRANSMITTED")
        self.assertEqual(res1["prospect_id"], "CP-01")
        self.assertEqual(res1["opportunity_id"], "REV-OPP-CONTENT-TO-MARKETING-ASSET")

        # Second attempt must be blocked
        res2 = self.dispatcher.execute_cp01_send(dry_run=True)
        self.assertEqual(res2["status"], "BLOCKED_DUPLICATE_SEND")


if __name__ == "__main__":
    unittest.main()
