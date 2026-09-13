"""
test_quiescent_queue_absorber.py - Targeted Acceptance Test for Quiescent weiter Absorber
Verifies Section 8:
Same generation + QUIESCENT_EXHAUSTION_CERTIFIED + 100 duplicate 'weiter' inputs produce:
- NEW_TASKS = 0
- NEW_BATCHES = 0
- NEW_DISCOVERY_RUNS = 0
- NEW_WRITERS = 0
- FULL_STATUS_REPORTS = 0
- LOGICAL_STATE_CHANGES = 0
- Response: QUIESCENT_NOOP only.
"""

import os
import sys
import unittest
import tempfile
import shutil

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.quiescent_absorber import QuiescentQueueAbsorber


class TestQuiescentQueueAbsorber(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.watermark_file = os.path.join(self.temp_dir, "quiescent_watermark.json")
        self.db_path = os.path.join(self.temp_dir, "test_cp.db")
        self.absorber = QuiescentQueueAbsorber(
            watermark_file=self.watermark_file,
            db_path=self.db_path,
            workspace_root=self.temp_dir
        )
        self.absorber.set_quiescent_watermark(
            state_generation=87,
            fingerprint="d8fbcd705b001ec6c5bd6fca4bbeb9429040284f4cdd0ac8182f01c165807d2e",
            status="ACTIVE"
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_absorb_100_duplicate_weiter_signals(self):
        """100 duplicate weiter signals produce 0 tasks, 0 batches, 0 discoveries, 0 reports, and only QUIESCENT_NOOP."""
        new_tasks = 0
        new_batches = 0
        new_discovery_runs = 0
        new_writers = 0
        state_changes = 0
        repeated_full_status_reports = 0

        responses = []
        for _ in range(100):
            res = self.absorber.process_signal(signal="weiter", current_state_gen=87)
            self.assertTrue(res["absorbed"])
            self.assertIn(res["classification"], ("DUPLICATE_CONTINUATION_ALREADY_SATISFIED", "QUIESCENT_NO_REAL_GAP"))
            self.assertEqual(res["action"], "QUIESCENT_NOOP")
            self.assertEqual(res["response_text"], "QUIESCENT_NOOP")

            new_tasks += res["new_tasks_created"]
            new_batches += res["new_batches_created"]
            new_discovery_runs += res["new_discovery_runs"]
            new_writers += res["new_writers"]
            state_changes += res["state_changes"]
            repeated_full_status_reports += res["repeated_full_status_reports"]
            responses.append(res["response_text"])

        self.assertEqual(new_tasks, 0)
        self.assertEqual(new_batches, 0)
        self.assertEqual(new_discovery_runs, 0)
        self.assertEqual(new_writers, 0)
        self.assertEqual(state_changes, 0)
        self.assertEqual(repeated_full_status_reports, 0)
        self.assertEqual(len(responses), 100)
        self.assertTrue(all(r == "QUIESCENT_NOOP" for r in responses))

    def test_02_wake_on_new_non_weiter_directive(self):
        """A genuine new directive breaks quiescent absorption."""
        res = self.absorber.process_signal(signal="START_NEW_COMMERCIAL_PILOT", current_state_gen=87)
        self.assertFalse(res["absorbed"])
        self.assertEqual(res["action"], "WAKE_ENGINE")
        self.assertIn("NEW_NON_WEITER_DIRECTIVE", res["reason"])

    def test_03_wake_on_state_generation_change(self):
        """A change in state generation breaks quiescent absorption."""
        res = self.absorber.process_signal(signal="weiter", current_state_gen=88)
        self.assertFalse(res["absorbed"])
        self.assertEqual(res["action"], "WAKE_ENGINE")
        self.assertIn("STATE_GENERATION_CHANGED", res["reason"])


if __name__ == "__main__":
    unittest.main()
