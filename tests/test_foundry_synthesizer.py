#!/usr/bin/env python3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import unittest
from foundry_synthesizer import run_synthesizer, detect_contradictions

class TestFoundrySynthesizer(unittest.TestCase):
    def test_synthesize_candidates(self):
        thoughts = [
            {"message_id": "msg-1", "kind": "IDEA", "summary": "System should always use cache."},
            {"message_id": "msg-2", "kind": "IDEA", "summary": "System must never use cache to avoid stale data."},
            {"message_id": "msg-3", "kind": "TASK", "summary": "Add redis integration."}
        ]
        
        result = run_synthesizer(thoughts)
        
        # Check clustering
        self.assertIn("IDEA", result["clusters"])
        self.assertIn("TASK", result["clusters"])
        self.assertEqual(len(result["clusters"]["IDEA"]), 2)
        
        # Check synthesis candidate (only groups with >1 item)
        self.assertEqual(len(result["synthesized_candidates"]), 1)
        candidate = result["synthesized_candidates"][0]
        self.assertEqual(candidate["kind"], "SYNTHESIS")
        self.assertEqual(candidate["source_thought_ids"], ["msg-1", "msg-2"])
        
        # Check contradictions
        self.assertEqual(len(candidate["contradictions"]), 1)
        self.assertEqual(candidate["contradictions"][0]["source_a"], "msg-1")
        self.assertEqual(candidate["contradictions"][0]["source_b"], "msg-2")
        self.assertEqual(result["contradiction_count"], 1)
        
        # Check relationship graph
        self.assertEqual(len(result["relationship_graph"]), 2)
        edges = [(e["from"], e["to"], e["type"]) for e in result["relationship_graph"]]
        self.assertIn(("msg-1", candidate["message_id"], "SYNTHESIZED_INTO"), edges)
        self.assertIn(("msg-2", candidate["message_id"], "SYNTHESIZED_INTO"), edges)

if __name__ == "__main__":
    unittest.main()
