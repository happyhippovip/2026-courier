#!/usr/bin/env python3
"""Unit Tests for Provider-Neutral Resource Pool Registry (Mission 168G).

Validates all 12 required acceptance conditions:
1. Multiple independent resource pools can coexist cleanly.
2. Zero credentials, passwords, tokens, or account emails stored.
3. Quota percentages are never mathematically summed across pools.
4. UNKNOWN capacity observations remain strictly UNKNOWN.
5. Quota reset detection is isolated per-pool without cross-pool assumptions.
6. Duplicate, hung, or no-information-gain work does not justify capacity expansion.
7. Money firewall remains active (0 EUR limit, PAYMENT_APPROVAL_REQUIRED).
8. Automatic account login and automatic account rotation are strictly DENIED.
9. Chief summary reports neutral pool IDs without credential leaks.
10. State persistence and reload preserves non-secret pool observations.
11. Malformed pool records fail safely.
12. Existing resource intelligence behavior (runways, observations, job telemetry) preserved.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.resource_intelligence import (
    JobResourceRecord, ResourceIntelligenceManager, ResourceObservation,
    ResourcePoolRecord, ResourcePoolRegistry,
)

COURIER_DIR = Path(__file__).resolve().parent.parent


class TestMultiPoolRegistryMission168G(unittest.TestCase):
    """Test suite for Mission 168G Multi-Pool Registry and Governance."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = Path(self.tmp_dir.name)
        (self.repo_dir / "events" / "resource-intelligence").mkdir(parents=True)
        self.registry = ResourcePoolRegistry(repo_dir=self.repo_dir)
        self.manager = ResourceIntelligenceManager(repo_dir=self.repo_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_multiple_independent_pools_coexist(self):
        p1 = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE", plan_class="PRO", status="AVAILABLE")
        p2 = ResourcePoolRecord(pool_id="GOOGLE_POOL_2", provider="GOOGLE", plan_class="PRO", status="AVAILABLE")
        p3 = ResourcePoolRecord(pool_id="ANTHROPIC_POOL_1", provider="ANTHROPIC", plan_class="STANDARD", status="AVAILABLE")

        self.registry.register_pool(p1)
        self.registry.register_pool(p2)
        self.registry.register_pool(p3)

        pools = self.registry.list_pools()
        self.assertEqual(len(pools), 3)
        pool_ids = {p["pool_id"] for p in pools}
        self.assertIn("GOOGLE_POOL_1", pool_ids)
        self.assertIn("GOOGLE_POOL_2", pool_ids)
        self.assertIn("ANTHROPIC_POOL_1", pool_ids)

    def test_02_zero_credentials_and_emails_stored(self):
        p1 = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE", plan_class="PRO", status="AVAILABLE")
        self.registry.register_pool(p1)

        raw = (self.repo_dir / "events" / "resource-intelligence" / "resource_pools.json").read_text(encoding="utf-8")
        patterns = [
            re.compile(r"(?i)(password|secret|apikey|api_key|token|auth|bearer)[\s:=]+[\"\x27][A-Za-z0-9_\-\.]{12,}[\"\x27]"),
            re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
            re.compile(r"ya29\.[0-9A-Za-z\-_]+"),
        ]
        for pat in patterns:
            self.assertEqual(pat.findall(raw), [], "Credential or email pattern matched in pool storage")

    def test_03_quota_percentages_never_summed(self):
        p1 = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE", status="AVAILABLE")
        p2 = ResourcePoolRecord(pool_id="GOOGLE_POOL_2", provider="GOOGLE", status="AVAILABLE")
        self.registry.register_pool(p1)
        self.registry.register_pool(p2)

        self.registry.update_pool_observation("GOOGLE_POOL_1", five_hour_pct=60.0)
        self.registry.update_pool_observation("GOOGLE_POOL_2", five_hour_pct=80.0)

        summary = self.registry.chief_summary()
        self.assertEqual(summary["AVAILABLE_POOLS"], 2)
        self.assertEqual(summary["ACTIVE_POOL_COUNT"], 2)
        # Verify 60% + 80% does NOT become 140% in summary
        self.assertNotIn("140", str(summary))
        self.assertNotIn(140.0, summary.values())

    def test_04_unknown_observations_remain_unknown(self):
        p = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE")
        self.registry.register_pool(p)

        ret = self.registry.get_pool("GOOGLE_POOL_1")
        self.assertEqual(ret["status"], "UNKNOWN")
        self.assertEqual(ret["availability"], "UNKNOWN")

    def test_05_reset_detection_remains_isolated_per_pool(self):
        p1 = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE")
        p2 = ResourcePoolRecord(pool_id="GOOGLE_POOL_2", provider="GOOGLE")
        self.registry.register_pool(p1)
        self.registry.register_pool(p2)

        # Pool 1: 40% -> 100% (Reset)
        self.registry.update_pool_observation("GOOGLE_POOL_1", five_hour_pct=40.0)
        self.registry.update_pool_observation("GOOGLE_POOL_1", five_hour_pct=100.0)

        # Pool 2: remains at 50%
        self.registry.update_pool_observation("GOOGLE_POOL_2", five_hour_pct=50.0)

        ret1 = self.registry.get_pool("GOOGLE_POOL_1")
        ret2 = self.registry.get_pool("GOOGLE_POOL_2")

        self.assertEqual(ret1["reset_information"].get("last_reset_type"), "FIVE_HOUR_RESET_OBSERVED")
        self.assertNotIn("last_reset_type", ret2["reset_information"])

    def test_06_waste_does_not_justify_capacity_expansion(self):
        p = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE", status="AVAILABLE")
        self.registry.register_pool(p)

        self.registry.record_job_usage("GOOGLE_POOL_1", productivity_class="DUPLICATE")
        self.registry.record_job_usage("GOOGLE_POOL_1", productivity_class="HUNG")
        self.registry.record_job_usage("GOOGLE_POOL_1", productivity_class="NO_INFORMATION_GAIN")

        summary = self.registry.chief_summary()
        self.assertTrue(summary["WASTE_DETECTED"])
        self.assertFalse(summary["PAYMENT_APPROVAL_REQUIRED"])

    def test_07_money_firewall_remains_zero_eur(self):
        summary = self.registry.chief_summary()
        self.assertEqual(summary["AUTONOMOUS_SPEND_LIMIT_EUR"], 0.0)
        self.assertFalse(summary["PAYMENT_APPROVAL_REQUIRED"])

    def test_08_automatic_login_and_rotation_denied(self):
        p = ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE")
        self.assertEqual(p.auto_account_login, "DENY")
        self.assertEqual(p.auto_account_rotation, "DENY")
        self.assertEqual(p.credential_storage, "DENY")

        summary = self.registry.chief_summary()
        self.assertEqual(summary["AUTO_ACCOUNT_LOGIN"], "DENY")
        self.assertEqual(summary["AUTO_ACCOUNT_ROTATION"], "DENY")
        self.assertEqual(summary["CREDENTIAL_STORAGE"], "DENY")

    def test_09_chief_summary_contains_neutral_pool_ids(self):
        self.registry.register_pool(ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE", status="AVAILABLE"))
        self.registry.register_pool(ResourcePoolRecord(pool_id="GOOGLE_POOL_2", provider="GOOGLE", status="LOW"))

        summary = self.registry.chief_summary()
        self.assertIn("GOOGLE_POOL_1", summary["RESOURCE_POOLS"])
        self.assertIn("GOOGLE_POOL_2", summary["RESOURCE_POOLS"])
        self.assertEqual(summary["RESOURCE_POOLS"]["GOOGLE_POOL_1"], "AVAILABLE")
        self.assertEqual(summary["RESOURCE_POOLS"]["GOOGLE_POOL_2"], "LOW")

    def test_10_persistence_and_reload(self):
        self.registry.register_pool(ResourcePoolRecord(pool_id="GOOGLE_POOL_1", provider="GOOGLE", plan_class="PRO", status="AVAILABLE"))
        self.registry.update_pool_observation("GOOGLE_POOL_1", five_hour_pct=85.0, notes="Verified post-switch")

        new_reg = ResourcePoolRegistry(repo_dir=self.repo_dir)
        loaded = new_reg.get_pool("GOOGLE_POOL_1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["capacity_observation"]["five_hour_remaining_pct"], 85.0)
        self.assertEqual(loaded["notes"], "Verified post-switch")

    def test_11_malformed_pool_records_fail_safely(self):
        with self.assertRaises(ValueError):
            ResourcePoolRecord(pool_id="", provider="GOOGLE")
        with self.assertRaises(ValueError):
            ResourcePoolRecord(pool_id="VALID_ID", provider="")

    def test_12_existing_resource_intelligence_manager_integration(self):
        obs = ResourceObservation(provider="GOOGLE", five_hour_remaining_pct=90.0)
        self.manager.record_observation(obs)

        job = JobResourceRecord(
            mission_id="168G", task_id="TASK-1", provider="GOOGLE", role="builder",
            start="2026-08-31T20:00:00+00:00", finish="2026-08-31T20:05:00+00:00",
            useful_work_score=1.0, information_gain=True,
        )
        self.manager.record_job(job)

        summary = self.manager.summary()
        self.assertEqual(summary["schema_version"], "1.1")
        self.assertIn("resource_pools", summary)
        self.assertEqual(summary["heavy_job_limit"], 1)


if __name__ == "__main__":
    unittest.main()
