#!/usr/bin/env python3
"""Acceptance Test Suite for Autonomous Agent Crash-Safety Toolkit."""

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SRC_DIR = TEST_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from safety_oracles import AgentSafetyAuditor


class TestAgentSafetyOracles(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="agent_safety_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_pid_liveness_oracle(self):
        self.assertTrue(AgentSafetyAuditor.audit_pid_liveness(os.getpid()))
        self.assertFalse(AgentSafetyAuditor.audit_pid_liveness(99999999))

    def test_02_flock_isolation_oracle(self):
        lock_file = self.test_dir / "agent.lock"
        self.assertTrue(AgentSafetyAuditor.audit_file_lock_isolation(lock_file))

    def test_03_spend_firewall_oracle(self):
        # 0.0 EUR within 0.0 EUR limit -> True
        self.assertTrue(AgentSafetyAuditor.audit_spend_firewall(0.0, 0.0))
        # 0.05 EUR exceeds 0.0 EUR limit -> False
        self.assertFalse(AgentSafetyAuditor.audit_spend_firewall(0.05, 0.0))

    def test_04_heartbeat_staleness_oracle(self):
        fresh_ts = time.time() - 5.0
        self.assertTrue(AgentSafetyAuditor.audit_heartbeat_staleness(fresh_ts, timeout_seconds=15.0))
        stale_ts = time.time() - 45.0
        self.assertFalse(AgentSafetyAuditor.audit_heartbeat_staleness(stale_ts, timeout_seconds=15.0))


if __name__ == "__main__":
    unittest.main()
