#!/usr/bin/env python3
"""Mission 215 Acceptance Test Suite: Goal-Driven Autonomous Engineering (Google Primary Builder).

Verifies:
1. Queue empty -> Goal-driven scan starts automatically -> discovers evidence-backed engineering candidate
2. Candidate passes safety gate -> executes candidate -> verifies result -> continues with no WEITER
3. Queue empty + genuinely no candidates -> SAFE_IDLE_AFTER_FULL_DISCOVERY with cryptographic proof
4. SAFE_IDLE without discovery proof -> Snitch PREMATURE_IDLE detection & alert emission
5. 100% Deterministic (0 Model Calls, 0 EUR Spend)
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
from scripts.goal_driven_discovery_engine import GoalDrivenDiscoveryEngine
from scripts.snitch_observer import SnitchObserver


class TestMission215GoalDrivenAutonomousEngineering(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_215_test_"))
        self.dispatcher = ContinuousSafeWorkDispatcher(repo_dir=self.test_dir)
        self.goal_engine = GoalDrivenDiscoveryEngine(repo_dir=self.test_dir)
        self.snitch = SnitchObserver(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_goal_driven_discovery_from_repository_evidence(self):
        """When ordinary queue is empty, goal-driven discovery finds evidence-backed task and executes it."""
        self.assertEqual(len(self.dispatcher.tasks), 0)

        # Ensure DR manifest & HQ snapshot exist
        state_dir = self.test_dir / "events" / "runtime-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "disaster_recovery_manifest.json").write_text(
            json.dumps({"manifest_digest": "valid_digest", "covered_paths": ["events"]}),
            encoding="utf-8",
        )
        (state_dir / "hq_telemetry_snapshot.json").write_text(
            json.dumps({"visual_state": "ALL_SYSTEMS_OPERATIONAL"}),
            encoding="utf-8",
        )

        # Inject real repository gap: dead lock in events/locks
        locks_dir = self.test_dir / "events" / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        dead_lock = locks_dir / "stale_heavy_job.json"
        dead_lock.write_text(
            json.dumps({"owner_id": "dead_worker", "pid": 9999999, "acquired_at": "2026-09-01T00:00:00Z"}),
            encoding="utf-8",
        )

        executed_tasks = []

        def safe_runner(t: DispatchableTask):
            executed_tasks.append(t.task_id)
            if t.task_id == "TASK-GOAL-PRUNE-DEAD-LOCKS":
                dead_lock.unlink(missing_ok=True)
            return True, {"pruned": True}

        # Dispatch cycle: automatically triggers goal-driven scan, enqueues, and executes!
        ev = self.dispatcher.dispatch_next_safe_cycle(runner_fn=safe_runner)

        self.assertEqual(ev.action, "EXECUTED")
        self.assertIn("TASK-GOAL-PRUNE-DEAD-LOCKS", executed_tasks)
        self.assertFalse(dead_lock.exists())

    def test_02_safe_idle_after_full_discovery_with_cryptographic_proof(self):
        """When queue is empty and goal discovery finds no gaps, declares SAFE_IDLE_AFTER_FULL_DISCOVERY."""
        # Ensure DR manifest exists so no bootstrap needed
        survival_dir = self.test_dir / "events" / "host-survival"
        survival_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = survival_dir / "disaster_recovery_manifest.json"
        manifest_file.write_text(
            json.dumps(
                {
                    "manifest_digest": "abcdef1234567890",
                    "confirmed_state_hashes": {"state": "abc"},
                    "generated_at": "2026-09-01T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        state_dir = self.test_dir / "events" / "runtime-state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Ensure HQ snapshot exists
        snap_file = state_dir / "hq_telemetry_snapshot.json"
        snap_file.write_text(
            json.dumps({"visual_state": "ALL_SYSTEMS_OPERATIONAL", "updated_at": "2026-09-01T00:00:00Z"}),
            encoding="utf-8",
        )

        ev = self.dispatcher.dispatch_next_safe_cycle()
        self.assertEqual(ev.action, "ENTERED_SAFE_IDLE")

        # Verify cryptographic proof file was written to disk
        proof_file = state_dir / "discovery_audit_proof.json"
        self.assertTrue(proof_file.exists())
        proof_data = json.loads(proof_file.read_text(encoding="utf-8"))
        self.assertEqual(proof_data["queue_scan"], "EMPTY")
        self.assertEqual(proof_data["goal_driven_scan"], "COMPLETED")
        self.assertEqual(proof_data["eligible_safe_candidates"], 0)
        self.assertTrue(proof_data["no_safe_work"])
        self.assertTrue(len(proof_data["proof_hash"]) > 0)

        # Snitch verifies SAFE_IDLE with valid proof
        obs = self.snitch.inspect_worker(
            worker_id="GOOGLE",
            pid=os.getpid(),
            session_state={"status": "SAFE_IDLE"},
        )
        self.assertEqual(obs.state, self.snitch.WorkerState.SAFE_IDLE if hasattr(self.snitch, "WorkerState") else "SAFE_IDLE")
        self.assertEqual(obs.details.get("status"), "SAFE_IDLE_AFTER_FULL_DISCOVERY")

    def test_03_snitch_detects_premature_idle_without_proof(self):
        """Snitch classifies worker as PREMATURE_IDLE if reporting SAFE_IDLE without discovery proof."""
        # Ensure proof file does NOT exist
        proof_file = self.test_dir / "events" / "runtime-state" / "discovery_audit_proof.json"
        proof_file.unlink(missing_ok=True)

        obs = self.snitch.inspect_worker(
            worker_id="GOOGLE",
            pid=os.getpid(),
            session_state={"status": "SAFE_IDLE"},
        )
        self.assertEqual(obs.state.value if hasattr(obs.state, "value") else str(obs.state), "PREMATURE_IDLE")
        self.assertEqual(obs.stop_reason, "PREMATURE_IDLE_MISSING_DISCOVERY_PROOF")

        # Verify alert was emitted to events/anomalies
        alerts = list((self.test_dir / "events" / "anomalies").glob("snitch_alert_*.json"))
        self.assertGreater(len(alerts), 0)

    def test_04_continuous_goal_driven_batch_run(self):
        """Executes full multi-step goal-driven loop continuously without WEITER."""
        # Inject two gaps
        locks_dir = self.test_dir / "events" / "locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        (locks_dir / "dead_lock_1.json").write_text(
            json.dumps({"owner_id": "dead_1", "pid": 9999991, "acquired_at": "2026-09-01T00:00:00Z"}),
            encoding="utf-8",
        )

        state_dir = self.test_dir / "events" / "runtime-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # Ensure DR manifest missing so DR bootstrap candidate is discovered

        completed = []

        def runner(t: DispatchableTask):
            completed.append(t.task_id)
            if t.task_id == "TASK-GOAL-PRUNE-DEAD-LOCKS":
                for f in locks_dir.glob("*.json"):
                    f.unlink(missing_ok=True)
            elif t.task_id == "TASK-GOAL-DR-BOOTSTRAP":
                (state_dir / "disaster_recovery_manifest.json").write_text(
                    json.dumps({"manifest_digest": "dummy", "covered_paths": ["events"]}),
                    encoding="utf-8",
                )
            return True, {"batch_step": "pass"}

        summary = self.dispatcher.run_continuous_backlog_batch(
            worker_id="GOOGLE",
            max_tasks=5,
            runner_fn=runner,
        )

        self.assertGreaterEqual(summary["tasks_completed"], 1)
        self.assertEqual(summary["model_calls"], 0)
        self.assertEqual(summary["spend_eur"], 0.0)


if __name__ == "__main__":
    unittest.main()
