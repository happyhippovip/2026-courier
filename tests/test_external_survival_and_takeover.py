#!/usr/bin/env python3
"""Acceptance Tests for External Sentinel, Takeover Protocol, and Hot-Plug Workers."""

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.external_sentinel_protocol import (
    ExternalSafeTelemetry,
    ExternalSentinelObserver,
    HostHealthStatus,
)
from scripts.host_survival_engine import HostSurvivalEngine
from scripts.hot_plug_worker_registry import HotPlugWorkerRegistry


class TestExternalSurvivalAndTakeover(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="ext_survival_test_"))
        self.engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="primary-mac-01")
        self.sentinel = ExternalSentinelObserver(repo_dir=self.test_dir, missed_heartbeats_threshold=2, stale_seconds_threshold=2.0)
        self.registry = HotPlugWorkerRegistry(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_external_heartbeat_fresh_and_stale(self):
        """Fresh telemetry classifies as HEALTHY; expired heartbeat classifies as SUPERVISOR_DEAD."""
        import datetime as dt
        now_dt = dt.datetime.now(dt.timezone.utc)
        fresh_ts = now_dt.isoformat()
        stale_ts = (now_dt - dt.timedelta(seconds=60)).isoformat()

        # 1. Fresh heartbeat
        self.sentinel.publish_safe_telemetry(
            host_id="primary-mac-01",
            supervisor_generation=1,
            last_heartbeat=fresh_ts,
            last_progress=fresh_ts,
            recovery_state="RECOVERY_READY",
        )
        st_fresh, _ = self.sentinel.classify_host_health()
        self.assertEqual(st_fresh, HostHealthStatus.HEALTHY)

        # 2. Stale heartbeat
        self.sentinel.publish_safe_telemetry(
            host_id="primary-mac-01",
            supervisor_generation=1,
            last_heartbeat=stale_ts,
            last_progress=stale_ts,
            recovery_state="RECOVERY_READY",
        )
        st_stale, _ = self.sentinel.classify_host_health()
        self.assertIn(st_stale, (HostHealthStatus.SUPERVISOR_DEAD, HostHealthStatus.MACHINE_OFFLINE))

    def test_02_temporary_unreachable_vs_prolonged_machine_offline(self):
        """1 miss = HOST_UNREACHABLE; >= threshold misses = MACHINE_OFFLINE."""
        # Telemetry file does not exist
        st1, reason1 = self.sentinel.classify_host_health()
        self.assertEqual(st1, HostHealthStatus.HOST_UNREACHABLE)

        st2, reason2 = self.sentinel.classify_host_health()
        self.assertEqual(st2, HostHealthStatus.MACHINE_OFFLINE)
        self.assertTrue(self.sentinel.should_trigger_takeover())

    def test_03_replacement_takeover_and_stale_primary_fencing(self):
        """When standby host executes takeover, old primary is fenced and denied mutations."""
        # Initial primary state
        self.engine.generate_dr_manifest()
        can_p1, _ = self.engine.can_mutate_state(host_id="primary-mac-01", host_generation=1)
        self.assertTrue(can_p1)

        # Standby node takeover
        standby_engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="standby-mac-02")
        new_token = standby_engine.perform_host_takeover("standby-mac-02")
        self.assertEqual(new_token.host_generation, 2)
        self.assertEqual(new_token.primary_host_id, "standby-mac-02")

        # Standby can write under gen 2
        can_standby, _ = standby_engine.can_mutate_state(host_id="standby-mac-02", host_generation=2)
        self.assertTrue(can_standby)

        # Old primary returns and attempts write under gen 1 -> DENIED
        can_old, reason = self.engine.can_mutate_state(host_id="primary-mac-01", host_generation=1)
        self.assertFalse(can_old)
        self.assertIn("HOST_FENCED_OFF", reason)

    def test_04_two_replacement_candidates_monotonic_fencing(self):
        """If two replacement candidates attempt takeover, higher generation wins."""
        eng_b = HostSurvivalEngine(repo_dir=self.test_dir, host_id="candidate-b")
        eng_c = HostSurvivalEngine(repo_dir=self.test_dir, host_id="candidate-c")

        token_b = eng_b.perform_host_takeover("candidate-b")
        token_c = eng_c.perform_host_takeover("candidate-c")

        self.assertEqual(token_b.host_generation, 2)
        self.assertEqual(token_c.host_generation, 3)

        # Candidate B with gen 2 is now stale compared to gen 3
        can_b, reason_b = eng_b.can_mutate_state("candidate-b", host_generation=2)
        self.assertFalse(can_b)

        # Candidate C with gen 3 is authorized
        can_c, _ = eng_c.can_mutate_state("candidate-c", host_generation=3)
        self.assertTrue(can_c)

    def test_05_corrupt_recovery_telemetry_fails_closed(self):
        """Corrupt telemetry file returns STATE_CORRUPT."""
        tel_file = self.test_dir / "events" / "host-survival" / "external_safe_telemetry.json"
        tel_file.parent.mkdir(parents=True, exist_ok=True)
        tel_file.write_text("MALFORMED_JSON", encoding="utf-8")

        st, _ = self.sentinel.classify_host_health()
        self.assertEqual(st, HostHealthStatus.STATE_CORRUPT)

    def test_06_hot_plug_worker_registration_and_deregistration(self):
        """Hot-plug workers can be registered, queried, and unregistered safely."""
        w1 = self.registry.register_worker(
            worker_id="CODEX_2",
            provider="OPENAI",
            capabilities=["CODE_REVIEW", "ADVERSARIAL_TEST"],
            role="REVIEWER",
        )
        self.assertEqual(w1.worker_id, "CODEX_2")
        self.assertEqual(w1.spend_limit_eur, 0.0)

        # Find matching workers
        testers = self.registry.get_available_workers_for_capability("ADVERSARIAL_TEST")
        self.assertEqual(len(testers), 1)
        self.assertEqual(testers[0].worker_id, "CODEX_2")

        # Unregister worker
        unreg_ok = self.registry.unregister_worker("CODEX_2")
        self.assertTrue(unreg_ok)
        self.assertEqual(len(self.registry.get_available_workers_for_capability("ADVERSARIAL_TEST")), 0)


if __name__ == "__main__":
    unittest.main()
