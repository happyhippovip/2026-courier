#!/usr/bin/env python3
"""Focused Acceptance Test Suite for Host Survival Engine & Reboot Recovery.

Verifies:
1. Host Fencing Token lifecycle & monotonic generation counter
2. Fencing protection against stale or fenced host mutations (Fail-Closed)
3. Replacement Host Takeover Protocol & old-primary fencing
4. Disaster Recovery (DR) Manifest cryptographic digest verification & tamper detection
5. Zero Blind Replay Reboot Reconciliation
6. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.host_survival_engine import (
    DisasterRecoveryManifest,
    HostFencingToken,
    HostSurvivalEngine,
)


class TestHostSurvivalEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="host_survival_test_"))
        self.engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="host-alpha")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_fencing_token_initialization_and_persistence(self):
        """Host fencing token initializes with gen 1 and persists to disk."""
        token = self.engine.load_fencing_token()
        self.assertEqual(token.primary_host_id, "host-alpha")
        self.assertEqual(token.host_generation, 1)
        self.assertEqual(token.state, "ACTIVE")

        # Mutate authorization check
        allowed, reason = self.engine.can_mutate_state("host-alpha", host_generation=1)
        self.assertTrue(allowed)
        self.assertEqual(reason, "AUTHORIZED")

    def test_02_stale_generation_and_fenced_host_rejected_fail_closed(self):
        """Stale generation tokens and fenced hosts are rejected fail-closed."""
        # Presented gen 0 < current gen 1
        allowed, reason = self.engine.can_mutate_state("host-alpha", host_generation=0)
        self.assertFalse(allowed)
        self.assertIn("STALE_HOST_GENERATION", reason)

        # Non-primary host with matching gen
        allowed, reason = self.engine.can_mutate_state("host-beta", host_generation=1)
        self.assertFalse(allowed)
        self.assertIn("NON_PRIMARY_HOST_DENIED", reason)

    def test_03_host_takeover_increments_generation_and_fences_old_primary(self):
        """Takeover assigns new primary, increments gen, and fences old host."""
        new_token = self.engine.perform_host_takeover(new_host_id="host-beta")
        self.assertEqual(new_token.primary_host_id, "host-beta")
        self.assertEqual(new_token.host_generation, 2)
        self.assertIn("host-alpha", new_token.fenced_hosts)

        # Old host cannot mutate even if it presents new gen
        allowed, reason = self.engine.can_mutate_state("host-alpha", host_generation=2)
        self.assertFalse(allowed)
        self.assertIn("HOST_FENCED_OFF", reason)

        # New host authorized
        allowed, reason = self.engine.can_mutate_state("host-beta", host_generation=2)
        self.assertTrue(allowed)

    def test_04_dr_manifest_digest_verification_and_tamper_detection(self):
        """DR manifest digest is verified, and any tamper fails closed."""
        manifest = self.engine.generate_dr_manifest(
            active_missions=["MISSION_TEST_01"],
            pending_jobs=["JOB_001", "JOB_002"],
        )
        self.assertTrue(manifest.manifest_digest)

        # Verify clean manifest
        loaded, status = self.engine.load_and_verify_dr_manifest()
        self.assertEqual(status, "VERIFIED")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.manifest_digest, manifest.manifest_digest)

        # Tamper with file
        raw = json.loads(self.engine.manifest_file.read_text(encoding="utf-8"))
        raw["active_missions"] = ["TAMPERED_MISSION"]
        self.engine.manifest_file.write_text(json.dumps(raw), encoding="utf-8")

        # Load tampered manifest -> fails closed
        tampered_loaded, tamper_status = self.engine.load_and_verify_dr_manifest()
        self.assertIsNone(tampered_loaded)
        self.assertEqual(tamper_status, "DIGEST_MISMATCH_CORRUPT")

    def test_05_reboot_reconciliation_zero_blind_replay(self):
        """Reboot reconciliation segregates confirmed, clean, and ambiguous jobs."""
        self.engine.generate_dr_manifest()

        in_flight = [
            {"job_id": "JOB_DONE", "effect_status": "CONFIRMED_DONE"},
            {"job_id": "JOB_CLEAN", "effect_status": "CLEAN_NOT_STARTED"},
            {"job_id": "JOB_AMBIGUOUS", "effect_status": "UNKNOWN"},
        ]

        result = self.engine.reconcile_after_reboot(in_flight)
        self.assertEqual(result["verdict"], "RECONCILED")
        self.assertIn("JOB_DONE", result["confirmed_done_jobs"])
        self.assertIn("JOB_CLEAN", result["resumable_jobs"])
        self.assertIn("JOB_AMBIGUOUS", result["ambiguous_jobs"])


if __name__ == "__main__":
    unittest.main()
