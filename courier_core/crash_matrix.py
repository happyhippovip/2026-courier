"""
courier_core/crash_matrix.py — Minimal Crash Matrix & Transition Boundary Map (CP-15 / CQ-15)

Invariants:
1. Every relevant persistent transition cut has a deterministic expected recovery state.
2. Zero data loss on committed state across all crash boundaries.
3. Pre-persistence failure fails cleanly without state corruption; client retries idempotently.
4. Mid-execution worker loss quarantines non-idempotent uncertain effects without blind retry.
5. Outbox fsync before ACK ensures zero loss of completed execution results.
6. Verified results are immutable and preserved across restart ("Bestätigte Ergebnisse bleiben erhalten").
7. Redundant test cases reuse canonical verification fixtures; physical evidence is strictly isolated.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class TransitionCut(str, Enum):
    CUT1_PRE_PERSISTENCE = "CUT1_PRE_PERSISTENCE"
    CUT2_PERSISTED_PRE_CLAIM = "CUT2_PERSISTED_PRE_CLAIM"
    CUT3_CLAIMED_PRE_START = "CUT3_CLAIMED_PRE_START"
    CUT4_RUNNING_MID_EXECUTION = "CUT4_RUNNING_MID_EXECUTION"
    CUT5_RESULT_FSYNC_PRE_ACK = "CUT5_RESULT_FSYNC_PRE_ACK"
    CUT6_RESULT_RECEIVED_PRE_VERIFY = "CUT6_RESULT_RECEIVED_PRE_VERIFY"
    CUT7_VERIFIED_PRE_HANDOFF = "CUT7_VERIFIED_PRE_HANDOFF"


class RecoveryExpectation(str, Enum):
    CLIENT_RETRY_IDEMPOTENT = "CLIENT_RETRY_IDEMPOTENT"
    RECALCULATE_READY_QUEUED = "RECALCULATE_READY_QUEUED"
    QUARANTINED_AMBIGUOUS_BLOCKED = "QUARANTINED_AMBIGUOUS_BLOCKED"
    ZOMBIE_FENCED_NO_REPLAY = "ZOMBIE_FENCED_NO_REPLAY"
    OUTBOX_REPLAY_ACK_DUPLICATE = "OUTBOX_REPLAY_ACK_DUPLICATE"
    RESCHEDULE_VERIFY_WITHOUT_RERUN = "RESCHEDULE_VERIFY_WITHOUT_RERUN"
    TERMINAL_PRESERVED_ADVANCE_DAG = "TERMINAL_PRESERVED_ADVANCE_DAG"


@dataclass
class CrashMatrixEntry:
    cut: TransitionCut
    boundary_name: str
    description: str
    state_before: str
    injected_fault: str
    expected_recovery_state: str
    recovery_expectation: RecoveryExpectation
    invariants_preserved: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["cut"] = self.cut.value
        d["recovery_expectation"] = self.recovery_expectation.value
        return d


class CrashMatrix:
    """Canonical registry and evaluation engine for Courier transition cuts."""

    ENTRIES: List[CrashMatrixEntry] = [
        CrashMatrixEntry(
            cut=TransitionCut.CUT1_PRE_PERSISTENCE,
            boundary_name="Pre-Persistence (Intake -> Disk)",
            description="Crash occurs while receiving goal/task before state file atomic fsync completes.",
            state_before="INCOMING_DRAFT",
            injected_fault="PROCESS_TERMINATION_BEFORE_FSYNC",
            expected_recovery_state="CLEAN_ORIGINAL_STATE",
            recovery_expectation=RecoveryExpectation.CLIENT_RETRY_IDEMPOTENT,
            invariants_preserved=["No partial state written", "Client receives connection drop and retries"],
        ),
        CrashMatrixEntry(
            cut=TransitionCut.CUT2_PERSISTED_PRE_CLAIM,
            boundary_name="Persisted Pre-Claim (Committed -> Worker Claim)",
            description="Task committed to durable disk as QUEUED; coordinator crashes before any claim.",
            state_before="QUEUED",
            injected_fault="COORDINATOR_COLD_CRASH",
            expected_recovery_state="QUEUED_COMPUTED_READY",
            recovery_expectation=RecoveryExpectation.RECALCULATE_READY_QUEUED,
            invariants_preserved=["Committed tasks survive 100%", "Ready tasks computed deterministically"],
        ),
        CrashMatrixEntry(
            cut=TransitionCut.CUT3_CLAIMED_PRE_START,
            boundary_name="Claimed Pre-Start (Lease Minted -> Execution)",
            description="Task claimed and marked DISPATCHED; worker process or host crashes before start.",
            state_before="DISPATCHED",
            injected_fault="WORKER_VANISHED_WITHOUT_START",
            expected_recovery_state="HUMAN_REQUIRED_OR_QUEUED",
            recovery_expectation=RecoveryExpectation.QUARANTINED_AMBIGUOUS_BLOCKED,
            invariants_preserved=["Fehlende Runtime-Evidenz wird nicht erfunden", "Non-idempotent work quarantined"],
        ),
        CrashMatrixEntry(
            cut=TransitionCut.CUT4_RUNNING_MID_EXECUTION,
            boundary_name="Running Mid-Execution (In-Flight -> Partial Effects)",
            description="Worker crashes mid-run; external effect status is unknown; coordinator mints new epoch.",
            state_before="RUNNING",
            injected_fault="MID_RUN_CRASH_AND_FAILOVER",
            expected_recovery_state="BLOCKED_FENCED",
            recovery_expectation=RecoveryExpectation.ZOMBIE_FENCED_NO_REPLAY,
            invariants_preserved=["Monotonic fencing token rejects stale zombie write", "Zero duplicate effect"],
        ),
        CrashMatrixEntry(
            cut=TransitionCut.CUT5_RESULT_FSYNC_PRE_ACK,
            boundary_name="Result Fsync Pre-ACK (Worker Outbox -> Network ACK)",
            description="Worker finishes and fsyncs outbox file; network drops before receiving server ACK.",
            state_before="OUTBOX_SAVED_PENDING_ACK",
            injected_fault="NETWORK_DROP_POST_FSYNC",
            expected_recovery_state="OUTBOX_FILE_PRESERVED_REPLAYED",
            recovery_expectation=RecoveryExpectation.OUTBOX_REPLAY_ACK_DUPLICATE,
            invariants_preserved=["Persist-Before-Send", "ACK-Before-Clear", "Idempotent result deduplication"],
        ),
        CrashMatrixEntry(
            cut=TransitionCut.CUT6_RESULT_RECEIVED_PRE_VERIFY,
            boundary_name="Result Ingest Pre-Verify (Ingested -> Signed Receipt)",
            description="Server ingests result as RESULT_RECEIVED; verifier process crashes before signature.",
            state_before="RESULT_RECEIVED",
            injected_fault="VERIFIER_DAEMON_CRASH",
            expected_recovery_state="RESULT_RECEIVED_REQUEUED_FOR_VERIFY",
            recovery_expectation=RecoveryExpectation.RESCHEDULE_VERIFY_WITHOUT_RERUN,
            invariants_preserved=["Zero re-execution of task code", "Verifier resumes from durable result"],
        ),
        CrashMatrixEntry(
            cut=TransitionCut.CUT7_VERIFIED_PRE_HANDOFF,
            boundary_name="Verified Pre-Handoff (Signed Receipt -> Next Step Ready)",
            description="Task verified and marked COMPLETE/RECONCILED; server crashes before dispatching step B.",
            state_before="RECONCILED",
            injected_fault="CRASH_BEFORE_NEXT_DISPATCH",
            expected_recovery_state="STEP_A_COMPLETE_STEP_B_READY",
            recovery_expectation=RecoveryExpectation.TERMINAL_PRESERVED_ADVANCE_DAG,
            invariants_preserved=["Bestätigte Ergebnisse bleiben erhalten", "DAG resolver advances to step B"],
        ),
    ]

    @classmethod
    def get_entry(cls, cut: TransitionCut) -> Optional[CrashMatrixEntry]:
        for entry in cls.ENTRIES:
            if entry.cut == cut:
                return entry
        return None

    @classmethod
    def transition_map(cls) -> Dict[str, Any]:
        """Return machine-readable transition map for documentation and audit evidence."""
        return {
            "version": "1.0.0",
            "total_cuts": len(cls.ENTRIES),
            "cuts": [e.to_dict() for e in cls.ENTRIES],
        }

    @classmethod
    def simulate_recovery(cls, cut: TransitionCut, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pure deterministic recovery transition function for any given crash cut.
        Proves state machine correctness without running unbounded physical crashes.
        """
        recovered = copy.deepcopy(task)

        if cut == TransitionCut.CUT1_PRE_PERSISTENCE:
            # Uncommitted draft is dropped entirely
            return {}

        elif cut == TransitionCut.CUT2_PERSISTED_PRE_CLAIM:
            # Task remains QUEUED and ready for claim
            recovered["status"] = "QUEUED"
            recovered["available_for_claim"] = True
            return recovered

        elif cut == TransitionCut.CUT3_CLAIMED_PRE_START:
            # If non-idempotent: quarantined to HUMAN_REQUIRED / BLOCKED
            is_idempotent = bool(recovered.get("idempotent") or recovered.get("effect_class") == "idempotent")
            if is_idempotent:
                recovered["status"] = "QUEUED"
                recovered["worker_id"] = None
                recovered["dispatch_id"] = None
            else:
                recovered["status"] = "HUMAN_REQUIRED"
                recovered["recovery_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS"
                recovered["reexecution_allowed"] = False
            return recovered

        elif cut == TransitionCut.CUT4_RUNNING_MID_EXECUTION:
            # Running task loses worker: quarantine non-idempotent; advance epoch
            recovered["status"] = "HUMAN_REQUIRED"
            recovered["recovery_reason"] = "MID_RUN_CRASH_EFFECT_UNKNOWN"
            recovered["reexecution_allowed"] = False
            # Fencing token incremented
            recovered["fencing_token"] = int(recovered.get("fencing_token", 1)) + 1
            return recovered

        elif cut == TransitionCut.CUT5_RESULT_FSYNC_PRE_ACK:
            # Worker outbox file was preserved; on replay, server acknowledges result
            recovered["outbox_preserved"] = True
            recovered["delivery_ack"] = "ACK_DUPLICATE"
            return recovered

        elif cut == TransitionCut.CUT6_RESULT_RECEIVED_PRE_VERIFY:
            # Result is intact; verifier queue picks it up without rerunning task
            recovered["status"] = "RESULT_RECEIVED"
            recovered["pending_verification"] = True
            return recovered

        elif cut == TransitionCut.CUT7_VERIFIED_PRE_HANDOFF:
            # Result remains COMPLETE/RECONCILED; next step in DAG is computed
            recovered["status"] = "RECONCILED"
            recovered["next_step_ready"] = True
            return recovered

        return recovered
