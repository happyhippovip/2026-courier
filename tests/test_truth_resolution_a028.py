"""Tests for Canonical Truth Conflict Resolution (ANTIGRAVITY 028).

Verifies authority invariants across disparate status sources:
- Conflicting Status: Local Session claims DONE, Ledger claims RUNNING -> Fail-closed TRUTH_CONFLICT.
- Worker vs Verifier: Worker claims PASS, Verifier reports FAIL -> Verifier prevails, result FAILED.
- Stale Checkpoint: Earlier generation checkpoint ignored, current generation prevails.
- Different Execution IDs: Multiple execution IDs claiming same attempt -> Fail-closed CONCURRENT_WRITER conflict.
- Newer Verified Receipt: Verified receipt preserved against later unconfirmed updates.
- Concurrent / Foreign Writer: Unregistered writer claiming task -> Fail-closed UNAUTHORIZED_WRITER conflict.
"""

import pytest

from courier_runtime.truth_resolution import (
    AuthorityLevel,
    CanonicalTruthResolver,
    ResolutionVerdict,
    TruthRecord,
)


def test_conflict_case_a_local_done_ledger_running():
    """Case A: Local session says DONE, Ledger says RUNNING.
    
    Must NOT promote status to DONE without verified ledger commitment.
    Fails closed to TRUTH_CONFLICT with STATUS_UNCOMMITTED.
    """
    records = [
        TruthRecord(
            source_type="PERSISTED_LEDGER",
            task_id="task-100",
            status="RUNNING",
            authority=AuthorityLevel.PERSISTED_LEDGER,
            writer_id="steward-mac",
            generation=1,
            attempt=1,
            timestamp=100.0,
        ),
        TruthRecord(
            source_type="SESSION_CHECKPOINT",
            task_id="task-100",
            status="DONE",
            authority=AuthorityLevel.SESSION_CHECKPOINT,
            writer_id="steward-mac",
            generation=1,
            attempt=1,
            timestamp=105.0,
        ),
    ]

    verdict = CanonicalTruthResolver.resolve(records, authorized_owner="steward-mac")

    assert verdict.is_conflict is True
    assert verdict.conflict_type == "STATUS_UNCOMMITTED"
    assert verdict.resolved_status == "TRUTH_CONFLICT"
    assert "uncommitted promotion blocked" in verdict.reason.lower()


def test_conflict_case_b_worker_pass_verifier_fail():
    """Case B: Worker claims PASS, Verifier reports FAIL.
    
    Verifier outranks worker self-report.
    Result is FAILED, not PASS.
    """
    records = [
        TruthRecord(
            source_type="WORKER_SELF_REPORT",
            task_id="task-101",
            status="PASS",
            authority=AuthorityLevel.WORKER_SELF_REPORT,
            writer_id="worker-01",
            generation=1,
            attempt=1,
            verified=False,
            timestamp=200.0,
        ),
        TruthRecord(
            source_type="VERIFIED_RECEIPT",
            task_id="task-101",
            status="FAIL",
            authority=AuthorityLevel.VERIFIED_RECEIPT,
            writer_id="verifier-01",
            generation=1,
            attempt=1,
            verified=True,
            evidence_ref="evidence/task-101_failure.json",
            timestamp=201.0,
        ),
    ]

    verdict = CanonicalTruthResolver.resolve(records)

    assert verdict.is_conflict is True
    assert verdict.conflict_type == "WORKER_VERIFIER_MISMATCH"
    assert verdict.resolved_status == "FAILED"
    assert verdict.winning_source == "VERIFIED_RECEIPT"


def test_conflict_case_c_stale_checkpoint_earlier_generation():
    """Case C: Stale checkpoint with earlier generation.
    
    Generation 1 checkpoint must NOT overwrite Generation 2 ledger state.
    """
    records = [
        TruthRecord(
            source_type="PERSISTED_LEDGER",
            task_id="task-102",
            status="RUNNING",
            authority=AuthorityLevel.PERSISTED_LEDGER,
            writer_id="owner-primary",
            generation=2,
            attempt=2,
            timestamp=310.0,
        ),
        TruthRecord(
            source_type="SESSION_CHECKPOINT",
            task_id="task-102",
            status="OPEN",
            authority=AuthorityLevel.SESSION_CHECKPOINT,
            writer_id="owner-primary",
            generation=1,
            attempt=1,
            timestamp=300.0,
        ),
    ]

    verdict = CanonicalTruthResolver.resolve(records, authorized_owner="owner-primary")

    assert verdict.winning_source == "PERSISTED_LEDGER"
    assert verdict.resolved_status == "RUNNING"
    assert verdict.conflict_type == "STALE_CHECKPOINT"


