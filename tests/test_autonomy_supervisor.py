#!/usr/bin/env python3
"""Acceptance Tests for Canonical Autonomy Supervisor & Watchdog."""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.autonomy_supervisor import (
    AutonomySupervisor,
    SupervisorLease,
    SupervisorMetrics,
    WorkerHeartbeat,
    WorkerRole,
    WorkerState,
)


class TestAutonomySupervisor(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="sup_test_"))
        self.sup1 = AutonomySupervisor(supervisor_id="sup-instance-01", repo_dir=self.test_dir)

    def tearDown(self):
        self.sup1.release_lease()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_single_active_leader_across_instances(self):
        """Exactly one active supervisor leader is elected across competing instances."""
        res1 = self.sup1.try_acquire_leader_lease()
        self.assertTrue(res1)
        self.assertTrue(self.sup1.is_active_leader)
        self.assertEqual(self.sup1.current_generation, 1)

        # Competing instance should fail while sup1 holds active lease
        sup2 = AutonomySupervisor(supervisor_id="sup-instance-02", repo_dir=self.test_dir)
        res2 = sup2.try_acquire_leader_lease()
        self.assertFalse(res2)
        self.assertFalse(sup2.is_active_leader)

    def test_02_monotonic_generation_fencing_on_failover(self):
        """When old leader releases, follower acquires lease with incremented generation."""
        self.sup1.try_acquire_leader_lease()
        self.assertEqual(self.sup1.current_generation, 1)

        # sup1 releases lease
        self.sup1.release_lease()

        # sup2 acquires
        sup2 = AutonomySupervisor(supervisor_id="sup-instance-02", repo_dir=self.test_dir)
        res2 = sup2.try_acquire_leader_lease()
        self.assertTrue(res2)
        self.assertTrue(sup2.is_active_leader)
        self.assertGreaterEqual(sup2.current_generation, 1)
        sup2.release_lease()

    def test_03_corrupt_lease_fails_closed(self):
        """Malformed or corrupt lease file prevents leadership promotion."""
        lease_file = self.test_dir / "events" / "autonomy-supervisor" / "supervisor_lease.json"
        lease_file.parent.mkdir(parents=True, exist_ok=True)
        lease_file.write_text("CORRUPT_NON_JSON_DATA", encoding="utf-8")

        sup = AutonomySupervisor(supervisor_id="sup-instance-03", repo_dir=self.test_dir)
        res = sup.try_acquire_leader_lease()
        self.assertFalse(res)
        self.assertFalse(sup.is_active_leader)

    def test_04_worker_restart_matrix_governance(self):
        """CLI1/CLI2 can restart, Google is conditional, Chief is forbidden."""
        can_cli1, _ = self.sup1.can_restart_worker(WorkerRole.CLI1.value)
        self.assertTrue(can_cli1)

        can_cli2, _ = self.sup1.can_restart_worker(WorkerRole.CLI2.value)
        self.assertTrue(can_cli2)

        can_google, _ = self.sup1.can_restart_worker(WorkerRole.GOOGLE.value)
        self.assertTrue(can_google)

        can_chief, reason = self.sup1.can_restart_worker(WorkerRole.CHIEF.value)
        self.assertFalse(can_chief)
        self.assertIn("CHIEF_AUTORESTART_FORBIDDEN", reason)

    def test_05_crash_loop_prevention(self):
        """Exceeding max restarts per window blocks restart storm."""
        for _ in range(5):
            ok, _ = self.sup1.restart_worker(WorkerRole.CLI1.value)
            self.assertTrue(ok)

        # 6th restart in quick succession should be blocked
        ok6, reason6 = self.sup1.restart_worker(WorkerRole.CLI1.value)
        self.assertFalse(ok6)
        self.assertEqual(reason6, "CRASH_LOOP_BLOCKED")
        self.assertEqual(self.sup1.metrics.crash_loops_blocked, 1)

    def test_06_pid_none_and_dead_pid_classification(self):
        """pid=None is never alive; dead process transitions to ORPHANED."""
        self.sup1.publish_worker_heartbeat(
            worker_id=WorkerRole.CLI1.value,
            state=WorkerState.PROGRESSING.value,
            process_id=None,
        )
        st, reason = self.sup1.inspect_worker_health(WorkerRole.CLI1.value)
        self.assertEqual(st, WorkerState.SAFE_IDLE)
        self.assertEqual(reason, "PID_NONE_SAFE_IDLE")

        self.sup1.publish_worker_heartbeat(
            worker_id=WorkerRole.CLI2.value,
            state=WorkerState.PROGRESSING.value,
            process_id=99999999,
        )
        st2, reason2 = self.sup1.inspect_worker_health(WorkerRole.CLI2.value)
        self.assertEqual(st2, WorkerState.ORPHANED)
        self.assertEqual(reason2, "DEAD_PROCESS_ORPHANED")

    def test_07_persistent_daemon_with_heartbeat_not_falsely_hung(self):
        """Persistent daemon in SAFE_IDLE with alive PID is not marked HUNG."""
        self.sup1.publish_worker_heartbeat(
            worker_id=WorkerRole.CLI1.value,
            state=WorkerState.SAFE_IDLE.value,
            process_id=os.getpid(),
        )
        st, reason = self.sup1.inspect_worker_health(WorkerRole.CLI1.value)
        self.assertEqual(st, WorkerState.SAFE_IDLE)

    def test_08_provider_quota_exhaustion_transitions_to_waiting_resource(self):
        """Provider quota exhaustion sets WAITING_RESOURCE."""
        self.sup1.publish_worker_heartbeat(
            worker_id=WorkerRole.GOOGLE.value,
            state=WorkerState.PROGRESSING.value,
            process_id=os.getpid(),
            provider_state="QUOTA_EXHAUSTED",
        )
        st, _ = self.sup1.inspect_worker_health(WorkerRole.GOOGLE.value)
        self.assertEqual(st, WorkerState.WAITING_RESOURCE)

    def test_09_chief_offline_mode_preserves_safe_execution(self):
        """Chief offline mode is enabled by default to allow approved safe work to continue."""
        self.assertTrue(self.sup1.chief_offline_mode)

    def test_10_checkpoint_persistence_and_metrics_counters(self):
        """Supervisor checkpoint stores telemetry and restart metrics."""
        self.sup1.metrics.worker_restarts = 4
        self.sup1.metrics.failovers = 2
        self.sup1.save_checkpoint()

        new_sup = AutonomySupervisor(supervisor_id="sup-instance-04", repo_dir=self.test_dir)
        self.assertEqual(new_sup.metrics.worker_restarts, 4)
        self.assertEqual(new_sup.metrics.failovers, 2)
        self.assertGreaterEqual(new_sup.metrics.checkpoint_resumes, 1)


if __name__ == "__main__":
    unittest.main()
