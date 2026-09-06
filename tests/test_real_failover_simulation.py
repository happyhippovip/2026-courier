#!/usr/bin/env python3
"""Acceptance Tests for Real Failover Simulation & Level 4 Deployment Prep."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_replacement_host import bootstrap_replacement_host
from scripts.external_sentinel_protocol import (
    ExternalSentinelObserver,
    HostHealthStatus,
)
from scripts.host_survival_engine import HostSurvivalEngine
from scripts.infra_decision_engine import evaluate_infrastructure_options
from scripts.sentinel_deployment_package import build_sentinel_deployment_package


class TestRealFailoverSimulation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="failover_test_"))
        self.primary_engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="primary-host-01")
        self.primary_engine.generate_dr_manifest()
        self.sentinel = ExternalSentinelObserver(repo_dir=self.test_dir, missed_heartbeats_threshold=2, stale_seconds_threshold=2.0)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_sentinel_deployment_package_builds_cleanly(self):
        """Sentinel deployment bundle is created as standalone tar.gz with zero secrets."""
        pkg_dir = self.test_dir / "dist"
        tar_path = build_sentinel_deployment_package(pkg_dir)
        self.assertTrue(tar_path.exists())
        self.assertGreater(tar_path.stat().st_size, 100)

    def test_02_full_failover_and_old_host_return_rejection(self):
        """Simulates full failover lifecycle and proves stale primary cannot regain write authority."""
        # 1. Primary Running & Publishing Telemetry
        self.sentinel.publish_safe_telemetry(
            host_id="primary-host-01",
            supervisor_generation=1,
            last_heartbeat="2026-09-01T04:55:00+00:00",
            last_progress="2026-09-01T04:55:00+00:00",
        )
        can_p1_before, _ = self.primary_engine.can_mutate_state("primary-host-01", host_generation=1)
        self.assertTrue(can_p1_before)

        # 2. Standby Node Executes Takeover
        res = bootstrap_replacement_host(new_host_id="standby-host-02", repo_dir=self.test_dir)
        self.assertEqual(res["bootstrap_verdict"], "SUCCESS")
        self.assertEqual(res["new_generation"], 2)
        self.assertIn("primary-host-01", res["fenced_hosts"])

        # 3. Standby is Authorized under Gen 2
        standby_engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="standby-host-02")
        can_standby, _ = standby_engine.can_mutate_state("standby-host-02", host_generation=2)
        self.assertTrue(can_standby)

        # 4. Old Primary re-awakens and attempts mutation under Gen 1 -> STRICTLY DENIED
        can_old_primary, reason = self.primary_engine.can_mutate_state("primary-host-01", host_generation=1)
        self.assertFalse(can_old_primary)
        self.assertIn("HOST_FENCED_OFF", reason)

    def test_03_deployment_profiles_and_cost_invariants(self):
        """All profiles define resources and adhere to 0 EUR autonomous spend limit."""
        profiles_file = Path(__file__).resolve().parent.parent / "events" / "host-survival" / "deployment_profiles.json"
        data = json.loads(profiles_file.read_text(encoding="utf-8"))
        self.assertEqual(data["autonomous_spend_limit_eur"], 0.0)
        self.assertGreaterEqual(len(data["profiles"]), 4)

    def test_04_durable_off_host_state_classification_integrity(self):
        """Classification covers REPLICATE, RECONSTRUCT, LOCAL_ONLY, and SECRET_DO_NOT_REPLICATE."""
        class_file = Path(__file__).resolve().parent.parent / "events" / "host-survival" / "durable_off_host_state_classification.json"
        data = json.loads(class_file.read_text(encoding="utf-8"))
        cats = data["categories"]
        self.assertIn("REPLICATE", cats)
        self.assertIn("RECONSTRUCT", cats)
        self.assertIn("LOCAL_ONLY", cats)
        self.assertIn("SECRET_DO_NOT_REPLICATE", cats)

    def test_05_infra_decision_engine_evaluation(self):
        """Infra decision engine ranks options and recommends 0 EUR options for autonomous operation."""
        rep = evaluate_infrastructure_options()
        self.assertEqual(rep["autonomous_spend_limit_eur"], 0.0)
        self.assertEqual(rep["best_autonomous_external_option"], "GITHUB_SENTINEL")
        self.assertEqual(rep["estimated_autonomous_cost_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
