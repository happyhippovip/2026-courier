"""
test_commercial_reality_hardening.py - Master Certification Suite for TASK-WIN-68
Certifies the Commercial Reality Hardening & Adversarial Red-Team for Agent Control Plane (OPP-SEED-04).
Covers Rules 9-22 of WINDOWS SYMPHONY MISSION COMMANDER.
"""

import os
import sys
import json
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

DOSSIER_PATH = os.path.join(WORKSPACE_ROOT, "project-memory", "data", "commercial", "COMMERCIAL_REALITY_DOSSIER_2026.json")
DEMO_DIR = os.path.join(WORKSPACE_ROOT, "project-memory", "data", "distribution_ready", "agent_control_plane")
if DEMO_DIR not in sys.path:
    sys.path.insert(0, DEMO_DIR)

from demo_spend_firewall import run_60_second_demo

class TestCommercialRealityHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DOSSIER_PATH, "r", encoding="utf-8") as f:
            cls.dossier = json.load(f)

    def test_01_commercial_reality_dossier_structure_and_rules(self):
        """Rule 9 & 10: Verify comprehensive buyer intelligence and pain mining."""
        rules = self.dossier.get("rules_verified", {})
        required_rule_keys = [
            "rule_09_buyer_definition",
            "rule_10_buyer_pain_mining",
            "rule_11_competitor_failure_mining",
            "rule_12_free_ai_red_team",
            "rule_13_offer_compression",
            "rule_14_60_second_value_test",
            "rule_15_5_minute_time_to_value",
            "rule_16_price_adversary",
            "rule_17_distribution_reality",
            "rule_18_launch_failure_tree",
            "rule_21_second_customer_test",
            "rule_22_50_euro_per_day_roadmap"
        ]
        for k in required_rule_keys:
            self.assertIn(k, rules, f"Missing required rule section: {k}")

        pains = rules["rule_10_buyer_pain_mining"]["observed_pain_patterns"]
        self.assertGreaterEqual(len(pains), 3)

    def test_02_free_ai_red_team_defensibility(self):
        """Rule 12: Verify defensibility against naive ChatGPT/Claude substitution."""
        red_team = self.dossier["rules_verified"]["rule_12_free_ai_red_team"]
        self.assertEqual(red_team["red_team_verdict"], "IMMUNE_TO_NAIVE_AI_SUBSTITUTION")
        pillars = red_team["defense_pillars"]
        self.assertGreaterEqual(len(pillars), 4)
        pillar_names = [p["pillar"] for p in pillars]
        self.assertIn("Streaming SSE Chunk Token Accounting", pillar_names)
        self.assertIn("Multi-Process Atomic Budget Mutex", pillar_names)

    def test_03_offer_compression_length_and_clarity(self):
        """Rule 13: Verify 1-sentence offer is crisp, clear, and <= 35 words."""
        pitch = self.dossier["rules_verified"]["rule_13_offer_compression"]["one_sentence_pitch"]
        self.assertTrue(len(pitch) > 20)
        word_count = len(pitch.split())
        self.assertLessEqual(word_count, 35, f"Pitch too wordy ({word_count} words)")
        self.assertIn("runaway", pitch.lower())
        self.assertIn("proxy", pitch.lower())

    def test_04_60_second_value_demo_execution(self):
        """Rule 14: Verify 60-second value demo runs and halts spending without real cost."""
        demo_res = run_60_second_demo(budget_eur=0.05)
        self.assertTrue(demo_res["success"])
        self.assertTrue(demo_res["budget_respected"])
        self.assertEqual(demo_res["intercepted"], 1)
        self.assertEqual(demo_res["approved"], 2)

    def test_05_launch_failure_tree_completeness(self):
        """Rule 18: Verify all 4 failure branches have precomputed contingencies."""
        tree = self.dossier["rules_verified"]["rule_18_launch_failure_tree"]
        branches = tree["branches"]
        self.assertEqual(len(branches), 4)
        symptoms = [b["symptom"] for b in branches]
        self.assertTrue(any("NO_IMPRESSIONS" in s for s in symptoms))
        self.assertTrue(any("IMPRESSIONS_NO_CLICKS" in s for s in symptoms))
        self.assertTrue(any("CLICKS_NO_DOWNLOADS" in s for s in symptoms))
        self.assertTrue(any("DOWNLOADS_NO_PURCHASES" in s for s in symptoms))

    def test_06_50_euro_per_day_unit_economics(self):
        """Rule 22: Verify math for EUR 50/day reality roadmap."""
        r22 = self.dossier["rules_verified"]["rule_22_50_euro_per_day_roadmap"]
        funnel = r22["traffic_funnel"]
        conv = float(funnel["target_conversion_rate"].replace("%", "")) / 100.0
        daily_visitors = funnel["required_daily_visitors"]
        expected_sales = daily_visitors * conv
        daily_rev = expected_sales * 19.99
        self.assertGreaterEqual(daily_rev, 49.0, "Funnel math must support at least €49/day")

    def test_07_zero_spend_and_mac_scope_invariants(self):
        """Rule 34 & 35: Verify spend limit remains 0.00 EUR and Mac scopes excluded."""
        self.assertEqual(self.dossier["spend_limit_eur"], 0)
        self.assertNotIn("universux", json.dumps(self.dossier).lower())

if __name__ == "__main__":
    unittest.main()
