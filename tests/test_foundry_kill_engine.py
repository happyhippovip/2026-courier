#!/usr/bin/env python3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import unittest
from foundry_kill_engine import run_kill_engine

class TestFoundryKillEngine(unittest.TestCase):
    def test_kill_weak_candidates(self):
        candidates = [
            {"message_id": "c1", "summary": "Build a strong caching layer.", "status_label": "IDEA"},
            {"message_id": "c2", "summary": "This could be useful for everyone.", "status_label": "IDEA"},
            {"message_id": "c3", "summary": "Process HIPAA and GDPR medical records.", "status_label": "IDEA"},
            {"message_id": "c4", "summary": "Use a manual review concierge process.", "status_label": "IDEA"}
        ]
        
        result = run_kill_engine(candidates)
        
        self.assertEqual(result["candidates_evaluated"], 4)
        self.assertEqual(len(result["survivors"]), 1)
        self.assertEqual(result["survivors"][0]["message_id"], "c1")
        
        self.assertEqual(len(result["killed"]), 3)
        killed_ids = [c["message_id"] for c in result["killed"]]
        self.assertIn("c2", killed_ids)
        self.assertIn("c3", killed_ids)
        self.assertIn("c4", killed_ids)
        
        # Verify specific kill reasons
        c3_kill = next(c for c in result["killed"] if c["message_id"] == "c3")
        self.assertEqual(c3_kill["status_label"], "KILLED")
        self.assertTrue(any("regulatory_burden" in r["reason"] for r in c3_kill["kill_reasons"]))

if __name__ == "__main__":
    unittest.main()
