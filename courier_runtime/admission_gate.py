"""Window Admission Gate: safe task admission into desktop terminal windows.

Governed by Courier V21 Universal Operating Contract & Window Custody Protocol.
Enforces that a task is admitted to a window ONLY when custody is proven,
terminal dimensions are viable (preventing 'Terminal too small' errors),
no active work is interrupted, provider capacity is verified, the workkey
is uniquely owned, and an enforceable progress gate prevents repeated no-evidence loops.
"""
from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


MIN_COLS = 80
MIN_ROWS = 24

VALID_CUSTODY_STATES = {"IDLE", "SAFE_TO_REUSE", "PARKED_VERIFIED"}


@dataclass(frozen=True)
class ExecutionAudit:
    """Enforces execution truth invariants:
    1. COMMAND_STARTED != COMMAND_COMPLETED
    2. COMMAND_COMPLETED != TEST_PASSED
    3. PASS requires exit_code == 0 and captured evidence.
    4. PASS requires pre-dispatch cost authorization.
    """
    command: str
    execution_handle: str
    started: bool
    completed: bool
    exit_code: Optional[int] = None
    output_captured: bool = False
    cost_authorized: bool = True

    @property
    def is_passed(self) -> bool:
        return (self.started and self.completed and self.exit_code == 0
                and self.output_captured and self.cost_authorized)

    def validate_verdict(self, claimed_pass: bool) -> Tuple[bool, str]:
        if not self.cost_authorized:
            return False, "COST_AUTHORIZATION_DENIED: execution was not cost-authorized before dispatch"
        if not self.started:
            return False, "EXECUTION_NOT_STARTED: command has not been launched"
        if not self.completed:
            return False, "COMMAND_STARTED_IS_NOT_COMPLETED: command is still running or handle was uncollected"
        if claimed_pass and self.exit_code != 0:
            return False, f"COMMAND_COMPLETED_IS_NOT_PASSED: exit code is {self.exit_code} != 0"
        if claimed_pass and not self.output_captured:
            return False, "MISSING_EVIDENCE: command exited 0 but stdout/stderr output was not captured"
        return True, "VERIFIED"



@dataclass(frozen=True)
class TerminalGeometry:
    cols: int
    rows: int
    width_px: Optional[int] = None
    height_px: Optional[int] = None

    @property
    def is_usable(self) -> bool:
        return self.cols >= MIN_COLS and self.rows >= MIN_ROWS


@dataclass(frozen=True)
class WindowTarget:
    window_id: str
    title: str
    host: str
    geometry: TerminalGeometry
    custody_state: str
    is_busy: bool
    is_accessible: bool = True
    session_id: Optional[str] = None


@dataclass(frozen=True)
class AdmissionDecision:
    decision: str  # ADMIT | REJECT
    reasons: List[str]
    window_id: str
    workkey: str
    session_id: str
    timestamp: float
    receipt_id: Optional[str] = None
    dedupe_key: Optional[str] = None


@dataclass(frozen=True)
class ProgressRecord:
    workkey: str
    baseline_checkpoint: str
    input_fingerprint: str
    evidence_fingerprint: Optional[str]
    status: str  # COMPLETED | BLOCKED | UNCERTAIN
    timestamp: float


