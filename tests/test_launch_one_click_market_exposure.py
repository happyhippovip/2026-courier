#!/usr/bin/env python3
"""Test suite for OneClickMarketExposureLauncher."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.launch_one_click_market_exposure import OneClickMarketExposureLauncher


class TestOneClickMarketExposureLauncher(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="launcher_test_"))
        tracker_dir = self.test_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit"
        tracker_dir.mkdir(parents=True, exist_ok=True)
        tracker_file = tracker_dir / "outreach_tracker.json"
        tracker_file.write_text(json.dumps({
            "prospects": [
                {
                    "prospect_id": "P-01",
                    "target_type": "AI Coding Agent Founder",
                    "channel": "LINKEDIN_DM",
                    "personalized_message": "Test offer for €99 AI Agent Reliability Check.",
                }
            ]
        }))

        self.launcher = OneClickMarketExposureLauncher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_prepare_one_click_url(self):
        """Prepares pre-populated URL with URL-encoded parameters and zero human copy/paste."""
        res = self.launcher.prepare_one_click_url("P-01")
        self.assertEqual(res["status"], "PREPARED")
        self.assertEqual(res["human_copy_paste_required"], 0)
        self.assertIn("mailto:", res["mailto_url"])
        self.assertIn("Test%20offer%20for%20%E2%82%AC99", res["mailto_url"])


if __name__ == "__main__":
    unittest.main()
