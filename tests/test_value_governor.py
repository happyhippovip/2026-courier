"""
test_value_governor.py - Acceptance Tests for Courier Value Governor & Anti-Busywork Court
Mission Class: P0 Autonomy Infrastructure
Operating Phase: AUTONOMY_FIRST

Verifies:
1. Rejection of Milestone Theater (task-count proofs, symphony milestones)
2. Rejection of Speculative Overengineering (SAML, ISO20022, Merkle, Brotli, etc.)
3. Rejection of Generic Court Reuse (using test_permanent_reserve_acceptance_court.py as task proof)
4. Rejection of Missing Source Evidence
5. Acceptance of Genuine Evidence-Backed Tasks with Distinct Test Scripts
6. Accurate Arithmetic Reconciliation between Control Plane and Safe Backlog
"""

import os
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
if os.path.join(WORKSPACE_ROOT, "courier") not in sys.path:
    sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "courier"))

from chief.value_governor import ValueGovernor, ALLOWED_REAL_DELTAS


class TestValueGovernor(unittest.TestCase):
    def setUp(self):
        self.workspace_root = WORKSPACE_ROOT

    def test_01_reject_milestone_theater(self):
        """Milestone theater tasks must be rejected."""
        candidates = [
            {"task_id": "TASK-WIN-250", "title": "Sesquimillennial Milestone: 650-Task Symphony Autonomous Reserve Proof", "expected_real_delta": "AUTONOMY_GAIN"},
            {"task_id": "TASK-WIN-260", "title": "Sexacentennial Milestone: 675-Task Symphony Autonomous Reserve Proof", "expected_real_delta": "AUTONOMY_GAIN"},
            {"task_id": "TASK-WIN-270", "title": "Septuagintennial Milestone: 700-Task Symphony Master Autonomous Proof", "expected_real_delta": "AUTONOMY_GAIN"},
            {"task_id": "TASK-WIN-300", "title": "Nongentennial Milestone: 800-Task Symphony Master Autonomous Proof", "expected_real_delta": "AUTONOMY_GAIN"},
        ]
        for c in candidates:
            c["source_evidence"] = "courier/chief/control_plane.py"
            c["script_path"] = "courier/tests/test_closure_gate.py"
            valid, reason = ValueGovernor.audit_candidate(c, self.workspace_root)
            self.assertFalse(valid, f"Should have rejected milestone task {c['task_id']}")
            self.assertIn("REJECTED_MILESTONE_THEATER", reason)

    def test_02_reject_speculative_overengineering(self):
        """Speculative enterprise features without measured gap must be rejected."""
        candidates = [
            {"task_id": "TASK-WIN-216", "title": "B2B ISO 20022 Pain.001 Payment Messaging Schema Validator", "conflict_scope": "ISO20022_SCHEMA", "expected_real_delta": "CAPABILITY_GAIN"},
            {"task_id": "TASK-WIN-221", "title": "B2B Enterprise SAML 2.0 Identity Provider Metadata Parser", "conflict_scope": "SAML_METADATA", "expected_real_delta": "CAPABILITY_GAIN"},
            {"task_id": "TASK-WIN-245", "title": "Microsecond Precision Execution Latency & Jitter Monitor", "conflict_scope": "JITTER_MONITOR", "expected_real_delta": "PERFORMANCE_GAIN"},
            {"task_id": "TASK-WIN-248", "title": "Offline License Revocation Merkle Tree Root Hash Generator", "conflict_scope": "MERKLE_REVOCATION", "expected_real_delta": "SECURITY_GAIN"},
            {"task_id": "TASK-WIN-263", "title": "Zero-Copy Inter-Thread Circular Buffer for Event Dispatch", "conflict_scope": "CIRCULAR_DISPATCH", "expected_real_delta": "PERFORMANCE_GAIN"},
            {"task_id": "TASK-WIN-265", "title": "Storefront Brotli Pre-Compression & Asset Integrity Hasher", "conflict_scope": "BROTLI_COMPRESSOR", "expected_real_delta": "PERFORMANCE_GAIN"},
        ]
        for c in candidates:
            c["source_evidence"] = "courier/chief/control_plane.py"
            c["script_path"] = "courier/tests/test_closure_gate.py"
            valid, reason = ValueGovernor.audit_candidate(c, self.workspace_root)
            self.assertFalse(valid, f"Should have rejected speculative task {c['task_id']}")
            self.assertIn("REJECTED_SPECULATIVE_OVERENGINEERING", reason)

    def test_03_reject_generic_court_reuse(self):
        """Candidate cannot reuse generic acceptance court as proof of task effect."""
        candidate = {
            "task_id": "TASK-WIN-CUSTOM",
            "title": "Legitimate SQLite Database WAL Compaction Optimization",
            "conflict_scope": "DB_COMPACTION",
            "expected_real_delta": "PERFORMANCE_GAIN",
            "source_evidence": "courier/chief/control_plane.py",
            "script_path": "courier/tests/test_permanent_reserve_acceptance_court.py"
        }
        valid, reason = ValueGovernor.audit_candidate(candidate, self.workspace_root)
        self.assertFalse(valid)
        self.assertIn("REJECTED_GENERIC_COURT_REUSE", reason)

    def test_04_reject_missing_source_evidence(self):
        """Candidate with missing or NONE source evidence must be rejected."""
        candidate = {
            "task_id": "TASK-WIN-NOEVID",
            "title": "Legitimate Bug Fix for SQLite Deadlock",
            "conflict_scope": "SQLITE_DEADLOCK",
            "expected_real_delta": "DEFECT_REMOVAL",
            "source_evidence": "NONE",
            "script_path": "courier/tests/test_fenced_mutex_guard.py"
        }
        valid, reason = ValueGovernor.audit_candidate(candidate, self.workspace_root)
        self.assertFalse(valid)
        self.assertIn("REJECTED_MISSING_SOURCE_EVIDENCE", reason)

    def test_05_accept_genuine_evidence_backed_candidate(self):
        """Candidate with real delta, real on-disk evidence, and distinct test must be accepted."""
        candidate = {
            "task_id": "TASK-WIN-GENUINE",
            "title": "Cross-Platform Fenced Mutex Race Condition Guard",
            "conflict_scope": "MUTEX_GUARD",
            "expected_real_delta": "RELIABILITY_GAIN",
            "source_evidence": "courier/chief/fenced_mutex.py",
            "script_path": "courier/tests/test_fenced_mutex_guard.py"
        }
        valid, reason = ValueGovernor.audit_candidate(candidate, self.workspace_root)
        self.assertTrue(valid, f"Should have accepted genuine candidate: {reason}")
        self.assertEqual(reason, "ACCEPTED")

    def test_06_arithmetic_reconciliation(self):
        """Reconciles exact row counts in SQLite CP vs safe_backlog."""
        db_path = os.path.join(WORKSPACE_ROOT, "courier", "chief_control_plane.db")
        backlog_path = os.path.join(WORKSPACE_ROOT, "project-memory", "data", "safe_backlog.json")
        rec = ValueGovernor.reconcile_arithmetic(db_path, backlog_path)
        self.assertGreater(rec["cp_total_completed_rows"], 0)
        self.assertGreater(rec["cp_historical_fallback_count"], 0)
        self.assertGreater(rec["cp_legitimate_win_count"], 0)
        # Proven that total rows = fallback + timestamped + legitimate
        total_parts = rec["cp_historical_fallback_count"] + rec["cp_timestamped_test_count"] + rec["cp_legitimate_win_count"]
        self.assertEqual(rec["cp_total_completed_rows"], total_parts)


if __name__ == "__main__":
    unittest.main()
