#!/usr/bin/env python3
"""Test suite for run_cli1_incident_recovery."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_cli1_incident_recovery import run_cli1_incident_recovery


class TestCLI1IncidentRecovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="recovery_test_"))
        # Setup mock ledger
        ledger_dir = self.test_dir / "events" / "revenue-opportunities"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        (ledger_dir / "canonical_revenue_ledger.json").write_text(json.dumps({"opportunities": {}}))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_incident_recovery_execution(self):
        """Verifies automated incident detection, orphan reclamation, and failover to alternate worker."""
        res = run_cli1_incident_recovery(
            error_id="test-incident-error-1234",
            failed_worker_id="CLI1",
            repo_dir=self.test_dir,
        )
        self.assertEqual(res["status"], "REAL_CRASH_RECOVERY_PASS")
        self.assertEqual(res["worker_failure_detected"], "PASS")
        self.assertEqual(res["stale_claim_recovered"], "PASS")
        self.assertEqual(res["duplicate_side_effects"], 0)
        self.assertEqual(res["human_intervention_count"], 0)
        self.assertEqual(res["weiter_count"], 0)


if __name__ == "__main__":
    unittest.main()