def test_conflict_case_d_different_execution_ids_same_attempt():
    """Case D: Two different execution IDs claim the same attempt.
    
    Violates single-writer fencing; must fail closed to TRUTH_CONFLICT.
    """
    records = [
        TruthRecord(
            source_type="WORKER_SELF_REPORT",
            task_id="task-103",
            status="RUNNING",
            authority=AuthorityLevel.WORKER_SELF_REPORT,
            writer_id="worker-node-a",
            generation=1,
            attempt=1,
            execution_id="exec-alpha-111",
            timestamp=400.0,
        ),
        TruthRecord(
            source_type="SESSION_CHECKPOINT",
            task_id="task-103",
            status="RUNNING",
            authority=AuthorityLevel.SESSION_CHECKPOINT,
            writer_id="worker-node-b",
            generation=1,
            attempt=1,
            execution_id="exec-beta-222",
            timestamp=401.0,
        ),
    ]

    verdict = CanonicalTruthResolver.resolve(records)

    assert verdict.is_conflict is True
    assert verdict.conflict_type == "CONCURRENT_WRITER"
    assert verdict.resolved_status == "TRUTH_CONFLICT"
    assert "single-writer violated" in verdict.reason.lower()


def test_conflict_case_e_verified_receipt_preserved_against_later_unconfirmed_status():
    """Case E: Verified result exists, but a later unconfirmed status contradicts it.
    
    Verified receipt is authoritative and preserved.
    """
    records = [
        TruthRecord(
            source_type="VERIFIED_RECEIPT",
            task_id="task-104",
            status="COMPLETE",
            authority=AuthorityLevel.VERIFIED_RECEIPT,
            writer_id="verifier-suite",
            generation=1,
            attempt=1,
            verified=True,
            evidence_ref="evidence/task-104_passed.json",
            timestamp=500.0,
        ),
        TruthRecord(
            source_type="WORKER_SELF_REPORT",
            task_id="task-104",
            status="RUNNING",
            authority=AuthorityLevel.WORKER_SELF_REPORT,
            writer_id="worker-stale",
            generation=1,
            attempt=1,
            timestamp=510.0,  # Newer timestamp, but subordinate authority
        ),
    ]

    verdict = CanonicalTruthResolver.resolve(records)

    assert verdict.resolved_status == "VERIFIED_COMPLETE"
    assert verdict.winning_source == "VERIFIED_RECEIPT"
    assert verdict.conflict_type == "UNCONFIRMED_OVERRIDE_PREVENTED"
    assert verdict.effective_record is not None
    assert verdict.effective_record.evidence_ref == "evidence/task-104_passed.json"


def test_conflict_case_f_unauthorized_foreign_writer_rejected():
    """Case F: A foreign writer claims a task owned by another agent in the ledger.
    
    Must reject unauthorized claim as UNAUTHORIZED_WRITER.
    """
    records = [
        TruthRecord(
            source_type="PERSISTED_LEDGER",
            task_id="task-105",
            status="RUNNING",
            authority=AuthorityLevel.PERSISTED_LEDGER,
            writer_id="authorized-owner-bob",
            generation=1,
            attempt=1,
            timestamp=600.0,
        ),
        TruthRecord(
            source_type="SESSION_CHECKPOINT",
            task_id="task-105",
            status="DONE",
            authority=AuthorityLevel.SESSION_CHECKPOINT,
            writer_id="foreign-intruder-eve",
            generation=1,
            attempt=1,
            timestamp=605.0,
        ),
    ]

    verdict = CanonicalTruthResolver.resolve(records)

    assert verdict.is_conflict is True
    assert verdict.conflict_type == "UNAUTHORIZED_WRITER"
    assert verdict.resolved_status == "TRUTH_CONFLICT"
    assert "no claim authority in ledger" in verdict.reason.lower()


def test_empty_records_returns_unknown():
    verdict = CanonicalTruthResolver.resolve([])
    assert verdict.resolved_status == "UNKNOWN"
    assert verdict.is_conflict is False


def test_cross_task_mismatch_fails_closed():
    records = [
        TruthRecord(
            source_type="PERSISTED_LEDGER",
            task_id="task-aaa",
            status="RUNNING",
            authority=AuthorityLevel.PERSISTED_LEDGER,
        ),
        TruthRecord(
            source_type="SESSION_CHECKPOINT",
            task_id="task-bbb",
            status="RUNNING",
            authority=AuthorityLevel.SESSION_CHECKPOINT,
        ),
    ]
    verdict = CanonicalTruthResolver.resolve(records)
    assert verdict.resolved_status == "TRUTH_CONFLICT"
    assert verdict.conflict_type == "CROSS_TASK_CONTAMINATION"
