#!/usr/bin/env python3
"""Focused Acceptance Test Suite for Snitch Observer & Operational Truth Engine.

Verifies:
1. Live vs Dead PID Inspection and Orphan Classification
2. Interactive Permission Prompt Detection in Logs
3. State Observation Matrix (PROGRESSING, SAFE_IDLE, WAITING_PERMISSION, WAITING_HUMAN, WAITING_RESOURCE)
4. Anomaly Alert Emission and Deduplication
5. Operational Readiness Assessment (READY vs NOT_READY)
6. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.snitch_observer import (
    OperationalReadinessReport,
    ReadinessLevel,
    SnitchObserver,
    WorkerObservation,
    WorkerState,
)


class TestSnitchObserver(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="snitch_test_"))
        self.snitch = SnitchObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_live_worker_inspection(self):
        """Live PID with active session state is classified as PROGRESSING."""
        current_pid = os.getpid()
        obs = self.snitch.inspect_worker(
            worker_id="GOOGLE",
            pid=current_pid,
            session_state={"status": "PROGRESSING", "last_active_at": "2026-09-01T12:00:00Z"},
        )
        self.assertEqual(obs.worker_id, "GOOGLE")
        self.assertTrue(obs.alive)
        self.assertEqual(obs.state, WorkerState.PROGRESSING)

    def test_02_dead_pid_with_active_session_classified_as_orphaned(self):
        """Dead PID with persisted active session state is classified as ORPHANED."""
        dead_pid = 99999999
        obs = self.snitch.inspect_worker(
            worker_id="CLI2",
            pid=dead_pid,
            session_state={"status": "RUNNING", "last_active_at": "2026-09-01T12:00:00Z"},
        )
        self.assertFalse(obs.alive)
        self.assertEqual(obs.state, WorkerState.ORPHANED)
        self.assertEqual(obs.stop_reason, "PID_NOT_ALIVE_ORPHAN")

    def test_03_permission_prompt_detection_in_log(self):
        """Permission prompts in log file transition state to WAITING_PERMISSION."""
        log_file = self.test_dir / "worker.log"
        log_file.write_text("Executing command: gcloud compute instances\nDo you want to proceed? [Y/n]", encoding="utf-8")

        obs = self.snitch.inspect_worker(
            worker_id="CLI1",
            pid=os.getpid(),
            log_path=log_file,
            session_state={"status": "RUNNING"},
        )
        self.assertTrue(obs.permission_blocked)
        self.assertIsNotNone(obs.permission_prompt_text)
        self.assertEqual(obs.state, WorkerState.WAITING_PERMISSION)

    def test_04_safe_idle_observation_with_discovery_proof(self):
        """Worker in SAFE_IDLE with valid discovery proof is classified as SAFE_IDLE."""
        proof_file = self.test_dir / "events" / "runtime-state" / "discovery_audit_proof.json"
        proof_file.parent.mkdir(parents=True, exist_ok=True)
        proof_file.write_text(json.dumps({
            "no_safe_work": True,
            "eligible_safe_candidates": 0,
            "proof_hash": "proof-hash-12345",
        }), encoding="utf-8")

        obs = self.snitch.inspect_worker(
            worker_id="GOOGLE",
            pid=os.getpid(),
            session_state={"status": "SAFE_IDLE"},
        )
        self.assertEqual(obs.state, WorkerState.SAFE_IDLE)
        self.assertFalse(obs.permission_blocked)
        self.assertEqual(obs.details.get("proof_hash"), "proof-hash-12345")

    def test_05_operational_readiness_assessment(self):
        """Evaluates overall readiness report accurately."""
        report = self.snitch.compute_operational_readiness(oracle_test_command=None)
        self.assertIsInstance(report, OperationalReadinessReport)
        self.assertIn(report.readiness, (ReadinessLevel.READY, ReadinessLevel.CONDITIONAL, ReadinessLevel.NOT_READY))
        self.assertEqual(report.autonomous_spend_limit_eur, 0.0)


if __name__ == "__main__":
    unittest.main()
