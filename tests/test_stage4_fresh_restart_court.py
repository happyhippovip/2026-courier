"""
test_stage4_fresh_restart_court.py - Unit test wrapper for Stage 4 Fresh Restart Court
"""

import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.scripts.run_stage4_fresh_restart_court import run_fresh_restart_court


class TestStage4FreshRestartCourt(unittest.TestCase):
    def test_fresh_restart_and_exactly_once(self):
        res = run_fresh_restart_court()
        self.assertEqual(res.get("TASK_B_REAL_EFFECT_COUNT"), 1)
        self.assertEqual(res.get("TASK_B_STATUS"), "COMPLETED")
        self.assertEqual(res.get("TASK_C_STATUS"), "COMPLETED")
        self.assertEqual(res.get("FINAL_CHECKPOINT_TASK"), "TASK-COURT-C")
        self.assertEqual(res.get("STAGE_4_FRESH_RESTART_COURT"), "PASS")


if __name__ == "__main__":
    unittest.main()
