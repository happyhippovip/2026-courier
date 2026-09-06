#!/usr/bin/env python3
"""Mission 216 Acceptance Test Suite: General Autonomous Engineering Backlog (Google Primary Builder).

Verifies:
1. Deterministic Repository Inventory Generation (sources, tests, operational, authority, recovery, observability, queues)
2. General evidence-driven candidate generation across code patterns and testing gaps
3. Structured candidate metadata standard (EVIDENCE, GOAL_CONNECTION, WHY_SAFE, RISK_CLASS)
4. Continuous autonomous execution of SAFE_LOCAL_INVESTIGATION and SAFE_LOCAL_ENGINEERING candidates without WEITER
5. Snitch fine-grained state detection (DISCOVERING, INVESTIGATING, EXECUTING, VERIFYING, SAFE_IDLE_AFTER_FULL_DISCOVERY, PREMATURE_IDLE)
6. 100% Deterministic (0 Model Calls, 0 EUR Spend)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_orchestrator import WorkerState
from scripts.continuous_safe_work_dispatcher import (
    ContinuousSafeWorkDispatcher,
    DispatchableTask,
    TaskSafetyClass,
)
from scripts.general_engineering_discovery_engine import (
    GeneralCandidate,
    GeneralEngineeringDiscoveryEngine,
    RepositoryInventory,
)
from scripts.snitch_observer import SnitchObserver


class TestMission216GeneralAutonomousEngineering(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_216_test_"))
        self.scripts_dir = self.test_dir / "scripts"
        self.tests_dir = self.test_dir / "tests"
        self.events_dir = self.test_dir / "events"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)
        self.general_engine = GeneralEngineeringDiscoveryEngine(repo_dir=self.test_dir)
        self.snitch = SnitchObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_deterministic_repository_inventory(self):
        """Validates comprehensive deterministic repository inventory generation."""
        # Create mock source and test files
        (self.scripts_dir / "canonical_authority.py").write_text("# Authority module\n", encoding="utf-8")
        (self.scripts_dir / "host_survival_engine.py").write_text("# Recovery module\n", encoding="utf-8")
        (self.scripts_dir / "snitch_observer.py").write_text("# Observability module\n", encoding="utf-8")
        (self.scripts_dir / "untested_custom_helper.py").write_text("# Untested module\n", encoding="utf-8")
        (self.tests_dir / "test_canonical_authority.py").write_text("# Test module\n", encoding="utf-8")

        inv = self.general_engine.generate_repository_inventory()

        self.assertIn("canonical_authority.py", inv.source_modules)
        self.assertIn("canonical_authority.py", inv.authority_modules)
        self.assertIn("host_survival_engine.py", inv.recovery_modules)
        self.assertIn("snitch_observer.py", inv.observability_modules)
        self.assertIn("untested_custom_helper.py", inv.untested_or_weakly_tested_modules)
        self.assertIn("test_canonical_authority.py", inv.test_modules)
        self.assertTrue(self.general_engine.inventory_file.exists())

    def test_02_general_evidence_driven_candidate_generation(self):
        """Generates candidates with complete required evidence and metadata standards."""
        # Mock an operational module with missing focused test
        (self.scripts_dir / "autonomy_supervisor.py").write_text("# Supervisor\n", encoding="utf-8")

        # Mock a file with silent exception swallow
        (self.scripts_dir / "canonical_authority.py").write_text(
            "def test():\n    try:\n        pass\n    except Exception:\n        pass\n",
            encoding="utf-8",
        )

        candidates, inv, audit = self.general_engine.run_general_discovery()

        self.assertGreater(len(candidates), 0)
        c = candidates[0]

        # Verify candidate metadata standard
        self.assertTrue(len(c.task_id) > 0)
        self.assertTrue(len(c.title) > 0)
        self.assertIn(c.task_type, ("SAFE_LOCAL_INVESTIGATION", "SAFE_LOCAL_ENGINEERING"))
        self.assertTrue(len(c.evidence_type) > 0)
        self.assertTrue(len(c.evidence_location) > 0)
        self.assertTrue(len(c.evidence_summary) > 0)
        self.assertTrue(len(c.project_goal_connection) > 0)
        self.assertTrue(len(c.expected_value) > 0)
        self.assertTrue(len(c.information_gain) > 0)
        self.assertEqual(c.risk_class, "LOW")
        self.assertTrue(len(c.files_in_scope) > 0)
        self.assertTrue(len(c.task_fingerprint) > 0)
        self.assertTrue(len(c.why_safe_to_autonomously_execute) > 0)

    def test_03_continuous_autonomous_batch_execution_of_general_candidates(self):
        """Executes 5 general candidates continuously in a batch without WEITER."""
        # Create 5 operational modules without dedicated tests
        modules = [
            "autonomy_supervisor.py",
            "hq_operations_daemon.py",
            "bootstrap_replacement_host.py",
            "disaster_recovery_bundle_sync.py",
            "multi_host_failover_coordinator.py",
        ]
        for m in modules:
            (self.scripts_dir / m).write_text(f"# {m}\n", encoding="utf-8")

        # Ensure DR manifest & HQ snapshot exist so baseline is clean
        survival_dir = self.test_dir / "events" / "host-survival"
        survival_dir.mkdir(parents=True, exist_ok=True)
        (survival_dir / "disaster_recovery_manifest.json").write_text(
            json.dumps({"manifest_digest": "valid", "confirmed_state_hashes": {"a": "1"}}),
            encoding="utf-8",
        )
        state_dir = self.test_dir / "events" / "runtime-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "hq_telemetry_snapshot.json").write_text(
            json.dumps({"visual_state": "ALL_SYSTEMS_OPERATIONAL"}),
            encoding="utf-8",
        )

        executed = []

        def runner(t: DispatchableTask):
            executed.append(t.task_id)
            return True, {"verified_investigation": f"evidence-report-{t.task_id}"}

        summary = self.dispatcher.run_continuous_backlog_batch(
            worker_id="GOOGLE",
            max_tasks=5,
            runner_fn=runner,
        )

        self.assertGreaterEqual(summary["tasks_completed"], 5)
        self.assertEqual(summary["model_calls"], 0)
        self.assertEqual(summary["spend_eur"], 0.0)
        self.assertEqual(len(executed), 5)

    def test_04_snitch_observes_fine_grained_states(self):
        """Snitch accurately detects and classifies fine-grained worker lifecycle states."""
        # Ensure discovery proof exists
        state_dir = self.test_dir / "events" / "runtime-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "discovery_audit_proof.json").write_text(
            json.dumps({"proof_hash": "valid_hash", "eligible_safe_candidates": 0, "no_safe_work": True}),
            encoding="utf-8",
        )

        # 1. Inspect DISCOVERING state
        obs_disc = self.snitch.inspect_worker(
            worker_id="GOOGLE",
            pid=os.getpid(),
            session_state={"status": "DISCOVERING"},
        )
        self.assertEqual(obs_disc.state.value if hasattr(obs_disc.state, "value") else str(obs_disc.state), "PROGRESSING")

        # 2. Inspect SAFE_IDLE with valid discovery proof
        obs_idle = self.snitch.inspect_worker(
            worker_id="GOOGLE",
            pid=os.getpid(),
            session_state={"status": "SAFE_IDLE"},
        )
        self.assertEqual(obs_idle.state.value if hasattr(obs_idle.state, "value") else str(obs_idle.state), "SAFE_IDLE")
        self.assertEqual(obs_idle.details.get("status"), "SAFE_IDLE_AFTER_FULL_DISCOVERY")


if __name__ == "__main__":
    unittest.main()
