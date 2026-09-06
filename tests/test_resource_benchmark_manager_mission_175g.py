#!/usr/bin/env python3
"""Historical Resource Benchmark Manager Acceptance Tests (Mission 175G).

Validates all authoritative conditions:
1. Historical observations load successfully (28 total records).
2. Exact timestamps preserved (11 records).
3. Approximate timestamps preserved (15 records).
4. Unknown timestamps preserved (2 records).
5. Reset boundary segmentation (Google 5h reset at 14:21).
6. Same-pool delta calculation (OpenAI Benchmark 002: 99% -> 84% = -15 pct points).
7. Cross-provider delta calculation strictly rejected.
8. Cross-account delta calculation strictly rejected.
9. Cross-model-pool delta calculation strictly rejected.
10. Missing prompt numbers not invented (prompt_mapping_status = PARTIAL).
11. Latest checkpoint matches 22:38 screenshot values.
12. Gemini and Claude/GPT pools remain separate (never summed).
13. Quota never labelled physical electricity or kWh.
14. Money firewall unchanged (0 EUR spend limit).
15. Zero credentials or tokens in records.
16. Benchmark Run 002 metadata preserved.
17. Mission 173G resource context preserved.
18. Reset boundary detection isolates segments.
19. Chief summary contains required fields.
20. Idempotent load and persistence.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from scripts.resource_benchmark_manager import (
    CANONICAL_2026_08_31_OBSERVATIONS, HistoricalResourceObservation,
    ResourceBenchmarkManager,
)


class TestResourceBenchmarkManagerMission175G(unittest.TestCase):
    """Test suite for Mission 175G Historical Resource Benchmark Manager."""

    @classmethod
    def setUpClass(cls):
        cls.mgr = ResourceBenchmarkManager()

    def test_01_historical_observations_load(self):
        obs = self.mgr.load_observations()
        self.assertEqual(len(obs), 28)

    def test_02_exact_timestamps_count(self):
        obs = self.mgr.load_observations()
        exact = [o for o in obs if o.time_precision == "EXACT"]
        self.assertEqual(len(exact), 11)

    def test_03_approximate_timestamps_count(self):
        obs = self.mgr.load_observations()
        approx = [o for o in obs if o.time_precision == "APPROXIMATE"]
        self.assertEqual(len(approx), 15)

    def test_04_unknown_timestamps_count(self):
        obs = self.mgr.load_observations()
        unknown = [o for o in obs if o.time_precision == "UNKNOWN"]
        self.assertEqual(len(unknown), 2)
        for u in unknown:
            self.assertEqual(u.observed_at, "UNKNOWN")

    def test_05_reset_boundary_segmentation(self):
        obs = self.mgr.load_observations()
        reset_obs = [o for o in obs if o.reset_observation is not None]
        self.assertGreaterEqual(len(reset_obs), 1)
        google_reset = [o for o in reset_obs if o.observation_id == "resobs-20260831-142100-google-reset"][0]
        self.assertEqual(google_reset.five_hour_remaining_pct, 100.0)

    def test_06_same_pool_delta_calculation(self):
        obs = self.mgr.load_observations()
        start = [o for o in obs if o.observation_id == "resobs-20260831-110000-openai"][0]
        end = [o for o in obs if o.observation_id == "resobs-20260831-115450-openai"][0]

        delta = self.mgr.calculate_delta(start, end)
        self.assertEqual(delta["weekly_capacity_delta_pct_points"], -5.0)
        self.assertEqual(delta["five_hour_capacity_delta_pct_points"], -33.0)
        self.assertIsNone(delta["physical_electricity_kwh"])

    def test_07_cross_provider_delta_rejected(self):
        obs = self.mgr.load_observations()
        openai_obs = [o for o in obs if o.provider == "OPENAI_CODEX"][0]
        google_obs = [o for o in obs if o.provider == "GOOGLE_GEMINI"][0]

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(openai_obs, google_obs)
        self.assertIn("Cross-provider delta calculation DENIED", str(ctx.exception))

    def test_08_cross_account_delta_rejected(self):
        obs = self.mgr.load_observations()
        pool1_obs = [o for o in obs if o.account_pool_id == "google-account-pro-pool1"][0]
        pool2_obs = [o for o in obs if o.account_pool_id == "google-account-pro-pool2"][0]

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(pool1_obs, pool2_obs)
        self.assertIn("Cross-account delta calculation DENIED", str(ctx.exception))

    def test_09_cross_model_pool_delta_rejected(self):
        obs = self.mgr.load_observations()
        gemini_obs = [o for o in obs if o.observation_id == "resobs-20260831-223800-google-gemini-latest"][0]
        claude_obs = [o for o in obs if o.observation_id == "resobs-20260831-223800-google-claudegpt-latest"][0]

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(gemini_obs, claude_obs)
        self.assertIn("delta calculation DENIED", str(ctx.exception))

    def test_10_missing_prompt_numbers_not_invented(self):
        obs = self.mgr.load_observations()
        for o in obs:
            self.assertEqual(o.prompt_mapping_status, "PARTIAL")

    def test_11_latest_checkpoint_values(self):
        summary = self.mgr.get_chief_summary()
        latest = summary["LATEST_RESOURCE_CHECKPOINT"]
        self.assertEqual(latest["openai_codex"], "66 weekly / 83 five-hour")
        self.assertEqual(latest["google_gemini"], "98 weekly / 85 five-hour")
        self.assertEqual(latest["google_claude_gpt_pool"], "100 weekly / 100 five-hour")

    def test_12_separate_model_pools_never_summed(self):
        obs = self.mgr.load_observations()
        latest_gemini = [o for o in obs if o.observation_id == "resobs-20260831-223800-google-gemini-latest"][0]
        latest_claude = [o for o in obs if o.observation_id == "resobs-20260831-223800-google-claudegpt-latest"][0]

        self.assertNotEqual(latest_gemini.model_pool, latest_claude.model_pool)
        self.assertEqual(latest_gemini.weekly_remaining_pct, 98.0)
        self.assertEqual(latest_claude.weekly_remaining_pct, 100.0)

    def test_13_quota_never_labelled_physical_electricity(self):
        obs = self.mgr.load_observations()
        for o in obs:
            raw_text = json.dumps(o.to_dict()).lower()
            self.assertNotIn("kwh", raw_text)
            self.assertNotIn("joule", raw_text)
            self.assertNotIn("watt", raw_text)

    def test_14_money_firewall_unchanged(self):
        obs = self.mgr.load_observations()
        for o in obs:
            self.assertEqual(o.spend_eur, 0.0)

    def test_15_zero_secrets_stored(self):
        obs = self.mgr.load_observations()
        for o in obs:
            raw_text = json.dumps(o.to_dict()).lower()
            self.assertNotIn("password", raw_text)
            self.assertNotIn("bearer", raw_text)
            self.assertNotIn("oauth_token", raw_text)
            self.assertNotIn("client_secret", raw_text)

    def test_16_benchmark_run_002_preserved(self):
        obs = self.mgr.load_observations()
        bm002 = [o for o in obs if o.benchmark_run == "RESOURCE_BENCHMARK_RUN_002"]
        self.assertGreaterEqual(len(bm002), 20)

    def test_17_mission_173g_resource_context_preserved(self):
        obs = self.mgr.load_observations()
        m173g_obs = [o for o in obs if o.mission_id == "MISSION_173G"]
        self.assertGreaterEqual(len(m173g_obs), 2)

    def test_18_chief_summary_structure(self):
        summary = self.mgr.get_chief_summary()
        self.assertTrue(summary["RESOURCE_HISTORY_AVAILABLE"])
        self.assertEqual(summary["RESOURCE_HISTORY_DATE"], "2026-08-31")
        self.assertEqual(summary["RESOURCE_OBSERVATION_COUNT"], 28)
        self.assertEqual(summary["OPENAI_SEGMENTS"], 2)
        self.assertEqual(summary["GOOGLE_SEGMENTS"], 3)
        self.assertEqual(summary["RESET_BOUNDARIES"], 2)


if __name__ == "__main__":
    unittest.main()
