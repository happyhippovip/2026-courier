#!/usr/bin/env python3
"""Test suite for MarketExposureRecorder."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.record_market_exposure import MarketExposureRecorder


class TestMarketExposureRecorder(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="exposure_test_"))
        tracker_dir = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = tracker_dir / "outreach_tracker.json"
        tracker_file.write_text(json.dumps({
            "batch_id": "TEST-BATCH-01",
            "prospects": [
                {"prospect_id": "P-01", "economic_state": "PREPARED_FOR_DISPATCH", "sent_at": None},
                {"prospect_id": "P-02", "economic_state": "PREPARED_FOR_DISPATCH", "sent_at": None},
            ]
        }))

        self.recorder = MarketExposureRecorder(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_record_single_exposure_updates_state(self):
        """Recording single exposure updates prospect state and advances canonical state to EXPOSURE."""
        res = self.recorder.record_exposure("P-01", channel="LINKEDIN_DM", notes="Sent test message")
        self.assertEqual(res["status"], "EXPOSURE_RECORDED")
        self.assertEqual(res["total_real_exposures"], 1)

        tracker = json.loads(self.recorder.tracker_file.read_text(encoding="utf-8"))
        p1 = next(p for p in tracker["prospects"] if p["prospect_id"] == "P-01")
        self.assertIsNotNone(p1["sent_at"])
        self.assertEqual(p1["economic_state"], "EXPOSURE")

    def test_02_record_response_updates_economic_conversation_state(self):
        """Recording incoming response transitions state to QUALIFIED_CONVERSATION or PAYMENT_DISCUSSION."""
        self.recorder.record_exposure("P-01", channel="LINKEDIN_DM")
        res = self.recorder.record_response(
            "P-01",
            response_text="Interested in the €99 check for our worker",
            problem_signal=True,
            scope_requested=True,
            payment_discussed=True,
        )
        self.assertEqual(res["status"], "RESPONSE_RECORDED")
        self.assertEqual(res["economic_state"], "PAYMENT_DISCUSSION")


if __name__ == "__main__":
    unittest.main()
