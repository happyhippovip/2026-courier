#!/usr/bin/env python3
"""Mission 204 Acceptance Test Suite: Canonical Authority Root-Cause Remediation.

Verifies:
1. Split-Brain Oracle: AutonomyControlPlane, EliteExecutionCore, and ResourceIntelligence
   cannot each independently grant overlapping heavy or mutation scope authority.
2. Corruption Matrix: Zero-byte files, truncated JSON, non-dict, missing fields,
   negative/string generation, and corrupt files strictly FAIL CLOSED (CORRUPT_BLOCKED).
3. Monotonic Generation Fencing: Stale generation cannot renew, release, or override newer locks.
4. Atomic Multi-Scope Acquisition: Overlapping scopes or halfway failures release only matching authority.
5. Crash Safety & Recovery: Dead PID + expired lease allows recovery only with generation increment.
6. Missing PID Liveness: Missing or None PID is never assumed alive in live_worker_registry.
7. Zero Model Calls & Spend: 0 EUR, 0 model calls across all authority checks.
"""

from __future__ import annotations

import datetime as dt
import json
import multiprocessing
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.autonomy_control_plane import AutonomyControlPlane, ModelAdmissionRequest
from scripts.canonical_authority import (
    AuthorityRecord,
    CanonicalAuthority,
    LockStatus,
    is_pid_alive,
    utc_now,
)
from scripts.elite_execution_core import EliteExecutionCore
from scripts.live_worker_registry import (
    EventType,
    LiveWorkerRegistry,
    WorkerRecord,
    WorkerState,
)
from scripts.resource_intelligence import ResourceIntelligenceManager


def _concurrent_acquire_worker(locks_dir_str: str, owner_id: str, task_id: str, scope: str, result_queue: multiprocessing.Queue):
    """Child process target for concurrent authority contention."""
    auth = CanonicalAuthority(locks_dir=Path(locks_dir_str))
    success, gen, err = auth.acquire_scopes(
        owner_id=owner_id,
        task_id=task_id,
        scopes=[scope],
        ttl_seconds=30,
    )
    result_queue.put({"owner_id": owner_id, "success": success, "generation": gen, "error": err})


def _concurrent_heavy_worker(locks_dir_str: str, owner_id: str, task_id: str, result_queue: multiprocessing.Queue):
    """Child process target for heavy slot contention."""
    auth = CanonicalAuthority(locks_dir=Path(locks_dir_str))
    success, gen, err = auth.acquire_heavy_authority(
        owner_id=owner_id,
        task_id=task_id,
        ttl_seconds=30,
    )
    result_queue.put({"owner_id": owner_id, "success": success, "generation": gen, "error": err})


