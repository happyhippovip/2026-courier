"""Canonical Truth Conflict Resolution (ANTIGRAVITY 028).

Resolves conflicting state reports across heterogeneous sources:
- Persisted Ledger (authoritative for task definitions and ownership)
- Verified Result Receipts (highest authority for completed/failed execution outcomes)
- Local Session Checkpoints (valid only with matching dispatch generation & writer ownership)
- Worker Self-Reports (provisional telemetry, strictly subordinate to verifiers)
- External Handoffs (unverified, lowest authority)

Canonical Invariants:
1. Authority Ranking: Verified Evidence > Persisted Ledger > Session Checkpoint > Worker Self-Report > Handoff.
2. No blind timestamp-wins: A newer low-authority update cannot overwrite verified or authoritative state.
3. Irreconcilable contradictions fail closed to TRUTH_CONFLICT / BLOCKED.
4. Single-writer enforcement: Concurrent execution claims on the same attempt fail closed.
5. Verifier trumps worker: Worker claiming PASS when verifier recorded FAIL is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Sequence


class AuthorityLevel(IntEnum):
    UNVERIFIED_HANDOFF = 10
    WORKER_SELF_REPORT = 20
    SESSION_CHECKPOINT = 30
    PERSISTED_LEDGER = 40
    VERIFIED_RECEIPT = 50


@dataclass(frozen=True)
class TruthRecord:
    """A single state observation from a specific source."""
    source_type: str  # VERIFIED_RECEIPT | PERSISTED_LEDGER | SESSION_CHECKPOINT | WORKER_SELF_REPORT | UNVERIFIED_HANDOFF
    task_id: str
    status: str       # e.g. DONE, COMPLETED, RUNNING, FAILED, PASS, FAIL, etc.
    authority: AuthorityLevel
    writer_id: Optional[str] = None
    generation: int = 1
    attempt: int = 1
    execution_id: Optional[str] = None
    verified: bool = False
    evidence_ref: Optional[str] = None
    timestamp: float = 0.0
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolutionVerdict:
    """The deterministic outcome of reconciling truth across multiple records."""
    task_id: str
    resolved_status: str       # VERIFIED_COMPLETE | RUNNING | FAILED | BLOCKED | TRUTH_CONFLICT
    winning_source: Optional[str]
    is_conflict: bool
    conflict_type: Optional[str]    # e.g. STATUS_UNCOMMITTED, WORKER_VERIFIER_MISMATCH, STALE_GENERATION, CONCURRENT_WRITER, UNAUTHORIZED_WRITER
    reason: str
    effective_record: Optional[TruthRecord] = None


class CanonicalTruthResolver:
    """Reconciles disparate task state records using proven authority invariants."""

    @staticmethod
    def resolve(records: Sequence[TruthRecord], *, authorized_owner: Optional[str] = None) -> ResolutionVerdict:
        if not records:
            return ResolutionVerdict(
                task_id="",
                resolved_status="UNKNOWN",
                winning_source=None,
                is_conflict=False,
                conflict_type=None,
                reason="NO_RECORDS_PROVIDED",
            )

        task_id = records[0].task_id
        if any(r.task_id != task_id for r in records):
            return ResolutionVerdict(
                task_id=task_id,
                resolved_status="TRUTH_CONFLICT",
                winning_source=None,
                is_conflict=True,
                conflict_type="CROSS_TASK_CONTAMINATION",
                reason="Records contain mismatched task IDs",
            )

        # 1. Authoritative Ledger & Ownership Check
        ledger_record = next(
            (r for r in records if r.source_type == "PERSISTED_LEDGER"), None
        )
        ledger_owner = ledger_record.writer_id if ledger_record else authorized_owner

        # Check for unauthorized / foreign writer claims (Case F)
        if ledger_owner:
            foreign_claim = next(
                (
                    r for r in records
                    if r.writer_id and r.writer_id != ledger_owner
                    and r.source_type in ("SESSION_CHECKPOINT", "WORKER_SELF_REPORT")
                ),
                None,
            )
            if foreign_claim:
                return ResolutionVerdict(
                    task_id=task_id,
                    resolved_status="TRUTH_CONFLICT",
                    winning_source="PERSISTED_LEDGER",
                    is_conflict=True,
                    conflict_type="UNAUTHORIZED_WRITER",
                    reason=f"Foreign writer '{foreign_claim.writer_id}' has no claim authority in ledger (owner: '{ledger_owner}')",
                    effective_record=ledger_record,
                )

        # 2. Check for Concurrent Execution IDs on Same Attempt (Case D)
        execution_ids: Dict[int, List[str]] = {}
        for r in records:
            if r.execution_id and r.source_type in ("WORKER_SELF_REPORT", "SESSION_CHECKPOINT"):
                execution_ids.setdefault(r.attempt, []).append(r.execution_id)
        
        for attempt, ids in execution_ids.items():
            distinct_ids = sorted(set(ids))
            if len(distinct_ids) > 1:
                return ResolutionVerdict(
                    task_id=task_id,
                    resolved_status="TRUTH_CONFLICT",
                    winning_source=None,
                    is_conflict=True,
                    conflict_type="CONCURRENT_WRITER",
                    reason=f"Multiple execution IDs {distinct_ids} claimed attempt {attempt}; single-writer violated",
                )

        # 3. Verified Result Receipt vs Other Records (Case E & Case B)
        verified_receipt = next(
            (r for r in records if r.source_type == "VERIFIED_RECEIPT" and r.verified), None
        )
        if verified_receipt:
            # Check if worker claims PASS while verifier recorded FAIL (Case B)
            worker_report = next(
                (r for r in records if r.source_type == "WORKER_SELF_REPORT"), None
            )
            if worker_report and worker_report.status.upper() in ("PASS", "COMPLETED", "DONE"):
                if verified_receipt.status.upper() in ("FAIL", "FAILED", "ERROR"):
                    return ResolutionVerdict(
                        task_id=task_id,
                        resolved_status="FAILED",
                        winning_source="VERIFIED_RECEIPT",
                        is_conflict=True,
                        conflict_type="WORKER_VERIFIER_MISMATCH",
                        reason="Worker claimed PASS but Verifier recorded FAIL; verifier outranks self-report",
                        effective_record=verified_receipt,
                    )

            # Case E: Verified result exists, but a later unverified status claims otherwise
            # Verified receipt is preserved against any lower authority update
            resolved_status = (
                "VERIFIED_COMPLETE"
                if verified_receipt.status.upper() in ("COMPLETE", "COMPLETED", "DONE", "PASS")
                else "FAILED"
            )
            has_conflicting_unverified = any(
                r.source_type != "VERIFIED_RECEIPT" and r.status.upper() != verified_receipt.status.upper()
                for r in records
            )
            return ResolutionVerdict(
                task_id=task_id,
                resolved_status=resolved_status,
                winning_source="VERIFIED_RECEIPT",
                is_conflict=has_conflicting_unverified,
                conflict_type="UNCONFIRMED_OVERRIDE_PREVENTED" if has_conflicting_unverified else None,
                reason="Verified receipt preserved; lower authority cannot overwrite verified evidence",
                effective_record=verified_receipt,
            )

        # 4. Dispatch Generation Check (Case C)
        max_generation = max((r.generation for r in records), default=1)
        stale_checkpoints = [
            r for r in records
            if r.source_type == "SESSION_CHECKPOINT" and r.generation < max_generation
        ]
        active_records = [
            r for r in records
            if not (r.source_type == "SESSION_CHECKPOINT" and r.generation < max_generation)
        ]
        stale_conflict = bool(stale_checkpoints)

        # 5. Local Session Checkpoint vs Ledger Discrepancy (Case A)
        checkpoint = next(
            (r for r in active_records if r.source_type == "SESSION_CHECKPOINT"), None
        )
        if checkpoint and ledger_record:
            cp_status = checkpoint.status.upper()
            ledger_status = ledger_record.status.upper()
            if cp_status in ("DONE", "COMPLETED") and ledger_status in ("RUNNING", "OPEN"):
                return ResolutionVerdict(
                    task_id=task_id,
                    resolved_status="TRUTH_CONFLICT",
                    winning_source="PERSISTED_LEDGER",
                    is_conflict=True,
                    conflict_type="STATUS_UNCOMMITTED",
                    reason="Local session claims DONE but Ledger is still RUNNING without receipt; uncommitted promotion blocked",
                    effective_record=ledger_record,
                )

        # 6. Default to Highest Authority Active Record
        sorted_records = sorted(
            active_records,
            key=lambda r: (int(r.authority), r.generation, r.timestamp),
            reverse=True,
        )
        top_record = sorted_records[0]

        # Check for status disagreement among comparable active sources
        distinct_statuses = {
            r.status.upper() for r in active_records
            if r.authority >= AuthorityLevel.SESSION_CHECKPOINT
        }
        status_conflict = len(distinct_statuses) > 1

        if status_conflict:
            return ResolutionVerdict(
                task_id=task_id,
                resolved_status="TRUTH_CONFLICT",
                winning_source=top_record.source_type,
                is_conflict=True,
                conflict_type="CONFLICTING_STATUS",
                reason=f"Discrepancy among authorities ({distinct_statuses}); fails closed to TRUTH_CONFLICT",
                effective_record=top_record,
            )

        resolved_st = top_record.status.upper()
        if resolved_st in ("COMPLETE", "COMPLETED", "DONE"):
            resolved_st = "DONE"
        elif resolved_st in ("FAIL", "FAILED"):
            resolved_st = "FAILED"

        return ResolutionVerdict(
            task_id=task_id,
            resolved_status=resolved_st,
            winning_source=top_record.source_type,
            is_conflict=stale_conflict,
            conflict_type="STALE_CHECKPOINT" if stale_conflict else None,
            reason="Resolved by authority ranking",
            effective_record=top_record,
        )
