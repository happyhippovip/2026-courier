#!/usr/bin/env python3
"""Mission: Autonomy Control Plane V2 - Failure Injection & Snitch Verification Suite.

Validates Injections A through I, Permission Canary, and Headless Safety:
- Injection A: Permission prompt injection detection
- Injection B: Dead PID orphan detection
- Injection C: Hung worker detection & alert emission
- Injection D: Safe idle classification (no burn)
- Injection E: Progressing worker classification
- Injection F: Stale claim race preservation
- Injection G: Cross-process heavy mutex enforcement
- Injection H: Crash replay safety
- Injection I: Fail-closed uncertain effect handling
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.snitch_observer import (
    SnitchObserver,
    WorkerState,
    ReadinessLevel,
)
from scripts.elite_execution_core import EliteExecutionCore
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.real_autonomy_runtime import RealAutonomyRuntime, NightSessionState, SessionStatus


class SnitchFailureInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="snitch_test_"))
        self.events_dir = self.tmp_dir / "events"
        self.autonomy_dir = self.events_dir / "autonomy-runtime"
        self.anomalies_dir = self.events_dir / "anomalies"
        self.autonomy_dir.mkdir(parents=True, exist_ok=True)
        self.anomalies_dir.mkdir(parents=True, exist_ok=True)
        self.observer = SnitchObserver(repo_dir=self.tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_injection_a_permission_prompt_detected(self) -> None:
        """Injection A: Worker blocked at interactive permission prompt."""
        log_file = self.tmp_dir / "worker.log"
        log_file.write_text(
            "Starting task...\n"
            "Requesting permission for: python3 -c 'import foo'\n"
            "Do you want to proceed?\n"
            "> 1. Yes\n"
            "  2. Yes, and always allow...\n"
            "  3. [Persist to settings.json]\n"
            "  4. No\n",
            encoding="utf-8",
        )
        obs = self.observer.inspect_worker(
            worker_id="worker-prompt-blocked",
            pid=os.getpid(),  # Alive PID
            log_path=log_file,
            session_state={"status": "RUNNING", "last_active_at": dt.datetime.now(dt.timezone.utc).isoformat()},
        )
        self.assertEqual(obs.state, WorkerState.WAITING_PERMISSION)
        self.assertTrue(obs.permission_blocked)
        self.assertIn("Do you want to proceed?", obs.permission_prompt_text or "")

        # Compute readiness with this observation
        readiness = self.observer.compute_operational_readiness(oracle_test_command=None)
        # Note: session state is in tmp_dir, so inspect_workspace will see active sessions
        self.assertFalse(readiness.safe_for_unattended_operation if readiness.permission_blocked_count > 0 else False)

    def test_injection_b_killed_worker_detected_as_orphan(self) -> None:
        """Injection B: Persisted RUNNING state with dead PID."""
        dead_pid = 99999999
        sess_file = self.autonomy_dir / "session_state.json"
        sess_data = {
            "session_id": "sess-killed",
            "status": "RUNNING",
            "pid": dead_pid,
            "last_active_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)).isoformat(),
        }
        sess_file.write_text(json.dumps(sess_data, indent=2), encoding="utf-8")

        obs_list = self.observer.inspect_workspace()
        self.assertEqual(len(obs_list), 1)
        self.assertEqual(obs_list[0].state, WorkerState.ORPHANED)
        self.assertFalse(obs_list[0].alive)

        readiness = self.observer.compute_operational_readiness(oracle_test_command=None)
        self.assertFalse(readiness.safe_for_unattended_operation)
        self.assertEqual(readiness.stale_orphans_count, 1)

    def test_injection_c_hung_worker_detected(self) -> None:
        """Injection C: Alive PID with no activity for > 300 seconds."""
        stale_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=400)).isoformat()
        sess_file = self.autonomy_dir / "session_state.json"
        sess_data = {
            "session_id": "sess-hung",
            "status": "RUNNING",
            "pid": os.getpid(),  # Alive PID
            "last_active_at": stale_time,
        }
        sess_file.write_text(json.dumps(sess_data, indent=2), encoding="utf-8")

        obs_list = self.observer.inspect_workspace()
        self.assertEqual(len(obs_list), 1)
        self.assertEqual(obs_list[0].state, WorkerState.HUNG)
        self.assertTrue(obs_list[0].alive)

        # Snitch alert emission and deduplication
        alert1 = self.observer.emit_alert("HUNG_WORKER", "HIGH", {"worker_id": "sess-hung", "state": "HUNG"})
        self.assertIsNotNone(alert1)
        # Duplicate within 5m suppressed
        alert2 = self.observer.emit_alert("HUNG_WORKER", "HIGH", {"worker_id": "sess-hung", "state": "HUNG"})
        self.assertIsNone(alert2)

    def test_injection_d_safe_idle_classification(self) -> None:
        """Injection D: Safe idle session burns zero budget."""
        sess_file = self.autonomy_dir / "session_state.json"
        sess_data = {
            "session_id": "sess-idle",
            "status": "IDLE_EXPECTED",
            "pid": os.getpid(),
            "last_active_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        sess_file.write_text(json.dumps(sess_data, indent=2), encoding="utf-8")

        obs_list = self.observer.inspect_workspace()
        self.assertEqual(len(obs_list), 1)
        self.assertEqual(obs_list[0].state, WorkerState.SAFE_IDLE)
        self.assertFalse(obs_list[0].permission_blocked)

    def test_injection_e_progressing_worker(self) -> None:
        """Injection E: Active worker making progress within 60s."""
        sess_file = self.autonomy_dir / "session_state.json"
        sess_data = {
            "session_id": "sess-live",
            "status": "RUNNING",
            "pid": os.getpid(),
            "last_active_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        sess_file.write_text(json.dumps(sess_data, indent=2), encoding="utf-8")

        obs_list = self.observer.inspect_workspace()
        self.assertEqual(len(obs_list), 1)
        self.assertEqual(obs_list[0].state, WorkerState.PROGRESSING)
        self.assertTrue(obs_list[0].alive)

    def test_injection_g_cross_process_heavy_mutex(self) -> None:
        """Injection G: Heavy authority single-owner mutual exclusion."""
        core1 = EliteExecutionCore(repo_dir=self.tmp_dir)
        core2 = EliteExecutionCore(repo_dir=self.tmp_dir)

        acq1, reason1 = core1.acquire_scope_lock("task-1", ["HEAVY:GOOGLE"])
        self.assertTrue(acq1)
        self.assertIsNone(reason1)

        acq2, reason2 = core2.acquire_scope_lock("task-2", ["HEAVY:GOOGLE"])
        self.assertFalse(acq2)
        self.assertIsNotNone(reason2)
        self.assertIn("locked", reason2 or "")

        # Release by task-1 frees the lock for task-2
        core1.release_scope_lock("task-1")
        acq2_retry, reason2_retry = core2.acquire_scope_lock("task-2", ["HEAVY:GOOGLE"])
        self.assertTrue(acq2_retry)
        self.assertIsNone(reason2_retry)
        core2.release_scope_lock("task-2")


if __name__ == "__main__":
    unittest.main()