class ProgressGate:
    """Enforces evidence-gated progress.

    Stops repeated analysis / status report loops by rejecting workkeys when
    baseline checkpoint and input fingerprint are unchanged and no new evidence is supplied.
    """

    def __init__(self):
        self.history: Dict[str, ProgressRecord] = {}

    def evaluate_cycle(
        self,
        workkey: str,
        owner: str,
        input_fingerprint: str,
        baseline_checkpoint: str,
        new_evidence_fingerprint: Optional[str] = None,
        is_uncertain: bool = False,
    ) -> Tuple[bool, str]:
        # Scenario D: Non-idempotent uncertain outcome fails closed
        if is_uncertain:
            return False, "UNCERTAIN_OUTCOME_FAIL_CLOSED: previous execution outcome is uncertain; blind retry blocked"

        last = self.history.get(workkey)
        if last is not None:
            # Scenario A: Completed workkey selected again without new evidence
            if last.status == "COMPLETED" and (
                new_evidence_fingerprint is None or new_evidence_fingerprint == last.evidence_fingerprint
            ):
                return False, f"ALREADY_COMPLETED: workkey '{workkey}' already completed with this evidence; no duplicate work admitted"

            # Scenario B: Same analysis runs against unchanged baseline, fingerprint, and evidence
            if (
                last.baseline_checkpoint == baseline_checkpoint
                and last.input_fingerprint == input_fingerprint
                and (new_evidence_fingerprint is None or new_evidence_fingerprint == last.evidence_fingerprint)
            ):
                return False, f"LOOP_PREVENTED: workkey '{workkey}' has unchanged baseline '{baseline_checkpoint[:8]}' and fingerprint '{input_fingerprint[:8]}' without new evidence"

        # Scenarios C & F: Valid new work or new evidence admitted
        return True, "PROGRESS_ADMISSIBLE"

    def record_outcome(
        self,
        workkey: str,
        baseline_checkpoint: str,
        input_fingerprint: str,
        evidence_fingerprint: Optional[str] = None,
        status: str = "COMPLETED",
    ) -> ProgressRecord:
        rec = ProgressRecord(
            workkey=workkey,
            baseline_checkpoint=baseline_checkpoint,
            input_fingerprint=input_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            status=status,
            timestamp=time.time(),
        )
        self.history[workkey] = rec
        return rec


