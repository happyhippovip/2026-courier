#!/usr/bin/env python3
"""Acceptance Test Suite for Autonomous Operational Hygiene Controller."""

import datetime as dt
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.autonomous_operational_hygiene import (
    AutonomousOperationalHygiene,
    HygieneClassification,
    HygieneTelemetry,
)
from scripts.canonical_authority import AuthorityRecord, CanonicalAuthority, is_pid_alive
from scripts.live_worker_registry import AvailabilityClass, LiveWorkerRegistry, WorkerState


class TestAutonomousOperationalHygiene(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="hygiene_test_"))
        self.hygiene = AutonomousOperationalHygiene(repo_dir=self.test_dir)
        self.locks_dir = self.test_dir / "events" / "locks"
        self.claims_dir = self.test_dir / "events" / "opportunity-claims"
        self.alerts_dir = self.test_dir / "events" / "runtime-alerts"
        self.state_dir = self.test_dir / "events" / "runtime-state"
        self.worker_events_dir = self.test_dir / "events" / "worker-events"
        self.autonomy_dir = self.test_dir / "events" / "autonomy-runtime"

        for d in [self.locks_dir, self.claims_dir, self.alerts_dir, self.state_dir, self.worker_events_dir, self.autonomy_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_expired_lock_dead_owner_reconciled(self):
        # 1. Create synthetic expired lock with dead PID
        lock_file = self.locks_dir / "scope_test_module_12345678.json"
        now = dt.datetime.now(dt.timezone.utc)
        expired_ts = (now - dt.timedelta(hours=2)).isoformat()

        rec = AuthorityRecord(
            schema_version="1.0",
            scope="test/module",
            owner_id="DEAD_WORKER",
            task_id="TASK-OLD-01",
            generation=5,
            pid=99999999,  # Dead PID
            acquired_at=expired_ts,
            heartbeat_at=expired_ts,
            lease_expires_at=expired_ts,
        )
        lock_file.write_text(json.dumps(rec.to_dict()), encoding="utf-8")
        self.assertTrue(lock_file.exists())

        # 2. Run hygiene cycle
        telemetry = self.hygiene.perform_hygiene_cycle()

        # 3. Verify lock is reconciled and removed
        self.assertFalse(lock_file.exists())
        self.assertEqual(telemetry.stale_locks, 1)
        self.assertEqual(telemetry.hygiene_items_recovered, 1)
        self.assertEqual(telemetry.last_reconciliation_result, "PASS")

        # 4. Verify reconciliation event emitted
        events = list(self.worker_events_dir.glob("*.json"))
        self.assertGreaterEqual(len(events), 1)

    def test_02_live_owner_lock_never_displaced(self):
        # 1. Create synthetic lock with live PID (current process)
        lock_file = self.locks_dir / "scope_live_module_87654321.json"
        now = dt.datetime.now(dt.timezone.utc)
        future_ts = (now + dt.timedelta(minutes=15)).isoformat()

        rec = AuthorityRecord(
            schema_version="1.0",
            scope="live/module",
            owner_id="CURRENT_PROCESS",
            task_id="TASK-LIVE-01",
            generation=6,
            pid=os.getpid(),  # Live PID
            acquired_at=now.isoformat(),
            heartbeat_at=now.isoformat(),
            lease_expires_at=future_ts,
        )
        lock_file.write_text(json.dumps(rec.to_dict()), encoding="utf-8")
        self.assertTrue(lock_file.exists())

        # 2. Run hygiene cycle
        telemetry = self.hygiene.perform_hygiene_cycle()

        # 3. Verify live lock is untouched
        self.assertTrue(lock_file.exists())
        self.assertEqual(telemetry.stale_locks, 0)
        self.assertEqual(telemetry.hygiene_items_recovered, 0)

    def test_03_malformed_authority_record_fails_closed_and_alerts_once(self):
        # 1. Create corrupt lock record
        corrupt_file = self.locks_dir / "scope_corrupt_bad12345.json"
        corrupt_file.write_text("CORRUPTED_NOT_JSON{{{", encoding="utf-8")

        # 2. Run hygiene cycle
        telemetry = self.hygiene.perform_hygiene_cycle()

        # 3. Verify corrupt file is NOT deleted (fails closed)
        self.assertTrue(corrupt_file.exists())
        self.assertEqual(telemetry.hygiene_items_blocked, 1)
        self.assertEqual(telemetry.last_reconciliation_result, "BLOCKED_CORRUPTION_DETECTED")

        # 4. Verify Snitch alert emitted once
        alerts = list(self.alerts_dir.glob("*.json"))
        self.assertEqual(len(alerts), 1)
        alert_data = json.loads(alerts[0].read_text(encoding="utf-8"))
        self.assertEqual(alert_data["event_type"], "CORRUPT_AUTHORITY_RECORD")

        # 5. Second cycle must NOT duplicate alert
        self.hygiene.perform_hygiene_cycle()
        alerts_after = list(self.alerts_dir.glob("*.json"))
        self.assertEqual(len(alerts_after), 1)

    def test_04_stale_opportunity_claim_reconciled(self):
        claim_file = self.claims_dir / "OPP-TEST-01.claim.json"
        claim_file.write_text(json.dumps({
            "opportunity_id": "OPP-TEST-01",
            "pid": 99999999,  # Dead PID
            "claimed_at": "2026-09-01T00:00:00Z",
        }), encoding="utf-8")

        telemetry = self.hygiene.perform_hygiene_cycle()
        self.assertFalse(claim_file.exists())
        self.assertEqual(telemetry.stale_claims, 1)

    def test_05_expired_temporary_worker_and_false_running_reconciled(self):
        # 1. Worker with dead PID progressing
        w = self.hygiene.registry.register_worker("ORPHAN_BUILDER", "BUILDER", "ANTIGRAVITY", pid=99999999)
        w.state = WorkerState.PROGRESSING.value
        self.hygiene.registry._save_worker_record(w)

        # 2. Worker with expired 30-day temporary registration
        w_exp = self.hygiene.registry.register_worker(
            "CLI2", "SECONDARY", "ANTIGRAVITY_BEATA",
            availability_class=AvailabilityClass.TEMPORARY_30_DAY,
            available_duration_seconds=-100.0,
        )

        telemetry = self.hygiene.perform_hygiene_cycle()

        # Verify states reconciled
        w_reconciled = self.hygiene.registry.get_worker("ORPHAN_BUILDER")
        self.assertEqual(w_reconciled.state, WorkerState.ORPHANED.value)

        w_exp_reconciled = self.hygiene.registry.get_worker("CLI2")
        self.assertEqual(w_exp_reconciled.availability_class, AvailabilityClass.EXPIRED.value)
        self.assertEqual(w_exp_reconciled.state, WorkerState.UNKNOWN.value)


if __name__ == "__main__":
    unittest.main()
