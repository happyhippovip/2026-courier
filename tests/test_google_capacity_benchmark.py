#!/usr/bin/env python3
"""Acceptance Tests for Google AI Capacity Benchmark Engine (Real Telemetry Mode)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.google_capacity_benchmark import GoogleCapacityBenchmark, JobRecord


class TestGoogleCapacityBenchmark(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="bench_test_"))
        self.session_file = self.test_dir / "benchmark_session.json"
        self.bench = GoogleCapacityBenchmark(
            account_alias="google-account-pro-benchmark-01",
            plan="GOOGLE_PRO",
            capacity_source="UNKNOWN",
            session_file=self.session_file,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_real_telemetry_initialization_invariants(self):
        """Validates 1-account, 0 EUR spend limit, and UNKNOWN capacity unless directly observed."""
        self.assertEqual(self.bench.account_count, 1)
        self.assertEqual(self.bench.spend_limit_eur, 0.0)
        self.assertEqual(self.bench.current_capacity, "UNKNOWN")
        self.assertEqual(self.bench.capacity_source, "UNKNOWN")
        self.assertEqual(self.bench.state, "PROGRESSING")
        self.assertTrue(self.session_file.exists())

    def test_02_real_job_recording_with_evidence_reference(self):
        """Only accepted outputs count toward accepted metrics, and evidence reference is preserved."""
        rec1 = self.bench.record_job(
            task_id="task-01-creator-pkg",
            task_type="REVENUE_ENABLING",
            model_or_product="GEMINI_2_5_PRO",
            result="PASS",
            useful_output_count=3,
            output_accepted=True,
            start_time="2026-09-01T04:00:00Z",
            end_time="2026-09-01T04:02:00Z",
            elapsed_seconds=120.0,
            evidence_reference="runtime/content/mission_151g_batch_manifest.json",
            capacity_evidence="UNVERIFIED",
            asset_type="REVENUE_ASSET",
            notes="3 Short packages produced and passed QC",
        )
        self.assertEqual(self.bench.metrics.tasks_completed, 1)
        self.assertEqual(self.bench.metrics.accepted_assets, 3)
        self.assertEqual(self.bench.metrics.revenue_assets_created, 3)
        self.assertEqual(rec1.evidence_reference, "runtime/content/mission_151g_batch_manifest.json")

    def test_03_provider_limit_handling(self):
        """Transitions state to WAITING_RESOURCE upon real provider limit event."""
        self.bench.record_provider_limit(notes="HTTP 429 Resource Exhausted")
        self.assertEqual(self.bench.state, "WAITING_RESOURCE")
        self.assertEqual(self.bench.limit_type, "PROVIDER_QUOTA_EXHAUSTION")
        self.assertIsNotNone(self.bench.time_to_limit)

    def test_04_zero_fabricated_revenue(self):
        """Real revenue remains strictly 0.0 EUR until payment is verified."""
        self.assertEqual(self.bench.metrics.real_revenue_eur, 0.0)


if __name__ == "__main__":
    unittest.main()
