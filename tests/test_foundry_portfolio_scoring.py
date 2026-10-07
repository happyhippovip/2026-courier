#!/usr/bin/env python3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import unittest
from foundry_portfolio_scoring import run_portfolio_scoring

class TestFoundryPortfolioScoring(unittest.TestCase):
    def test_portfolio_sorting(self):
        candidates = [
            {
                "message_id": "c1", 
                "metrics": {
                    "problem_strength": 5,
                    "wtp_evidence": 0,
                    "build_effort": 8,
                    "compliance_risk": 2,
                    "evidence_confidence": 0.5
                }
            },
            {
                "message_id": "c2", 
                "metrics": {
                    "problem_strength": 9,
                    "wtp_evidence": 8,
                    "build_effort": 2,
                    "compliance_risk": 0,
                    "evidence_confidence": 0.9
                }
            },
            {
                "message_id": "c3",
                "status_label": "KILLED"
            }
        ]
        
        result = run_portfolio_scoring(candidates)
        
        self.assertEqual(result["candidates_scored"], 2)
        portfolio = result["sorted_portfolio"]
        
        # c2 has high wtp, low effort, so it should be first
        self.assertEqual(portfolio[0]["message_id"], "c2")
        self.assertEqual(portfolio[1]["message_id"], "c1")
        
        self.assertGreater(portfolio[0]["portfolio_score"], portfolio[1]["portfolio_score"])

if __name__ == "__main__":
    unittest.main()
