"""
test_campaign_manager.py - Unit tests for ContinuationCampaignManager
Verifies:
1. Multi-signal budget absorption: 100 raw signals absorbed into 1 logical intent.
2. Signal coalescing: Incoming duplicate weiter signals result in COALESCED_NOOP.
3. Persistence: Campaign state persists to SQLite and JSON.
4. Progress recording and campaign closure.
"""

import os
import sys
import unittest
import tempfile
import json

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.control_plane import ControlPlane
from courier.chief.campaign_manager import ContinuationCampaignManager


class TestContinuationCampaignManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cp.db")
        self.state_file = os.path.join(self.temp_dir, "test_campaign.json")
        self.cp = ControlPlane(db_path=self.db_path)
        self.mgr = ContinuationCampaignManager(cp=self.cp, state_file=self.state_file)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_campaign_initialization(self):
        state = self.mgr.start_or_get_campaign("CAMP-TEST-01", raw_budget=100)
        self.assertTrue(state["active"])
        self.assertEqual(state["raw_weiter_observed"], 100)
        self.assertEqual(state["weiter_absorbed"], 99)
        self.assertEqual(state["logical_continuation_intents"], 1)
        self.assertEqual(state["duplicate_signals_suppressed"], 99)
        self.assertTrue(os.path.exists(self.state_file))

    def test_02_signal_coalescing(self):
        self.mgr.start_or_get_campaign("CAMP-TEST-02", raw_budget=50)
        res = self.mgr.consume_signal("weiter", "CAMP-TEST-02")
        self.assertTrue(res["coalesced"])
        self.assertEqual(res["action"], "COALESCED_NOOP")
        state = res["state"]
        self.assertEqual(state["raw_weiter_observed"], 51)
        self.assertEqual(state["weiter_absorbed"], 50)
        self.assertEqual(state["duplicate_signals_suppressed"], 50)

    def test_03_record_progress_and_close(self):
        self.mgr.start_or_get_campaign("CAMP-TEST-03", raw_budget=10)
        self.mgr.record_progress("CAMP-TEST-03", tasks_executed=3, tasks_verified=3)
        st = self.mgr.get_campaign_state("CAMP-TEST-03")
        self.assertEqual(st["tasks_executed"], 3)
        self.assertEqual(st["tasks_verified"], 3)

        self.mgr.close_campaign("CAMP-TEST-03", "COMPLETE_SAFE_WORK_EXHAUSTED")
        closed = self.mgr.get_campaign_state("CAMP-TEST-03")
        self.assertFalse(closed["active"])
        self.assertEqual(closed["status"], "COMPLETE_SAFE_WORK_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
