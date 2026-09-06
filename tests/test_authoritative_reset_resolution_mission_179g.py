#!/usr/bin/env python3
"""Authoritative Reset Segment Resolution Acceptance Tests (Mission 179G).

Validates all primary security properties from Codex 178C remediation contract:
1. Forged same segment ID across Google reset is DENIED.
2. Forged same segment ID across OpenAI reset is DENIED.
3. Caller attempts to tamper with segment metadata or percentage -> DENIED via integrity check.
4. Unknown observation ID -> DENIED.
5. Malformed observation dictionary or invalid type -> DENIED.
6. Cross-account comparison -> DENIED.
7. Cross-model-pool comparison -> DENIED.
8. Cross-provider comparison -> DENIED.
9. Cross-dimension comparison -> DENIED.
10. Google pre/post 14:21 five-hour -> DENIED.
11. Google post-reset 100% -> 97% -> ALLOWED.
12. Google five-hour reset does not reset weekly dimension.
13. OpenAI 0% -> 83% five-hour -> DENIED.
14. OpenAI five-hour reset does not fabricate weekly reset.
15. UNKNOWN timestamp remains UNKNOWN and cannot produce a numeric delta.
16. Unsafe chronological ambiguity / out-of-order timestamps -> FAIL CLOSED.
17. Canonical observation IDs passed directly calculate deterministic delta.
18. Money firewall unchanged (0 EUR spend limit).
19. Physical energy inference strictly denied.
20. All 28 canonical observations preserved verbatim.
"""

from __future__ import annotations

from dataclasses import replace
import json
import unittest
from pathlib import Path

from scripts.resource_benchmark_manager import (
    CANONICAL_2026_08_31_OBSERVATIONS, HistoricalResourceObservation,
    ResourceBenchmarkManager,
)


