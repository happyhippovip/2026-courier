#!/usr/bin/env python3
"""Acceptance Tests for Host Survival Layer & Infinite Life (2026-Projektzentrale)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_replacement_host import bootstrap_replacement_host
from scripts.host_survival_engine import (
    DisasterRecoveryManifest,
    HostFencingToken,
    HostSurvivalEngine,
)


class TestHostSurvivalLayer(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="host_survival_test_"))
        self.engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="home-mac-primary")
        self.engine.generate_dr_manifest()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_dr_manifest_creation_and_cryptographic_verification(self):
        """DR manifest is created with matching SHA-256 digest; verified successfully."""
        manifest, status = self.engine.load_and_verify_dr_manifest()
        self.assertEqual(status, "VERIFIED")
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.host_id, "home-mac-primary")
        self.assertEqual(manifest.survival_level, 2)

    def test_02_corrupt_recovery_manifest_fails_closed(self):
        """Tampered or truncated manifest fails cryptographic verification fail-closed."""
        man_path = self.test_dir / "events" / "host-survival" / "disaster_recovery_manifest.json"
        data = json.loads(man_path.read_text(encoding="utf-8"))
        data["host_id"] = "TAMPERED_HOST_ID"  # Tamper without updating digest
        man_path.write_text(json.dumps(data), encoding="utf-8")

        manifest, status = self.engine.load_and_verify_dr_manifest()
        self.assertIsNone(manifest)
        self.assertEqual(status, "DIGEST_MISMATCH_CORRUPT")

    def test_03_reboot_reconciliation_zero_blind_replay_of_ambiguous_effects(self):
        """Ambiguous in-flight jobs are routed to WAITING_HUMAN; clean jobs are resumed."""
        in_flight = [
            {"job_id": "job-clean-1", "effect_status": "CLEAN_NOT_STARTED"},
            {"job_id": "job-done-1", "effect_status": "CONFIRMED_DONE"},
            {"job_id": "job-ambiguous-1", "effect_status": "UNKNOWN"},
        ]
        rec = self.engine.reconcile_after_reboot(in_flight)
        self.assertEqual(rec["verdict"], "RECONCILED")
        self.assertIn("job-clean-1", rec["resumable_jobs"])
        self.assertIn("job-done-1", rec["confirmed_done_jobs"])
        self.assertIn("job-ambiguous-1", rec["ambiguous_jobs"])

    def test_04_host_generation_fencing_blocks_stale_generations(self):
        """Lower generation tokens are strictly denied write authorization."""
        can_write, _ = self.engine.can_mutate_state(host_id="home-mac-primary", host_generation=1)
        self.assertTrue(can_write)

        # Stale generation 0 should be rejected
        can_stale, reason = self.engine.can_mutate_state(host_id="home-mac-primary", host_generation=0)
        self.assertFalse(can_stale)
        self.assertIn("STALE_HOST_GENERATION", reason)

    def test_05_replacement_host_takeover_and_old_primary_fencing(self):
        """When replacement host bootstraps, old primary is fenced off and denied mutations."""
        res = bootstrap_replacement_host(new_host_id="replacement-node-02", repo_dir=self.test_dir)
        self.assertEqual(res["bootstrap_verdict"], "SUCCESS")
        self.assertEqual(res["new_generation"], 2)
        self.assertIn("home-mac-primary", res["fenced_hosts"])

        # Old primary tries to write with old generation
        can_old, reason_old = self.engine.can_mutate_state(host_id="home-mac-primary", host_generation=1)
        self.assertFalse(can_old)
        self.assertIn("HOST_FENCED_OFF", reason_old)

    def test_06_corrupt_fencing_token_fails_closed(self):
        """Zero-byte or corrupted fencing token blocks all write authority fail-closed."""
        fence_file = self.test_dir / "events" / "host-survival" / "host_fencing_token.json"
        fence_file.write_text("", encoding="utf-8")  # Zero-byte corruption

        can_write, reason = self.engine.can_mutate_state(host_id="home-mac-primary", host_generation=1)
        self.assertFalse(can_write)
        self.assertIn("FENCING_STATE_CORRUPT_FAIL_CLOSED", reason)

    def test_07_resilience_improvement_queue_zero_new_spend(self):
        """Resilience queue contains infra proposals with strict 0 EUR autonomous spend limit."""
        proposals = self.engine.generate_resilience_queue()
        self.assertGreaterEqual(len(proposals), 3)
        for p in proposals:
            self.assertEqual(p["status"], "PROPOSAL_PENDING_CHIEF_APPROVAL")
            self.assertTrue(p["requires_chief_approval"])

    def test_08_sentinel_interface_specification_generation(self):
        """Sentinel interface specification generated with valid health probe endpoints."""
        spec = self.engine.generate_sentinel_spec()
        self.assertEqual(spec["schema_version"], "SENTINEL_INTERFACE_V1")
        self.assertIn("http://127.0.0.1:8765/health", spec["health_probe_endpoints"])


if __name__ == "__main__":
    unittest.main()
