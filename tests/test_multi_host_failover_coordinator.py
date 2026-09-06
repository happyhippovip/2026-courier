#!/usr/bin/env python3
"""Focused Acceptance Test Suite for Multi-Host Failover Coordinator (Mission Infinite Life Level-5).

Verifies:
1. Failover evaluation aborts when primary is healthy or no standbys are available
2. Automated standby host promotion when primary is conclusively MACHINE_OFFLINE
3. Fencing token update and generation increment
4. Event logging to events/host-survival/failover_events_log.json
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.external_sentinel_protocol import HostHealthStatus
from scripts.generic_host_registry import GenericHostRegistry, HostHealthState, HostRole
from scripts.host_survival_engine import HostSurvivalEngine
from scripts.multi_host_failover_coordinator import MultiHostFailoverCoordinator


class TestMultiHostFailoverCoordinator(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="failover_test_"))
        self.survival_dir = self.test_dir / "events" / "host-survival"
        self.survival_dir.mkdir(parents=True, exist_ok=True)

        self.coordinator = MultiHostFailoverCoordinator(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_no_failover_when_no_registered_primary(self):
        """Returns False when no active primary is registered."""
        ok, reason, rec = self.coordinator.evaluate_cluster_and_failover_if_needed()
        self.assertFalse(ok)
        self.assertIn("NO_REGISTERED_PRIMARY", reason)
        self.assertIsNone(rec)

    def test_02_no_failover_when_primary_is_alive(self):
        """Returns False when primary is alive according to sentinel."""
        # Register primary and standby
        self.coordinator.registry.register_host("primary-01", HostRole.PRIMARY, "macbook_pro", ["CPU"])
        self.coordinator.registry.register_host("standby-02", HostRole.STANDBY_HOT, "mac_mini", ["CPU"])

        # Mock sentinel heartbeat
        spec_file = self.survival_dir / "external_sentinel_interface.json"
        spec_file.write_text(
            json.dumps({"heartbeat_at": "2026-09-01T12:00:00Z", "health_state": "ONLINE"}),
            encoding="utf-8",
        )

        ok, reason, rec = self.coordinator.evaluate_cluster_and_failover_if_needed()
        self.assertFalse(ok)
        self.assertIn("PRIMARY_NOT_OFFLINE", reason)
        self.assertIsNone(rec)

    def test_03_automated_failover_when_primary_offline(self):
        """Promotes standby to primary and fences old primary when primary is dead."""
        # Register primary and standby
        self.coordinator.registry.register_host("primary-01", HostRole.PRIMARY, "macbook_pro", ["CPU"])
        self.coordinator.registry.register_host("standby-02", HostRole.STANDBY_HOT, "mac_mini", ["CPU"])

        # Ensure valid DR manifest
        manifest = self.coordinator.survival_engine.generate_dr_manifest()

        # Mock sentinel state as MACHINE_OFFLINE
        self.coordinator.sentinel.classify_host_health = lambda: (
            HostHealthStatus.MACHINE_OFFLINE,
            "No heartbeat received for 300s",
        )

        ok, msg, rec = self.coordinator.evaluate_cluster_and_failover_if_needed()

        self.assertTrue(ok)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.previous_primary_host_id, "primary-01")
        self.assertEqual(rec.promoted_primary_host_id, "standby-02")
        self.assertEqual(rec.new_generation, 2)
        self.assertIn("primary-01", rec.fenced_hosts)
        self.assertTrue(self.coordinator.events_log_file.exists())


if __name__ == "__main__":
    unittest.main()
