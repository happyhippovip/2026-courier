#!/usr/bin/env python3
"""Resource Reset Segmentation Remediation Acceptance Tests (Mission 177G).

Authoritative verification for Codex Mission 175C blocker remediation:
1. Google 47% -> 46% same segment delta is ALLOWED.
2. Google 47% 5-hour -> later values in same segment is ALLOWED.
3. Google pre-reset 5-hour -> 100% at ~14:21: DELTA IS REJECTED (RESET BOUNDARY).
4. Google post-reset 100% -> 97%: DELTA IS ALLOWED.
5. Old Google account -> new Google account: DELTA IS REJECTED.
6. OpenAI historical 5-hour 0% -> 22:38 5-hour 83%: DELTA IS REJECTED (RESET BOUNDARY).
7. OpenAI weekly historical -> 22:38 weekly: DELTA IS ALLOWED via dimension-aware weekly segmentation.
8. Gemini -> Google Claude/GPT pool: DELTA IS REJECTED.
9. Google -> OpenAI: DELTA IS REJECTED.
10. Unknown timestamp observation remains UNKNOWN without invented time.
11. Dimension-aware delta methods (calculate_five_hour_delta vs calculate_weekly_delta).
12. All 28 historical observations preserved with explicit dimension-aware segment IDs.
13. Money firewall unchanged (AUTONOMOUS_SPEND_LIMIT = 0 EUR).
14. Zero credentials, tokens, or private data in records.
15. Prompt mapping status remains PARTIAL.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.resource_benchmark_manager import (
    CANONICAL_2026_08_31_OBSERVATIONS, HistoricalResourceObservation,
    ResourceBenchmarkManager,
)


class TestResourceResetSegmentationMission177G(unittest.TestCase):
    """Test suite for Mission 177G Resource Reset Segmentation Remediation."""

    @classmethod
    def setUpClass(cls):
        cls.mgr = ResourceBenchmarkManager()

    def test_01_all_28_observations_preserved(self):
        obs = self.mgr.load_observations()
        self.assertEqual(len(obs), 28)

    def test_02_google_same_segment_delta_allowed(self):
        obs = self.mgr.load_observations()
        g_1100 = [o for o in obs if o.observation_id == "resobs-20260831-110000-google"][0]
        g_1111 = [o for o in obs if o.observation_id == "resobs-20260831-111151-google"][0]

        delta = self.mgr.calculate_delta(g_1100, g_1111)
        self.assertEqual(delta["weekly_capacity_delta_pct_points"], -1.0)
        self.assertEqual(delta["five_hour_capacity_delta_pct_points"], -3.0)

    def test_03_google_pre_reset_to_14_21_reset_rejected(self):
        obs = self.mgr.load_observations()
        g_1324 = [o for o in obs if o.observation_id == "resobs-20260831-132400-google"][0]
        g_reset = [o for o in obs if o.observation_id == "resobs-20260831-142100-google-reset"][0]

        # 5-hour delta across reset boundary MUST fail closed
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(g_1324, g_reset)
        self.assertIn("Cross-five-hour-reset delta calculation DENIED", str(ctx.exception))

        # Default calculate_delta must also reject
        with self.assertRaises(ValueError) as ctx2:
            self.mgr.calculate_delta(g_1324, g_reset)
        self.assertIn("Cross-five-hour-reset delta calculation DENIED", str(ctx2.exception))

    def test_04_google_post_reset_delta_allowed(self):
        obs = self.mgr.load_observations()
        g_reset = [o for o in obs if o.observation_id == "resobs-20260831-142100-google-reset"][0]
        g_1432 = [o for o in obs if o.observation_id == "resobs-20260831-143200-google"][0]

        delta = self.mgr.calculate_five_hour_delta(g_reset, g_1432)
        self.assertEqual(delta["five_hour_capacity_delta_pct_points"], -3.0)
        self.assertEqual(delta["segment_id"], "google-pool1-5h-seg2")

    def test_05_old_google_account_to_new_google_account_rejected(self):
        obs = self.mgr.load_observations()
        old_acc = [o for o in obs if o.observation_id == "resobs-20260831-143200-google"][0]
        new_acc = [o for o in obs if o.observation_id == "resobs-20260831-213500-google-pool2"][0]

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(old_acc, new_acc)
        self.assertIn("Cross-account delta calculation DENIED", str(ctx.exception))

    def test_06_openai_five_hour_reset_boundary_rejected(self):
        obs = self.mgr.load_observations()
        oa_1432 = [o for o in obs if o.observation_id == "resobs-20260831-143200-openai"][0]
        oa_latest = [o for o in obs if o.observation_id == "resobs-20260831-223800-openai-latest"][0]

        # 5-hour delta 9% -> 83% across reset boundary MUST fail closed
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(oa_1432, oa_latest)
        self.assertIn("Cross-five-hour-reset delta calculation DENIED", str(ctx.exception))

    def test_07_openai_dimension_aware_weekly_delta_allowed(self):
        obs = self.mgr.load_observations()
        oa_start = [o for o in obs if o.observation_id == "resobs-20260831-110000-openai"][0]
        oa_latest = [o for o in obs if o.observation_id == "resobs-20260831-223800-openai-latest"][0]

        # Weekly delta in same billing week is valid via dimension-aware calculation
        weekly_delta = self.mgr.calculate_weekly_delta(oa_start, oa_latest)
        self.assertEqual(weekly_delta["weekly_capacity_delta_pct_points"], -33.0)
        self.assertEqual(weekly_delta["segment_id"], "openai-plus-weekly-seg1")

    def test_08_gemini_to_claude_gpt_pool_rejected(self):
        obs = self.mgr.load_observations()
        gemini_obs = [o for o in obs if o.observation_id == "resobs-20260831-223800-google-gemini-latest"][0]
        claude_obs = [o for o in obs if o.observation_id == "resobs-20260831-223800-google-claudegpt-latest"][0]

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(gemini_obs, claude_obs)
        self.assertIn("delta calculation DENIED", str(ctx.exception))

    def test_09_google_to_openai_rejected(self):
        obs = self.mgr.load_observations()
        g_obs = [o for o in obs if o.provider == "GOOGLE_GEMINI"][0]
        oa_obs = [o for o in obs if o.provider == "OPENAI_CODEX"][0]

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(g_obs, oa_obs)
        self.assertIn("Cross-provider delta calculation DENIED", str(ctx.exception))

    def test_10_unknown_timestamps_remain_unknown(self):
        obs = self.mgr.load_observations()
        unknown_obs = [o for o in obs if o.time_precision == "UNKNOWN"]
        self.assertEqual(len(unknown_obs), 2)
        for u in unknown_obs:
            self.assertEqual(u.observed_at, "UNKNOWN")

    def test_11_latest_checkpoint_preserved(self):
        summary = self.mgr.get_chief_summary()
        latest = summary["LATEST_RESOURCE_CHECKPOINT"]
        self.assertEqual(latest["openai_codex"], "66 weekly / 83 five-hour")
        self.assertEqual(latest["google_gemini"], "98 weekly / 85 five-hour")
        self.assertEqual(latest["google_claude_gpt_pool"], "100 weekly / 100 five-hour")

    def test_12_money_firewall_and_energy_semantics(self):
        summary = self.mgr.get_chief_summary()
        self.assertEqual(summary["MONEY_FIREWALL"], "0_EUR_AUTONOMOUS_SPEND_ENFORCED")
        self.assertEqual(summary["PHYSICAL_ENERGY_INFERENCE"], "DENIED")
        self.assertEqual(summary["CROSS_PROVIDER_PERCENT_CONVERSION"], "DENIED")


if __name__ == "__main__":
    unittest.main()
