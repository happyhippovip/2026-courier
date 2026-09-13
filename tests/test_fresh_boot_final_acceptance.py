"""
test_fresh_boot_final_acceptance.py - WEITER 3: Fresh-Boot Final Windows Autonomy Acceptance Unit Test
"""

import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.scripts.run_fresh_boot_final_acceptance import execute_fresh_boot_acceptance


class TestFreshBootFinalAcceptance(unittest.TestCase):
    def test_fresh_boot_acceptance_court(self):
        res = execute_fresh_boot_acceptance()
        self.assertEqual(res["STATUS"], "PASS")
        self.assertEqual(res["EXTERNAL_START_SIGNALS"], 1)
        self.assertEqual(res["EXTERNAL_WEITER_AFTER_START"], 0)
        self.assertGreaterEqual(res["AUTO_TASK_SUCCESSIONS"], 2)
        self.assertEqual(res["REAL_EFFECT_COUNT_B"], 1)
        self.assertEqual(res["DUPLICATE_EFFECTS"], 0)
        self.assertEqual(res["CONFLICTING_WRITERS"], 0)
        self.assertEqual(res["STATE_AUTHORITY_DRIFT"], 0)
        self.assertEqual(res["DISPATCH_CONFLICTS"], 0)
        self.assertEqual(res["CRITICAL_PROOF_DEBT"], 0)


if __name__ == "__main__":
    unittest.main()