class WindowAdmissionGate:
    """Evaluates window readiness and controls single-task admission."""

    def __init__(self, heavy_job_limit: int = 1, progress_gate: Optional[ProgressGate] = None):
        self.heavy_job_limit = heavy_job_limit
        self.progress_gate = progress_gate or ProgressGate()
        self.active_admissions: Dict[str, AdmissionDecision] = {}  # window_id -> decision
        self.workkey_owners: Dict[str, str] = {}  # workkey -> session_id
        self.dedupe_seen: Set[str] = set()

    def evaluate(
        self,
        target: WindowTarget,
        workkey: str,
        session_id: str,
        provider_capacity_ok: bool = True,
        current_heavy_jobs: int = 0,
        input_fingerprint: Optional[str] = None,
        baseline_checkpoint: Optional[str] = None,
        new_evidence_fingerprint: Optional[str] = None,
        is_uncertain: bool = False,
        estimated_cost_eur: Optional[float] = 0.0,
        cost_grant: Any = None,
        resource_id: str = "google_antigravity_plus",
    ) -> AdmissionDecision:
        reasons = []
        now = time.time()

        # 1. Terminal Dimensions Check (Root cause of "Terminal too small")
        if not target.geometry.is_usable:
            reasons.append(
                f"TERMINAL_TOO_SMALL: {target.geometry.cols}x{target.geometry.rows} "
                f"< required {MIN_COLS}x{MIN_ROWS}"
            )

        # 2. Window Accessibility & Focus
        if not target.is_accessible:
            reasons.append(f"WINDOW_INACCESSIBLE: window {target.window_id} cannot receive input")

        # 3. Active Work Detection
        if target.is_busy:
            reasons.append(f"ACTIVE_WORK_IN_PROGRESS: window {target.window_id} is currently busy")

        # 4. Custody Proof
        if target.custody_state not in VALID_CUSTODY_STATES:
            reasons.append(
                f"UNPROVEN_CUSTODY: custody state '{target.custody_state}' is not safe to admit"
            )

        # 5. Workkey Ownership & Collision Check
        existing_owner = self.workkey_owners.get(workkey)
        if existing_owner and existing_owner != session_id:
            reasons.append(f"WORKKEY_COLLISION: workkey '{workkey}' is owned by session '{existing_owner}'")

        # 6. Provider & Host Capacity Check (Scenario E)
        if not provider_capacity_ok:
            reasons.append("PROVIDER_CAPACITY_EXHAUSTED: provider quota or rate limit active")

        if current_heavy_jobs >= self.heavy_job_limit:
            reasons.append(
                f"HOST_PRESSURE: heavy jobs {current_heavy_jobs} >= limit {self.heavy_job_limit}"
            )

        # 6b. Cost & Spend Authorization Gate (Zero unauthorized spend enforcement)
        from scripts.resource_policy import CostGate
        cost_eval = CostGate.evaluate_spend_request(
            resource_id=resource_id,
            estimated_cost_eur=estimated_cost_eur if estimated_cost_eur is not None else float("nan"),
            grant=cost_grant,
        )
        if not cost_eval.get("allowed", False):
            reasons.append(f"COST_AUTHORIZATION_DENIED: {cost_eval.get('reason')}")

        # 7. Deduplication Key Check (Prevent duplicate task injection)
        dedupe_key = hashlib.sha256(f"{target.window_id}:{workkey}:{session_id}".encode()).hexdigest()[:16]
        if dedupe_key in self.dedupe_seen:
            reasons.append(f"DUPLICATE_SUBMISSION: task '{workkey}' already admitted via key {dedupe_key}")

        # 8. Progress Gate Check (Scenarios A, B, C, D, F)
        if input_fingerprint is not None and baseline_checkpoint is not None:
            can_proceed, code = self.progress_gate.evaluate_cycle(
                workkey=workkey,
                owner=session_id,
                input_fingerprint=input_fingerprint,
                baseline_checkpoint=baseline_checkpoint,
                new_evidence_fingerprint=new_evidence_fingerprint,
                is_uncertain=is_uncertain,
            )
            if not can_proceed:
                reasons.append(code)

        if reasons:
            return AdmissionDecision(
                decision="REJECT",
                reasons=reasons,
                window_id=target.window_id,
                workkey=workkey,
                session_id=session_id,
                timestamp=now,
                dedupe_key=dedupe_key,
            )

        # Generate Admission Receipt
        receipt_id = f"adm-{hashlib.sha256(f'{dedupe_key}:{now}'.encode()).hexdigest()[:12]}"
        decision = AdmissionDecision(
            decision="ADMIT",
            reasons=["All custody, dimension, ownership, capacity, and progress gates passed"],
            window_id=target.window_id,
            workkey=workkey,
            session_id=session_id,
            timestamp=now,
            receipt_id=receipt_id,
            dedupe_key=dedupe_key,
        )

        # Commit reservation
        self.active_admissions[target.window_id] = decision
        self.workkey_owners[workkey] = session_id
        self.dedupe_seen.add(dedupe_key)
        return decision

    def record_progress(
        self,
        workkey: str,
        baseline_checkpoint: str,
        input_fingerprint: str,
        evidence_fingerprint: Optional[str] = None,
        status: str = "COMPLETED",
    ) -> ProgressRecord:
        """Records completed or blocked work to update progress memory."""
        return self.progress_gate.record_outcome(
            workkey=workkey,
            baseline_checkpoint=baseline_checkpoint,
            input_fingerprint=input_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            status=status,
        )

    def release(self, window_id: str, workkey: str):
        """Release admission lock upon task completion or retirement."""
        self.active_admissions.pop(window_id, None)
        self.workkey_owners.pop(workkey, None)


@dataclass(frozen=True)
class QueueBatchResult:
    admitted: List[str]
    buffered: List[str]
    rejected_duplicates: List[str]
    rejected_completed: List[str]
    capacity_denied: List[str]
    status: str  # ADMITTED | SATURATED_BACKPRESSURE | CAPACITY_EXHAUSTED | HARVEST_REQUIRED | TRUE_IDLE
    reason: str