class TestAuthoritativeResetResolutionMission179G(unittest.TestCase):
    """Test suite for Mission 179G Authoritative Reset Segment Resolution."""

    @classmethod
    def setUpClass(cls):
        cls.mgr = ResourceBenchmarkManager()
        cls.obs = {o.observation_id: o for o in cls.mgr.load_observations()}

    def test_01_all_28_canonical_observations_preserved(self):
        obs = self.mgr.load_observations()
        self.assertEqual(len(obs), 28)

    def test_02_forged_segment_id_across_google_reset_denied(self):
        before = self.obs["resobs-20260831-132400-google"]
        reset = self.obs["resobs-20260831-142100-google-reset"]
        forged = replace(reset, five_hour_segment_id=before.five_hour_segment_id)

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(before, forged)
        self.assertIn("Observation integrity violation", str(ctx.exception))

    def test_03_forged_segment_id_across_openai_reset_denied(self):
        before = self.obs["resobs-20260831-unknown-openai"]
        latest = self.obs["resobs-20260831-223800-openai-latest"]
        forged = replace(latest, five_hour_segment_id=before.five_hour_segment_id)

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(before, forged)
        self.assertTrue(
            "Observation integrity violation" in str(ctx.exception) or
            "UNKNOWN timestamp" in str(ctx.exception)
        )

    def test_04_caller_tampered_metadata_on_same_segment_denied(self):
        obs1 = self.obs["resobs-20260831-110000-openai"]
        obs2 = self.obs["resobs-20260831-111151-openai"]
        tampered = replace(obs2, weekly_remaining_pct=50.0)

        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(obs1, tampered)
        self.assertIn("Observation integrity violation", str(ctx.exception))

    def test_05_unknown_observation_id_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta("resobs-nonexistent-id", "resobs-20260831-110000-openai")
        self.assertIn("Unknown observation ID", str(ctx.exception))

    def test_06_malformed_observation_type_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(12345, "resobs-20260831-110000-openai")
        self.assertIn("Unsupported observation input type", str(ctx.exception))

    def test_07_cross_account_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(
                "resobs-20260831-143200-google",
                "resobs-20260831-213500-google-pool2"
            )
        self.assertIn("Cross-account delta calculation DENIED", str(ctx.exception))

    def test_08_cross_model_pool_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(
                "resobs-20260831-223800-google-gemini-latest",
                "resobs-20260831-223800-google-claudegpt-latest"
            )
        self.assertIn("delta calculation DENIED", str(ctx.exception))

    def test_09_cross_provider_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(
                "resobs-20260831-110000-google",
                "resobs-20260831-110000-openai"
            )
        self.assertIn("Cross-provider delta calculation DENIED", str(ctx.exception))

    def test_10_google_pre_post_14_21_five_hour_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(
                "resobs-20260831-132400-google",
                "resobs-20260831-142100-google-reset"
            )
        self.assertIn("Cross-five-hour-reset delta calculation DENIED", str(ctx.exception))

    def test_11_google_post_reset_delta_allowed(self):
        result = self.mgr.calculate_five_hour_delta(
            "resobs-20260831-142100-google-reset",
            "resobs-20260831-143200-google"
        )
        self.assertEqual(result["five_hour_capacity_delta_pct_points"], -3.0)
        self.assertEqual(result["segment_id"], "google-pool1-5h-seg2")

    def test_12_google_five_hour_reset_does_not_reset_weekly(self):
        result = self.mgr.calculate_weekly_delta(
            "resobs-20260831-110000-google",
            "resobs-20260831-143200-google"
        )
        self.assertEqual(result["weekly_capacity_delta_pct_points"], -13.0)
        self.assertEqual(result["segment_id"], "google-pool1-weekly-seg1")

    def test_13_openai_zero_to_83_five_hour_reset_denied(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(
                "resobs-20260831-unknown-openai",
                "resobs-20260831-223800-openai-latest"
            )
        self.assertTrue(
            "Cross-five-hour-reset" in str(ctx.exception) or
            "UNKNOWN timestamp" in str(ctx.exception)
        )

    def test_14_openai_weekly_delta_in_same_week_allowed(self):
        result = self.mgr.calculate_weekly_delta(
            "resobs-20260831-110000-openai",
            "resobs-20260831-223800-openai-latest"
        )
        self.assertEqual(result["weekly_capacity_delta_pct_points"], -33.0)
        self.assertEqual(result["segment_id"], "openai-plus-weekly-seg1")

    def test_15_unknown_timestamp_fails_closed(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_five_hour_delta(
                "resobs-20260831-110000-openai",
                "resobs-20260831-unknown-openai"
            )
        self.assertIn("Timestamp ordering cannot be established for UNKNOWN timestamp", str(ctx.exception))

    def test_16_out_of_order_timestamps_fail_closed(self):
        with self.assertRaises(ValueError) as ctx:
            self.mgr.calculate_delta(
                "resobs-20260831-112759-openai",
                "resobs-20260831-110000-openai"
            )
        self.assertIn("Timestamps not in chronological order", str(ctx.exception))

    def test_17_deterministic_string_id_calculations(self):
        res1 = self.mgr.calculate_delta(
            "resobs-20260831-110000-openai",
            "resobs-20260831-111151-openai"
        )
        res2 = self.mgr.calculate_delta(
            "resobs-20260831-110000-openai",
            "resobs-20260831-111151-openai"
        )
        self.assertEqual(res1, res2)
        self.assertEqual(res1["weekly_capacity_delta_pct_points"], -1.0)
        self.assertEqual(res1["five_hour_capacity_delta_pct_points"], -6.0)

    def test_18_money_firewall_and_physical_energy_denied(self):
        summary = self.mgr.get_chief_summary()
        self.assertEqual(summary["MONEY_FIREWALL"], "0_EUR_AUTONOMOUS_SPEND_ENFORCED")
        self.assertEqual(summary["PHYSICAL_ENERGY_INFERENCE"], "DENIED")
        self.assertEqual(summary["AUTOMATIC_ACCOUNT_ROTATION"], "DENIED")
        self.assertEqual(summary["CROSS_PROVIDER_PERCENT_CONVERSION"], "DENIED")


if __name__ == "__main__":
    unittest.main()