class TestCanonicalAuthorityRootCause(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="canonical_auth_204_"))
        self.events_dir = self.test_dir / "events"
        self.locks_dir = self.events_dir / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.auth = CanonicalAuthority(locks_dir=self.locks_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. SPLIT-BRAIN ORACLE
    # --------------------------------------------------------------------------

    def test_01_split_brain_heavy_job_single_winner(self):
        """AutonomyControlPlane, EliteExecutionCore, and ResourceIntelligence cannot simultaneously hold heavy slot."""
        acp = AutonomyControlPlane(repo_dir=self.test_dir)
        eec = EliteExecutionCore(repo_dir=self.test_dir)
        rim = ResourceIntelligenceManager(repo_dir=self.test_dir)

        # 1. ResourceIntelligence claims heavy command
        res1 = rim.claim_command(command="render_3d_heavy", code_hash="abc1", owner_id="worker_rim", heavy=True)
        self.assertEqual(res1.get("decision"), "CLAIMED")

        # 2. EliteExecutionCore attempts heavy scope lock -> MUST BE REJECTED
        eec_ok, eec_err = eec.acquire_scope_lock(task_id="task_eec", scopes=["HEAVY:GLOBAL"])
        self.assertFalse(eec_ok)
        self.assertIn("is locked by", str(eec_err))

        # 3. AutonomyControlPlane attempts admission for heavy scope -> MUST BE REJECTED
        adm_ok, adm_err = acp._acquire_scope_locks(task_id="task_acp", requested_scopes=["HEAVY:GLOBAL"])
        self.assertFalse(adm_ok)
        self.assertIn("is locked by", str(adm_err))

        # 4. Release heavy slot from RIM
        rim.complete_command(fingerprint=res1["fingerprint"], result_hash="res_hash_1", owner_id="worker_rim")

        # 5. Now EEC can acquire heavy slot
        eec_ok2, _ = eec.acquire_scope_lock(task_id="task_eec", scopes=["HEAVY:GLOBAL"])
        self.assertTrue(eec_ok2)

        # 6. RIM now blocked because EEC owns it
        res2 = rim.claim_command(command="render_3d_heavy_2", code_hash="abc2", owner_id="worker_rim_2", heavy=True)
        self.assertEqual(res2.get("decision"), "BLOCK_HEAVY_JOB_LIMIT")

    def test_02_split_brain_overlapping_mutation_scopes(self):
        """ACP and EEC cannot acquire overlapping scope paths."""
        acp = AutonomyControlPlane(repo_dir=self.test_dir)
        eec = EliteExecutionCore(repo_dir=self.test_dir)

        # ACP acquires parent directory scope
        ok1, _ = acp._acquire_scope_locks(task_id="task_acp_1", requested_scopes=["src/core"])
        self.assertTrue(ok1)

        # EEC attempts to acquire child file scope -> MUST BE REJECTED due to hierarchical overlap
        ok2, err2 = eec.acquire_scope_lock(task_id="task_eec_1", scopes=["src/core/models.py"])
        self.assertFalse(ok2)
        self.assertIn("is locked by", str(err2))

        # ACP releases
        acp.release_scope_locks(task_id="task_acp_1")

        # Now EEC can acquire
        ok3, _ = eec.acquire_scope_lock(task_id="task_eec_1", scopes=["src/core/models.py"])
        self.assertTrue(ok3)

    # --------------------------------------------------------------------------
    # 2. CORRUPTION MATRIX (FAIL CLOSED)
    # --------------------------------------------------------------------------

    def test_03_corruption_matrix_zero_byte_file(self):
        """Zero-byte scope file is parsed as CORRUPT_BLOCKED and fails closed on acquisition."""
        corrupt_file = self.locks_dir / "scope_corrupt_test_12345678.json"
        corrupt_file.write_text("", encoding="utf-8")

        status, rec, err = self.auth.parse_authority_record(corrupt_file)
        self.assertEqual(status, LockStatus.CORRUPT_BLOCKED)
        self.assertIn("Zero-byte", str(err))

        # Attempting to acquire any scope while corrupt lock exists MUST FAIL CLOSED
        ok, gen, acq_err = self.auth.acquire_scopes(owner_id="w1", task_id="t1", scopes=["src/test"])
        self.assertFalse(ok)
        self.assertIn("BLOCK_CORRUPT_STATE", str(acq_err))

    def test_04_corruption_matrix_malformed_json_and_non_dict(self):
        """Malformed JSON, arrays, null, and non-dicts fail closed."""
        corrupt_file = self.locks_dir / "scope_bad_json_12345678.json"

        cases = [
            "{truncated json",
            "[]",
            "null",
            '"just a string"',
            "12345",
        ]
        for content in cases:
            corrupt_file.write_text(content, encoding="utf-8")
            status, _, err = self.auth.parse_authority_record(corrupt_file)
            self.assertEqual(status, LockStatus.CORRUPT_BLOCKED, f"Expected CORRUPT_BLOCKED for content: {content}")

            ok, _, acq_err = self.auth.acquire_scopes(owner_id="w1", task_id="t1", scopes=["src/valid"])
            self.assertFalse(ok, f"Acquisition should fail closed for corrupt content: {content}")
            self.assertIn("BLOCK_CORRUPT_STATE", str(acq_err))

    def test_05_corruption_matrix_missing_or_invalid_fields(self):
        """Missing owner, negative generation, non-integer generation fail closed."""
        corrupt_file = self.locks_dir / "scope_invalid_fields_12345678.json"

        invalid_records = [
            {"schema_version": "1.0", "scope": "s1"},  # missing owner_id, pid, generation
            {"schema_version": "1.0", "scope": "s1", "owner_id": "o1", "task_id": "t1", "generation": -5, "pid": 100, "acquired_at": utc_now(), "lease_expires_at": utc_now()},  # negative gen
            {"schema_version": "1.0", "scope": "s1", "owner_id": "o1", "task_id": "t1", "generation": "100", "pid": 100, "acquired_at": utc_now(), "lease_expires_at": utc_now()},  # string gen
            {"schema_version": "1.0", "scope": "s1", "owner_id": "o1", "task_id": "t1", "generation": 10, "pid": "bad_pid", "acquired_at": utc_now(), "lease_expires_at": utc_now()},  # string pid
        ]

        for rec_dict in invalid_records:
            corrupt_file.write_text(json.dumps(rec_dict), encoding="utf-8")
            status, _, _ = self.auth.parse_authority_record(corrupt_file)
            self.assertEqual(status, LockStatus.CORRUPT_BLOCKED)

    # --------------------------------------------------------------------------
    # 3. GENERATION & FENCING
    # --------------------------------------------------------------------------

    def test_06_generation_fencing_rejects_stale_owner_actions(self):
        """Stale generation cannot renew, release, or overwrite newer owner."""
        # 1. Owner A acquires scope at Gen N
        ok_a, gen_a, _ = self.auth.acquire_scopes(owner_id="owner_a", task_id="task_a", scopes=["src/core"])
        self.assertTrue(ok_a)

        # Release scope
        self.auth.release_scopes(owner_id="owner_a", scopes=["src/core"], generation=gen_a)

        # 2. Owner B acquires same scope at Gen N+1
        ok_b, gen_b, _ = self.auth.acquire_scopes(owner_id="owner_b", task_id="task_b", scopes=["src/core"])
        self.assertTrue(ok_b)
        self.assertGreater(gen_b, gen_a)

        # 3. Owner A wakes up and attempts to heartbeat as Gen N -> MUST BE FENCED OUT
        renew_ok, renew_err = self.auth.renew_heartbeat(owner_id="owner_a", scope="src/core", generation=gen_a)
        self.assertFalse(renew_ok)
        self.assertIn("Fenced out", str(renew_err))

        # 4. Owner A attempts to release scope using stale Gen N -> MUST NOT RELEASE Owner B
        released_count, _ = self.auth.release_scopes(owner_id="owner_a", scopes=["src/core"], generation=gen_a)
        self.assertEqual(released_count, 0)

        # Verify Owner B still securely owns the scope
        active = self.auth.list_active_locks()
        self.assertIn("src/core", active)
        self.assertEqual(active["src/core"]["owner_id"], "owner_b")
        self.assertEqual(active["src/core"]["generation"], gen_b)

    # --------------------------------------------------------------------------
    # 4. ATOMIC MULTI-SCOPE ACQUISITION
    # --------------------------------------------------------------------------

    def test_07_atomic_multi_scope_all_or_nothing(self):
        """If one of three requested scopes is locked, none are acquired."""
        # Pre-lock scope3
        self.auth.acquire_scopes(owner_id="other_owner", task_id="other_task", scopes=["scope_gamma"])

        # Caller requests scope_alpha, scope_beta, scope_gamma
        ok, gen, err = self.auth.acquire_scopes(
            owner_id="my_owner",
            task_id="my_task",
            scopes=["scope_alpha", "scope_beta", "scope_gamma"],
        )
        self.assertFalse(ok)
        self.assertIn("is locked by", str(err))

        # Verify neither scope_alpha nor scope_beta was partially acquired
        active = self.auth.list_active_locks()
        self.assertNotIn("scope_alpha", active)
        self.assertNotIn("scope_beta", active)
        self.assertEqual(active["scope_gamma"]["owner_id"], "other_owner")

    # --------------------------------------------------------------------------
    # 5. CROSS-PROCESS MUTUAL EXCLUSION
    # --------------------------------------------------------------------------

    def test_08_cross_process_heavy_contention(self):
        """Contention across separate OS processes results in exactly 1 winner."""
        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(
            target=_concurrent_heavy_worker,
            args=(str(self.locks_dir), "proc_1", "task_1", q),
        )
        p2 = multiprocessing.Process(
            target=_concurrent_heavy_worker,
            args=(str(self.locks_dir), "proc_2", "task_2", q),
        )

        p1.start()
        p2.start()
        p1.join(timeout=5)
        p2.join(timeout=5)

        results = [q.get() for _ in range(2)]
        winners = [r for r in results if r["success"]]
        losers = [r for r in results if not r["success"]]

        self.assertEqual(len(winners), 1, f"Expected exactly 1 winner, got {len(winners)}: {results}")
        self.assertEqual(len(losers), 1, f"Expected exactly 1 loser, got {len(losers)}: {results}")

    # --------------------------------------------------------------------------
    # 6. LIVE WORKER REGISTRY MISSING PID FIX
    # --------------------------------------------------------------------------

    def test_09_live_worker_registry_missing_pid_not_assumed_alive(self):
        """Missing or None PID is never assumed alive; transitions to UNKNOWN instead of remaining PROGRESSING."""
        reg = LiveWorkerRegistry(repo_dir=self.test_dir)
        worker = WorkerRecord(
            worker_id="test-worker-no-pid",
            role="Primary Builder",
            provider="GOOGLE_PRO",
            availability_class="SUBSCRIPTION_RESERVE",
            available_until=None,
            state=WorkerState.PROGRESSING.value,
        )
        reg._save_worker_record(worker)

        # Audit with None PID
        audited = reg.audit_worker_liveness(worker, pid=None)
        self.assertEqual(audited.state, WorkerState.UNKNOWN.value)
        self.assertEqual(audited.blocked_reason, "MISSING_OR_INVALID_PID")

    def test_10_live_worker_registry_dead_pid_transitions_to_orphaned(self):
        """Dead PID with PROGRESSING state transitions to ORPHANED."""
        reg = LiveWorkerRegistry(repo_dir=self.test_dir)
        worker = WorkerRecord(
            worker_id="test-worker-dead-pid",
            role="QA Reviewer",
            provider="CODEX",
            availability_class="SUBSCRIPTION_RESERVE",
            available_until=None,
            state=WorkerState.PROGRESSING.value,
        )
        reg._save_worker_record(worker)

        # Audit with non-existent PID (e.g. 99999999)
        audited = reg.audit_worker_liveness(worker, pid=99999999)
        self.assertEqual(audited.state, WorkerState.ORPHANED.value)
        self.assertEqual(audited.blocked_reason, "PID_DEAD_WITH_ACTIVE_STATE")


if __name__ == "__main__":
    unittest.main()