class QueueBackpressureGate:
    """Controls queue intake admission, enforces batch concurrency bounds, and prevents model polling loops.
    
    Invariants:
    1. Zero duplicate executions: Duplicate workkeys in the same batch or queue are deduplicated immediately.
    2. Zero re-execution of completed work: Tasks marked completed without new evidence are rejected.
    3. Host capacity protection: If current heavy jobs >= limit, admission fails closed (CAPACITY_EXHAUSTED).
    4. Bounded concurrency / Backpressure: Limits max in-flight admissions to prevent host memory exhaustion.
    5. Clean idle / Harvester priority: If queue has no new tasks but unharvested results exist -> HARVEST_REQUIRED;
       only when queue is empty and all results are harvested -> TRUE_IDLE.
    """

    def __init__(
        self,
        max_batch_size: int = 5,
        heavy_job_limit: int = 1,
        progress_gate: Optional[ProgressGate] = None,
    ):
        self.max_batch_size = max_batch_size
        self.heavy_job_limit = heavy_job_limit
        self.progress_gate = progress_gate or ProgressGate()
        self.admitted_in_flight: Set[str] = set()

    def process_queue_intake(
        self,
        candidate_workkeys: Sequence[str],
        current_heavy_jobs: int = 0,
        unharvested_results_count: int = 0,
        is_heavy_batch: bool = False,
    ) -> QueueBatchResult:
        if not candidate_workkeys and not self.admitted_in_flight:
            if unharvested_results_count > 0:
                return QueueBatchResult(
                    admitted=[],
                    buffered=[],
                    rejected_duplicates=[],
                    rejected_completed=[],
                    capacity_denied=[],
                    status="HARVEST_REQUIRED",
                    reason=f"{unharvested_results_count} completed results pending harvest before idle",
                )
            return QueueBatchResult(
                admitted=[],
                buffered=[],
                rejected_duplicates=[],
                rejected_completed=[],
                capacity_denied=[],
                status="TRUE_IDLE",
                reason="Queue is empty and all results are harvested; zero model polling required",
            )

        admitted: List[str] = []
        buffered: List[str] = []
        rejected_duplicates: List[str] = []
        rejected_completed: List[str] = []
        capacity_denied: List[str] = []

        seen_in_batch: Set[str] = set()
        clean_candidates: List[str] = []

        # 1. Deduplication (Scenario A)
        for key in candidate_workkeys:
            if key in seen_in_batch or key in self.admitted_in_flight:
                rejected_duplicates.append(key)
            else:
                seen_in_batch.add(key)
                clean_candidates.append(key)

        # 2. Check for already completed tasks (Scenario D)
        filtered_candidates: List[str] = []
        for key in clean_candidates:
            record = self.progress_gate.history.get(key)
            if record is not None and record.status == "COMPLETED":
                rejected_completed.append(key)
            else:
                filtered_candidates.append(key)

        # 3. Host Capacity / Heavy Job Gate (Scenario C)
        if is_heavy_batch and current_heavy_jobs >= self.heavy_job_limit:
            capacity_denied = list(filtered_candidates)
            return QueueBatchResult(
                admitted=[],
                buffered=[],
                rejected_duplicates=rejected_duplicates,
                rejected_completed=rejected_completed,
                capacity_denied=capacity_denied,
                status="CAPACITY_EXHAUSTED",
                reason=f"Host heavy jobs ({current_heavy_jobs}) >= limit ({self.heavy_job_limit}); admission denied",
            )

        # 4. Bounded Admission & Backpressure (Scenario B)
        available_slots = max(0, self.max_batch_size - len(self.admitted_in_flight))
        for idx, key in enumerate(filtered_candidates):
            if idx < available_slots:
                admitted.append(key)
                self.admitted_in_flight.add(key)
            else:
                buffered.append(key)

        status = "ADMITTED"
        reason = f"Admitted {len(admitted)} tasks"
        if buffered:
            status = "SATURATED_BACKPRESSURE"
            reason = f"Admitted {len(admitted)} tasks; {len(buffered)} buffered under backpressure (max {self.max_batch_size})"

        return QueueBatchResult(
            admitted=admitted,
            buffered=buffered,
            rejected_duplicates=rejected_duplicates,
            rejected_completed=rejected_completed,
            capacity_denied=capacity_denied,
            status=status,
            reason=reason,
        )

    def release_task(self, workkey: str):
        """Release completed or aborted task from in-flight backpressure tracking."""
        self.admitted_in_flight.discard(workkey)

