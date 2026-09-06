#!/usr/bin/env python3
"""Targeted Unit Test Suite for Automatic Deterministic Result Handoff."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.automatic_result_handoff import (
    AutomaticResultHandoff,
    HandoffSignal,
    WorkerResultEnvelope,
)
from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState


class TestAutomaticResultHandoff(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="handoff_test_"))
        self.handoff = AutomaticResultHandoff(repo_dir=self.test_dir)
        self.registry = self.handoff.registry
        self.events_dir = self.test_dir / "events" / "worker-events"
        self.alerts_dir = self.test_dir / "events" / "runtime-alerts"
        self.results_dir = self.test_dir / "events" / "results"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_google_completion_to_candidate_signal(self):
        self.registry.register_worker("GOOGLE", "PRIMARY_BUILDER", "ANTIGRAVITY", mission_id="M204")
        self.registry.record_progress("GOOGLE", {"step": "active"})

        res = {
            "worker": "GOOGLE",
            "mission": "M204",
            "state": "COMPLETED",
            "candidate_fingerprint": "c1a2b3c4d5e6",
            "severity": "INFO",
            "ready_for_next": True,
            "next": "CLI2_ADVERSARIAL_REVIEW",
        }

        sig, reason = self.handoff.ingest_and_route_result(res)
        self.assertEqual(sig, HandoffSignal.GOOGLE_CANDIDATE_AVAILABLE)
        self.assertEqual(self.handoff.active_google_candidate, "c1a2b3c4d5e6")

        # Worker registry state must be updated
        google_worker = self.registry.get_worker("GOOGLE")
        self.assertIn(google_worker.state, (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value))

    def test_02_cli2_high_defect_to_release_blocker(self):
        self.registry.register_worker("CLI2", "SECONDARY_AUTONOMOUS_WORKER", "ANTIGRAVITY_BEATA", mission_id="M205")

        res = {
            "worker": "CLI2",
            "mission": "M205",
            "state": "COMPLETED",
            "new_high": True,
            "severity": "HIGH",
            "block_reason": "Data race on concurrent session token refresh",
            "tests": {"passed": 12, "failed": 1},
        }

        sig, reason = self.handoff.ingest_and_route_result(res)
        self.assertEqual(sig, HandoffSignal.RELEASE_BLOCKER_FOUND)

        # Alert must be present in runtime-alerts
        alerts = list(self.alerts_dir.glob("*.json"))
        self.assertGreaterEqual(len(alerts), 1)

    def test_03_cli2_pass_matching_candidate_to_final_acceptance_ready(self):
        # 1. Ingest Google Candidate
        self.registry.register_worker("GOOGLE", "BUILDER", "ANTIGRAVITY")
        self.handoff.ingest_and_route_result({
            "worker": "GOOGLE",
            "mission": "M204",
            "state": "COMPLETED",
            "candidate_fingerprint": "cand-hash-999",
        })

        # 2. CLI2 passes adversarial test on same candidate
        self.registry.register_worker("CLI2", "WORKER", "ANTIGRAVITY_BEATA")
        res_cli2 = {
            "worker": "CLI2",
            "mission": "M205",
            "state": "COMPLETED",
            "target_fingerprint": "cand-hash-999",
            "new_high": False,
            "tests": {"passed": 45, "failed": 0},
            "ready_for_next": True,
        }

        sig, reason = self.handoff.ingest_and_route_result(res_cli2)
        self.assertEqual(sig, HandoffSignal.FINAL_ACCEPTANCE_READY)

    def test_04_mismatched_candidate_fingerprint_suppression(self):
        # Google produces cand-AAA
        self.handoff.ingest_and_route_result({
            "worker": "GOOGLE", "mission": "M204", "state": "COMPLETED",
            "candidate_fingerprint": "cand-AAA",
        })

        # CLI2 tested obsolete cand-BBB
        res_mismatch = {
            "worker": "CLI2", "mission": "M205", "state": "COMPLETED",
            "target_fingerprint": "cand-BBB", "new_high": False,
        }

        sig, reason = self.handoff.ingest_and_route_result(res_mismatch)
        # Mismatched target must NOT trigger final acceptance!
        self.assertEqual(sig, HandoffSignal.NO_ACTION)
        self.assertEqual(reason, "MISMATCHED_TARGET_FINGERPRINT")

    def test_05_codex_release_to_release_accepted(self):
        self.registry.register_worker("CODEX", "CHIEF_ORACLE", "OPENAI_CODEX")

        res = {
            "worker": "CODEX",
            "mission": "M207",
            "state": "RELEASE",
            "severity": "INFO",
            "ready_for_next": True,
        }

        sig, reason = self.handoff.ingest_and_route_result(res)
        self.assertEqual(sig, HandoffSignal.RELEASE_ACCEPTED)

    def test_06_codex_remediate_to_remediation_required(self):
        self.registry.register_worker("CODEX", "CHIEF_ORACLE", "OPENAI_CODEX")

        res = {
            "worker": "CODEX",
            "mission": "M207",
            "state": "REMEDIATE",
            "severity": "HIGH",
            "block_reason": "Security boundary verification failed on node B",
        }

        sig, reason = self.handoff.ingest_and_route_result(res)
        self.assertEqual(sig, HandoffSignal.REMEDIATION_REQUIRED)

    def test_07_execution_surface_block_detection(self):
        res = {
            "worker": "CLI2",
            "mission": "M205",
            "state": "FAILED",
            "execution_surface_block": True,
            "block_reason": "Headless Godot renderer missing OpenGL context",
            "severity": "HIGH",
        }

        sig, reason = self.handoff.ingest_and_route_result(res)
        self.assertEqual(sig, HandoffSignal.EXECUTION_SURFACE_BLOCK)

    def test_08_duplicate_result_and_fast_path(self):
        res_file = self.results_dir / "res-01.json"
        res_payload = {
            "worker": "GOOGLE",
            "mission": "M204",
            "state": "COMPLETED",
            "candidate_fingerprint": "hash-12345",
        }
        res_file.write_text(json.dumps(res_payload), encoding="utf-8")

        # Ingest first time
        sig1, _ = self.handoff.ingest_and_route_result(res_payload, source_file=res_file)
        self.assertEqual(sig1, HandoffSignal.GOOGLE_CANDIDATE_AVAILABLE)

        # Ingest second time (fast path stat check)
        sig2, reason2 = self.handoff.ingest_and_route_result(res_payload, source_file=res_file)
        self.assertEqual(sig2, HandoffSignal.NO_ACTION)
        self.assertEqual(reason2, "FAST_PATH_UNCHANGED")
        self.assertEqual(self.handoff.telemetry["duplicates_suppressed"], 1)
        self.assertEqual(self.handoff.telemetry["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
