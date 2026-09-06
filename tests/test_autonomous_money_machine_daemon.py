#!/usr/bin/env python3
"""Test suite for AutonomousMoneyMachineDaemon."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomous_money_machine_daemon import AutonomousMoneyMachineDaemon


class TestAutonomousMoneyMachineDaemon(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="daemon_test_"))

        # Setup tracker directory
        tracker_dir = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        (tracker_dir / "outreach_tracker.json").write_text(json.dumps({
            "prospects": [{"prospect_id": "P-01", "economic_state": "EXPOSURE", "response_state": "WAITING_FOR_RESPONSE"}]
        }))

        # Setup ledger directory
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        (ledger_dir / "canonical_revenue_ledger.json").write_text(json.dumps({
            "opportunities": {
                "REV-OPP-B2B-AUTONOMY-AUDIT": {
                    "opportunity_id": "REV-OPP-B2B-AUTONOMY-AUDIT",
                    "title": "B2B Autonomous System Determinism & Crash-Safety Audit Blueprint",
                    "state": "EXPOSURE",
                    "economic_class": "CASH_NOW",
                    "time_to_first_eur": "1-3_DAYS",
                    "customer": "AI Founders",
                    "evidence_confidence": 0.9,
                    "result": "EXPOSURE",
                }
            }
        }))

        self.daemon = AutonomousMoneyMachineDaemon(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_run_single_autonomous_cycle(self):
        """Executes full autonomous cycle and proves zero human WEITER and zero copy/paste."""
        res = self.daemon.run_single_autonomous_cycle(dry_run=True)
        self.assertEqual(res["status"], "CYCLE_COMPLETED")
        self.assertFalse(res["human_weiter_required"])
        self.assertEqual(res["human_copy_paste_count"], 0)
        self.assertEqual(res["autonomous_spend_eur"], 0.0)
        self.assertEqual(res["payment_status"]["canonical_state"], "PAYMENT_SETUP_REQUIRED")


if __name__ == "__main__":
    unittest.main()
