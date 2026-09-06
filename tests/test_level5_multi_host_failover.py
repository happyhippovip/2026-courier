#!/usr/bin/env python3
"""Acceptance Tests for Level-5 Multi-Host Cluster Registry and Automated Failover."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.disaster_recovery_bundle_sync import DisasterRecoveryBundleSync
from scripts.external_sentinel_protocol import ExternalSentinelObserver, HostHealthStatus
from scripts.generic_host_registry import (
    GenericHostRegistry,
    HostHealthState,
    HostRole,
)
from scripts.host_survival_engine import HostSurvivalEngine
from scripts.multi_host_failover_coordinator import MultiHostFailoverCoordinator


class TestLevel5MultiHostFailover(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="level5_test_"))
        self.registry = GenericHostRegistry(repo_dir=self.test_dir)
        self.registry.register_host(
            "home-mac-primary",
            HostRole.PRIMARY,
            "APPLE_SILICON_M_SERIES",
            ["HEAVY_RENDER", "CODE_BUILD"],
        )
        self.registry.register_host(
            "standby-mac-02",
            HostRole.STANDBY_HOT,
            "APPLE_SILICON_M_SERIES",
            ["HEAVY_RENDER", "CODE_BUILD"],
        )
        self.engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="home-mac-primary")
        self.engine.generate_dr_manifest()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_host_registry_single_primary_enforcement(self):
        """Only one host can be primary; registering a new primary demotes previous primary."""
        p = self.registry.get_active_primary()
        self.assertIsNotNone(p)
        self.assertEqual(p.host_id, "home-mac-primary")

        # Registering node-3 as primary demotes home-mac-primary
        self.registry.register_host(
            "node-3",
            HostRole.PRIMARY,
            "LINUX_X86_64",
            ["LIGHT_OPS"],
        )
        p_new = self.registry.get_active_primary()
        self.assertEqual(p_new.host_id, "node-3")
        self.assertEqual(self.registry.hosts["home-mac-primary"].role, HostRole.STANDBY_HOT.value)

    def test_02_standby_promotion_increments_cluster_generation(self):
        """Promoting hot standby increments cluster generation and fences previous primary."""
        self.assertEqual(self.registry.active_generation, 1)
        ok, new_gen, msg = self.registry.promote_standby_to_primary("standby-mac-02")
        self.assertTrue(ok)
        self.assertEqual(new_gen, 2)
        self.assertEqual(self.registry.active_generation, 2)

        # home-mac-primary is now fenced
        self.assertTrue(self.registry.hosts["home-mac-primary"].is_fenced)
        self.assertEqual(self.registry.hosts["home-mac-primary"].health_state, HostHealthState.FENCED_OFF.value)

    def test_03_automated_failover_coordinator_promotes_hot_standby(self):
        """Failover coordinator promotes hot standby when primary is MACHINE_OFFLINE."""
        coord = MultiHostFailoverCoordinator(repo_dir=self.test_dir)

        # Simulate primary offline by having sentinel record missing telemetry >= threshold
        coord.sentinel.classify_host_health()  # 1 miss
        coord.sentinel.classify_host_health()  # 2 misses
        coord.sentinel.classify_host_health()  # 3 misses -> MACHINE_OFFLINE

        in_flight = [
            {"job_id": "job-safe-1", "effect_status": "CLEAN_NOT_STARTED"},
            {"job_id": "job-amb-1", "effect_status": "UNKNOWN"},
        ]

        triggered, reason, record = coord.evaluate_cluster_and_failover_if_needed(in_flight)
        self.assertTrue(triggered)
        self.assertIn("FAILOVER_COMPLETED_PROMOTED_standby-mac-02", reason)
        self.assertIsNotNone(record)
        self.assertEqual(record.new_generation, 2)
        self.assertEqual(record.ambiguous_jobs_count, 1)

    def test_04_stale_primary_return_after_failover_is_fenced(self):
        """Returning old primary is fenced and strictly denied write authorization."""
        coord = MultiHostFailoverCoordinator(repo_dir=self.test_dir)
        coord.sentinel.classify_host_health()
        coord.sentinel.classify_host_health()
        coord.sentinel.classify_host_health()
        coord.evaluate_cluster_and_failover_if_needed()

        # Old primary attempts mutation under gen 1 -> DENIED
        can_old, reason = self.engine.can_mutate_state("home-mac-primary", host_generation=1)
        self.assertFalse(can_old)
        self.assertIn("HOST_FENCED_OFF", reason)

    def test_05_dr_bundle_sync_creation_and_verification(self):
        """DR bundle is created and verified against SHA-256 manifest."""
        syncer = DisasterRecoveryBundleSync(repo_dir=self.test_dir)
        tar_path, sha, meta = syncer.create_snapshot_bundle("test-bundle-01")
        manifest_path = self.test_dir / "events" / "disaster-recovery" / "bundles" / "test-bundle-01_manifest.json"

        self.assertTrue(tar_path.exists())
        self.assertTrue(manifest_path.exists())

        ok, v_msg = syncer.verify_snapshot_bundle(tar_path, manifest_path)
        self.assertTrue(ok)
        self.assertEqual(v_msg, "VERIFIED")


if __name__ == "__main__":
    unittest.main()
