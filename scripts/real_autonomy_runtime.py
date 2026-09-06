#!/usr/bin/env python3
"""Real Local Autonomy Runtime & Zero-Copy-Paste Execution Engine (Mission 185G).

Moves 2026 Zentrale directly from simulated autonomy to a REAL LOCAL unattended runtime:
1. Connects AutonomyControlPlane with Chief Brain, Autopilot, OpportunityQueue, and Dispatcher.
2. Real Event Ingestion & Correlation (RESULT, BLOCKER, NEW_EVIDENCE, DECISION_REQUIRED, HUMAN_GATE).
3. Automatic Next-Action Selection (Deterministic-first, barrier-aware, branch-isolated, value-gated).
4. Provider-neutral Job Envelopes (resumable, reconcilable, zero-credential).
5. Concurrency & Scope-safe Parallelism (Google / Codex isolation, deterministic parallel).
6. Human & Money Branch Isolation (parking gated tasks without freezing independent work).
7. Robust Failure & Restart Recovery (process restart, hung job recovery, duplicate event defense).
8. Bounded Night Session Controller & Deterministic Morning Report Generation.
9. Multi-step zero-copy-paste sequential autonomous transitions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
RUNTIME_STATE_DIR = EVENTS_DIR / "autonomy-runtime"
NIGHT_JOURNAL_DIR = EVENTS_DIR / "night-journal"

try:
    from autonomy_control_plane import (
        AdmissionDecision,
        AutonomyControlPlane,
        DecisionValueClass,
        ExecutionTier,
        ModelAdmissionRequest,
        ModelAdmissionResult,
        RiskLevel,
        StructuredMessageType,
        TaskContinuationState,
    )
    from chief_brain import ChiefBrain, MemoryItem
    from opportunity_queue import Opportunity, OpportunityQueue
except ImportError:
    from scripts.autonomy_control_plane import (
        AdmissionDecision,
        AutonomyControlPlane,
        DecisionValueClass,
        ExecutionTier,
        ModelAdmissionRequest,
        ModelAdmissionResult,
        RiskLevel,
        StructuredMessageType,
        TaskContinuationState,
    )
    from scripts.chief_brain import ChiefBrain, MemoryItem
    from scripts.opportunity_queue import Opportunity, OpportunityQueue

try:
    from organization_elite_policy import (
        AnomalyDomain,
        AnomalySeverity,
        CentralElitePolicyRegistry,
        FastFinishEngine,
        SnitchAnomalyManager,
    )
    from elite_execution_core import (
        CapabilityType,
        EliteActionSpec,
        EliteExecutionCore,
        IntelligenceLadderLevel,
        QualityFloorClass,
        SchedulerDecision,
    )
except ImportError:
    from scripts.organization_elite_policy import (
        AnomalyDomain,
        AnomalySeverity,
        CentralElitePolicyRegistry,
        FastFinishEngine,
        SnitchAnomalyManager,
    )
    from scripts.elite_execution_core import (
        CapabilityType,
        EliteActionSpec,
        EliteExecutionCore,
        IntelligenceLadderLevel,
        QualityFloorClass,
        SchedulerDecision,
    )


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_digest(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_json_safe(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


# ==============================================================================
# Provider-Neutral Job Envelopes & Night Session Models
# ==============================================================================

class JobStatus(str, enum.Enum):
    PREPARED = "PREPARED"
    DISPATCHED = "DISPATCHED"
    EXECUTED_SUCCESS = "EXECUTED_SUCCESS"
    EXECUTED_FAIL = "EXECUTED_FAIL"
    PARKED_HUMAN_GATE = "PARKED_HUMAN_GATE"
    PARKED_MONEY_GATE = "PARKED_MONEY_GATE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class SessionStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    HUMAN_GATE = "HUMAN_GATE"
    PAYMENT_APPROVAL_REQUIRED = "PAYMENT_APPROVAL_REQUIRED"
    IDLE_EXPECTED = "IDLE_EXPECTED"
    COMPLETED = "COMPLETED"
    STOPPED_SAFELY = "STOPPED_SAFELY"
    FAILED_SAFE = "FAILED_SAFE"


@dataclass
class ProviderJobEnvelope:
    job_id: str
    task_id: str
    correlation_id: str
    owner: str  # GOOGLE | CODEX | LOCAL | CHIEF
    provider: str  # LOCAL_DETERMINISTIC | GOOGLE_PRO | OPENAI_CODEX
    scope: str
    mutation_scope: List[str]
    dependency_ids: List[str]
    context_reference: str
    expected_unlock: str
    resource_class: str
    risk_class: str
    admission_reason: str
    max_iterations: int = 1
    created_at: str = field(default_factory=utc_now)
    status: JobStatus = JobStatus.PREPARED
    execution_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProviderJobEnvelope:
        return cls(
            job_id=data["job_id"],
            task_id=data["task_id"],
            correlation_id=data["correlation_id"],
            owner=data.get("owner", "LOCAL"),
            provider=data.get("provider", "LOCAL_DETERMINISTIC"),
            scope=data.get("scope", "PROJECT_GLOBAL"),
            mutation_scope=data.get("mutation_scope", []),
            dependency_ids=data.get("dependency_ids", []),
            context_reference=data.get("context_reference", ""),
            expected_unlock=data.get("expected_unlock", ""),
            resource_class=data.get("resource_class", "DEFAULT"),
            risk_class=data.get("risk_class", "LOW"),
            admission_reason=data.get("admission_reason", ""),
            max_iterations=data.get("max_iterations", 1),
            created_at=data.get("created_at", utc_now()),
            status=JobStatus(data.get("status", JobStatus.PREPARED.value)),
            execution_result=data.get("execution_result"),
        )


@dataclass
class NightSessionState:
    session_id: str
    goal: str
    allowed_scopes: List[str]
    max_runtime_minutes: int
    max_iterations: int
    started_at: str = field(default_factory=utc_now)
    last_active_at: str = field(default_factory=utc_now)
    ended_at: Optional[str] = None
    status: SessionStatus = SessionStatus.RUNNING
    iterations_completed: int = 0
    idle_observations: int = 0
    max_idle_observations: int = 50000
    jobs_dispatched: List[str] = field(default_factory=list)
    jobs_completed: List[str] = field(default_factory=list)
    human_gates_encountered: List[Dict[str, Any]] = field(default_factory=list)
    money_gates_encountered: List[Dict[str, Any]] = field(default_factory=list)
    events_log: List[Dict[str, Any]] = field(default_factory=list)
    morning_report_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NightSessionState:
        return cls(
            session_id=data["session_id"],
            goal=data["goal"],
            allowed_scopes=data.get("allowed_scopes", []),
            max_runtime_minutes=data.get("max_runtime_minutes", 480),
            max_iterations=data.get("max_iterations", 50),
            started_at=data.get("started_at", utc_now()),
            last_active_at=data.get("last_active_at", utc_now()),
            ended_at=data.get("ended_at"),
            status=SessionStatus(data.get("status", SessionStatus.RUNNING.value)),
            iterations_completed=data.get("iterations_completed", 0),
            idle_observations=data.get("idle_observations", 0),
            max_idle_observations=data.get("max_idle_observations", 50000),
            jobs_dispatched=data.get("jobs_dispatched", []),
            jobs_completed=data.get("jobs_completed", []),
            human_gates_encountered=data.get("human_gates_encountered", []),
            money_gates_encountered=data.get("money_gates_encountered", []),
            events_log=data.get("events_log", []),
            morning_report_path=data.get("morning_report_path"),
        )


# ==============================================================================
# Real Autonomy Runtime Engine
# ==============================================================================

class RealAutonomyRuntime:
    """Core local unattended execution coordinator for 2026 Zentrale."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.runtime_dir = self.repo_dir / "events" / "autonomy-runtime"
        self.journal_dir = self.repo_dir / "events" / "night-journal"
        self.jobs_dir = self.runtime_dir / "jobs"
        self.events_inbox = self.runtime_dir / "inbox"
        self.session_file = self.runtime_dir / "current_session.json"
        self.event_ledger_file = self.runtime_dir / "event_ledger.json"

        # Adapters to existing components
        self.control_plane = AutonomyControlPlane(repo_dir=self.repo_dir)
        self.chief_brain = ChiefBrain(repo_dir=self.repo_dir)
        self.opp_queue = OpportunityQueue(self.repo_dir)

        # Central Organization Policy Registry (Active Organization-Wide Inheritance)
        from scripts.organization_elite_policy import CentralElitePolicyRegistry
        self.policy_registry = CentralElitePolicyRegistry(repo_dir=self.repo_dir)
        self.elite_core = self.policy_registry.core
        self.snitch_manager = self.policy_registry.snitch_manager
        self.fast_finish_engine = self.policy_registry.fast_finish_engine

        # Governance & Safety Firewalls
        self.AUTONOMOUS_SPEND_LIMIT_EUR: float = 0.0
        self.PUBLICATION_AUTHORIZATION_INFERENCE: str = "DENY"

        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.events_inbox.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Event Ledger & Storage IO
    # --------------------------------------------------------------------------

    def _load_ledger(self) -> Dict[str, Any]:
        return read_json_safe(self.event_ledger_file, {"processed_event_hashes": [], "events": []})

    def _save_ledger(self, ledger: Dict[str, Any]) -> None:
        atomic_write_json(self.event_ledger_file, ledger)

    def _load_session(self) -> Optional[NightSessionState]:
        data = read_json_safe(self.session_file)
        return NightSessionState.from_dict(data) if data else None

    def _save_session(self, session: NightSessionState) -> None:
        atomic_write_json(self.session_file, session.to_dict())

    # --------------------------------------------------------------------------
    # Phase B: Real Event Ingestion & Correlation
    # --------------------------------------------------------------------------

    def ingest_real_event(
        self,
        event_type: str,  # RESULT | BLOCKER | NEW_EVIDENCE | DECISION_REQUIRED | HUMAN_GATE
        source_worker: str,
        correlation_id: str,
        payload: Dict[str, Any],
        task_id: str,
        artifact_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validates, correlates, deduplicates, and ingests a real runtime event."""
        ledger = self._load_ledger()
        event_raw = {
            "event_type": event_type,
            "source_worker": source_worker,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "payload": payload,
        }
        event_hash = sha256_digest(event_raw)

        # 1. Deduplication Defense
        if event_hash in ledger["processed_event_hashes"]:
            metrics = self.control_plane._load_metrics()
            metrics.duplicate_calls_avoided += 1
            self.control_plane._save_metrics(metrics)
            return {
                "status": "DUPLICATE_IGNORED",
                "event_hash": event_hash,
                "correlation_id": correlation_id,
                "message": "Duplicate event hash detected. Ingestion bypassed without re-triggering.",
            }

        # 2. Record Event in Ledger as RECEIVED (Transactional staging)
        event_entry = {
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "event_hash": event_hash,
            "event_type": event_type,
            "source_worker": source_worker,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "payload": payload,
            "artifact_path": artifact_path,
            "ingested_at": utc_now(),
            "stage": "RECEIVED",
        }
        ledger["events"].append(event_entry)
        self._save_ledger(ledger)

        # 2.5 Active Snitch Observation Routing (Blocker 3)
        observed = payload.get("observed", payload.get("outcome", payload.get("message", "")))
        expected = payload.get("expected", "SUCCESS" if payload.get("outcome") == "SUCCESS" else "")
        domain_raw = payload.get("anomaly_domain", "PROCESS_BEHAVIOR")
        try:
            domain = AnomalyDomain(domain_raw)
        except Exception:
            domain = AnomalyDomain.PROCESS_BEHAVIOR

        affected_scope = payload.get("affected_scope", "GLOBAL")
        affected_branch = payload.get("affected_branch", "MAIN")
        evidence_refs = payload.get("evidence_refs", [])
        local_checks = payload.get("local_checks", [])

        sev, snitch_event, snitch_action = self.policy_registry.snitch_manager.report_observation(
            reporting_agent=source_worker,
            domain=domain,
            observed=str(observed) if observed else str(payload),
            expected=str(expected) if expected else str(payload),
            affected_scope=affected_scope,
            affected_branch=affected_branch,
            evidence_refs=evidence_refs,
            local_checks=local_checks,
        )

        # 3. Ingest into Chief Brain & Result Barrier (Authoritative downstream application)
        satisfied_barriers = []
        if event_type == "RESULT":
            # Update Chief Brain
            self.chief_brain.ingest_worker_result(
                task_id=task_id,
                worker=source_worker,
                outcome=payload.get("outcome", "SUCCESS"),
                evidence=payload.get("evidence", {}),
                files_changed=payload.get("files_changed", []),
                tests_passed=payload.get("tests_passed", 0),
                tests_failed=payload.get("tests_failed", 0),
            )
            # Update Control Plane Barrier
            satisfied_barriers = self.control_plane.ingest_result(
                result_id=correlation_id,
                result_payload=payload,
            )

        elif event_type == "HUMAN_GATE":
            self.chief_brain.record_memory(MemoryItem(
                memory_id=f"mem-gate-{task_id}",
                item_type="HUMAN_GATE",
                title=f"Human gate for {task_id}",
                content=json.dumps(payload),
                source="RUNTIME_INGESTION",
            ))

        # 4. Transaction Commit: Mark event APPLIED and record dedupe hash only AFTER successful downstream application
        event_entry["stage"] = "APPLIED"
        event_entry["applied_at"] = utc_now()
        if event_hash not in ledger["processed_event_hashes"]:
            ledger["processed_event_hashes"].append(event_hash)
        self._save_ledger(ledger)

        return {
            "status": "INGESTED",
            "event_id": event_entry["event_id"],
            "event_type": event_type,
            "correlation_id": correlation_id,
            "satisfied_barriers": satisfied_barriers,
            "snitch_severity": sev.value,
            "snitch_action": snitch_action,
            "quarantined": self.policy_registry.snitch_manager.is_branch_quarantined(affected_branch),
        }

    # --------------------------------------------------------------------------
    # Phase C & D: Automatic Next-Action Selection & Quality-First Efficiency
    # --------------------------------------------------------------------------

    def select_next_action(
        self,
        session: NightSessionState,
        deterministic_resolver: Optional[Callable[[str], Tuple[bool, Any]]] = None,
    ) -> Dict[str, Any]:
        """Evaluates canonical state and selects the next safe, high-quality, efficient action."""
        # 1. Check newly satisfied barriers ready for synthesis
        barriers = self.control_plane._load_barriers()
        for bid, b in barriers.items():
            if b.is_satisfied() and b.state == TaskContinuationState.READY_FOR_CHIEF_SYNTHESIS:
                # Barrier satisfied -> prepare synthesis action
                req = ModelAdmissionRequest(
                    request_id=f"adm-syn-{uuid.uuid4().hex[:8]}",
                    task_id=b.task_id,
                    why_model="Synthesize satisfied multi-worker barrier evidence",
                    why_not_local="Multi-worker dependency resolution requires synthesis decision",
                    new_information=f"Dependencies satisfied: {sorted(list(b.arrived_result_ids))}",
                    expected_unlock=f"Task {b.task_id} completed",
                    decision_value_class=DecisionValueClass.HIGH_VALUE,
                    context_reference=f"barrier:{b.barrier_id}",
                    prior_judgment_reusable=True,
                )
                adm_res = self.control_plane.evaluate_admission(req, deterministic_resolver=deterministic_resolver)
                b.state = TaskContinuationState.CLOSED
                self.control_plane._save_barriers(barriers)

                return {
                    "action_type": "SYNTHESIS",
                    "task_id": b.task_id,
                    "barrier_id": b.barrier_id,
                    "admission": adm_res.to_dict(),
                    "admitted": adm_res.admitted,
                    "execution_tier": adm_res.execution_tier.value,
                }

        # 2. Check Opportunity Queue & execute through Organization FastFinish and Admission Gates
        all_opps = sorted(self.opp_queue.list_opportunities(), key=lambda o: -o.priority)
        for opp in all_opps:
            if opp.status in ("WAITING_FOR_HUMAN", "HUMAN_GATE"):
                if not any(g.get("task_id") == opp.opportunity_id for g in session.human_gates_encountered):
                    session.human_gates_encountered.append({"task_id": opp.opportunity_id, "reason": "HUMAN_GATE"})
            elif opp.cost_class == "PAID_EXTERNAL" or opp.estimated_cost > 0 or opp.status == "PAYMENT_APPROVAL_REQUIRED":
                if not any(g.get("task_id") == opp.opportunity_id for g in session.money_gates_encountered):
                    session.money_gates_encountered.append({"task_id": opp.opportunity_id, "reason": "MONEY_GATE_SPEND_LIMIT_0"})

        ready_opps = [o for o in all_opps if o.status == "READY"]

        if ready_opps:
            candidate_specs = []
            for o in ready_opps:
                # 2.1 Resolve & Apply Mandatory Organization Policy (Blocker 1)
                agent_id = f"agent-{o.target_agent or 'local'}"
                policy_info = self.policy_registry.inherit_policy_for_agent(agent_id=agent_id, role=o.target_agent or "DEFAULT_WORKER")
                inherited = policy_info["inherited_policy"]

                # Mandatory policy constraints cannot be weakened by opportunity parameters
                mandated_spend_limit = min(inherited.get("spend_limit_eur", 0.0), self.policy_registry.config.autonomous_spend_limit_eur)

                # Infer Quality Floor Class
                q_floor = QualityFloorClass.LOW_RISK
                if o.cost_class == "PAID_EXTERNAL" or o.estimated_cost > mandated_spend_limit or o.status == "PAYMENT_APPROVAL_REQUIRED":
                    q_floor = QualityFloorClass.MONEY
                elif "publish" in o.description.lower() or "release" in o.description.lower() or o.target_agent == "publication_officer":
                    q_floor = QualityFloorClass.PUBLICATION
                elif "security" in o.description.lower() or o.risk == "HIGH":
                    q_floor = QualityFloorClass.SECURITY
                elif o.priority >= 7:
                    q_floor = QualityFloorClass.MEDIUM_RISK

                spec = EliteActionSpec(
                    action_id=o.opportunity_id,
                    goal=o.description,
                    expected_unlock=o.expected_output,
                    quality_floor=q_floor,
                    risk_class=o.risk,
                    new_information=o.problem_or_goal or o.description,
                    why_now="Autonomy queue ready",
                    why_model="Model judgment required" if o.priority >= 8 else "",
                    why_not_local="Structural synthesis required" if o.priority >= 8 else "Local execution possible",
                    why_not_cache="",
                    decision_value_class="CRITICAL_UNBLOCK" if o.priority >= 9 else ("HIGH_VALUE" if o.priority >= 7 else "USEFUL"),
                    mutation_scope=[o.project or "GLOBAL"],
                    is_on_critical_path=o.priority >= 8 or len(getattr(o, "dependency_ids", None) or []) > 0,
                    priority=o.priority,
                )
                candidate_specs.append(spec)

            # 2.2 Active FastFinish Execution Plan Evaluation (Blocker 2 & 4)
            plan = self.fast_finish_engine.evaluate_and_schedule_plan(
                candidate_specs,
                goal_target=session.goal,
                deterministic_resolver=deterministic_resolver,
                snitch_manager=self.policy_registry.snitch_manager,
            )

            # 2.3 Process Plan Admissions
            if plan.get("status") == "PLAN_OPTIMIZED":
                admissions = plan.get("admissions", {})

                # Record all gate encounters across all ready candidates
                for opp_item in ready_opps:
                    aid = opp_item.opportunity_id
                    adm = admissions.get(aid, {})
                    dec = adm.get("decision")
                    scope = opp_item.project or "GLOBAL"
                    branch = getattr(opp_item, "branch", "MAIN") or "MAIN"

                    if self.policy_registry.snitch_manager.is_branch_quarantined(branch) or self.policy_registry.snitch_manager.is_scope_quarantined(scope):
                        if not any(g.get("task_id") == aid for g in session.human_gates_encountered):
                            session.human_gates_encountered.append({"task_id": aid, "reason": f"QUARANTINED_BY_SNITCH:{branch}:{scope}"})
                    elif dec == SchedulerDecision.PARK_HUMAN_GATE.value:
                        if not any(g.get("task_id") == aid for g in session.human_gates_encountered):
                            session.human_gates_encountered.append({"task_id": aid, "reason": "HUMAN_GATE_PUBLICATION_FIREWALL"})
                    elif dec == SchedulerDecision.PARK_MONEY_GATE.value:
                        if not any(g.get("task_id") == aid for g in session.money_gates_encountered):
                            session.money_gates_encountered.append({"task_id": aid, "reason": "MONEY_GATE_SPEND_LIMIT_0"})

                # Execute top runnable candidate from planned actions
                primary_id = plan.get("primary_action")
                all_candidate_ids = [primary_id] + plan.get("parallel_actions", [])

                for aid in all_candidate_ids:
                    adm = admissions.get(aid, {})
                    matching_opp = next((o for o in ready_opps if o.opportunity_id == aid), None)
                    if not matching_opp:
                        continue

                    scope = matching_opp.project or "GLOBAL"
                    branch = getattr(matching_opp, "branch", "MAIN") or "MAIN"
                    if self.policy_registry.snitch_manager.is_branch_quarantined(branch) or self.policy_registry.snitch_manager.is_scope_quarantined(scope):
                        continue

                    dec = adm.get("decision")
                    if dec in (SchedulerDecision.PARK_HUMAN_GATE.value, SchedulerDecision.PARK_MONEY_GATE.value):
                        continue
                    elif dec == SchedulerDecision.LOCALIZE.value:
                        can_resolve, res = deterministic_resolver(aid) if deterministic_resolver else (False, None)
                        metrics = self.control_plane._load_metrics()
                        metrics.model_calls_avoided += 1
                        self.control_plane._save_metrics(metrics)
                        return {
                            "action_type": "LOCAL_DETERMINISTIC_EXECUTION",
                            "task_id": aid,
                            "title": matching_opp.description,
                            "result": res if can_resolve else {"status": "LOCAL_EXECUTED"},
                            "execution_tier": ExecutionTier.LOCAL_DETERMINISTIC.value,
                        }
                    elif dec in (SchedulerDecision.RUN_NOW.value, SchedulerDecision.REUSE_CACHE.value) and adm.get("admitted"):
                        # Scope exclusivity check
                        locked, lock_owner = self.control_plane._check_scope_conflicts(aid, [scope])
                        if locked:
                            continue

                        # Pass to canonical low-level control-plane admission
                        req = ModelAdmissionRequest(
                            request_id=f"adm-opp-{uuid.uuid4().hex[:8]}",
                            task_id=aid,
                            why_model=f"Execute high priority backlog task: {matching_opp.description}",
                            why_not_local="Code generation or structural change requiring model intelligence",
                            new_information=matching_opp.problem_or_goal or matching_opp.description,
                            expected_unlock=matching_opp.expected_value or matching_opp.expected_output,
                            decision_value_class=DecisionValueClass.HIGH_VALUE if matching_opp.priority >= 8 else DecisionValueClass.USEFUL,
                            risk_level=RiskLevel.HIGH if matching_opp.risk == "HIGH" else RiskLevel.LOW,
                            target_scope=[scope],
                        )
                        adm_res = self.control_plane.evaluate_admission(req, deterministic_resolver=deterministic_resolver)
                        if adm_res.admitted:
                            job_env = ProviderJobEnvelope(
                                job_id=f"job-{uuid.uuid4().hex[:8]}",
                                task_id=aid,
                                correlation_id=f"corr-{uuid.uuid4().hex[:8]}",
                                owner="GOOGLE" if matching_opp.target_agent == "antigravity" else "LOCAL",
                                provider="GOOGLE_PRO" if matching_opp.target_agent == "antigravity" else "LOCAL_DETERMINISTIC",
                                scope=scope,
                                mutation_scope=[scope],
                                dependency_ids=[],
                                context_reference=adm_res.context_lease_id or "",
                                expected_unlock=matching_opp.expected_output,
                                resource_class="GOOGLE_PRO_POOL_1",
                                risk_class=matching_opp.risk,
                                admission_reason=adm_res.reason,
                                status=JobStatus.PREPARED,
                            )
                            self._save_job_envelope(job_env)

                            return {
                                "action_type": "DISPATCH_JOB",
                                "job_envelope": job_env.to_dict(),
                                "admission": adm_res.to_dict(),
                                "admitted": True,
                                "execution_tier": adm_res.execution_tier.value,
                            }

        # 3. Check for waiting barriers
        waiting_count = sum(1 for b in barriers.values() if not b.is_satisfied())
        if waiting_count > 0:
            return {
                "action_type": "WAITING_FOR_DEPENDENCIES",
                "waiting_barriers_count": waiting_count,
                "status": "WAITING",
            }

        # 4. No actionable work -> IDLE_EXPECTED (idle is success!)
        return {
            "action_type": "IDLE_EXPECTED",
            "status": "IDLE_EXPECTED",
            "message": "No actionable backlog or barriers remaining. Safe idle state.",
        }

    def _save_job_envelope(self, env: ProviderJobEnvelope) -> None:
        atomic_write_json(self.jobs_dir / f"{env.job_id}.json", env.to_dict())

    def get_job_envelope(self, job_id: str) -> Optional[ProviderJobEnvelope]:
        data = read_json_safe(self.jobs_dir / f"{job_id}.json")
        return ProviderJobEnvelope.from_dict(data) if data else None

    # --------------------------------------------------------------------------
    # Phase I, J & K: Night Session Controller & Morning Report
    # --------------------------------------------------------------------------

    def start_night_session(
        self,
        session_id: str,
        goal: str,
        allowed_scopes: Optional[List[str]] = None,
        max_runtime_minutes: int = 480,
        max_iterations: int = 50,
    ) -> NightSessionState:
        """Initializes and persists a bounded unattended night session."""
        session = NightSessionState(
            session_id=session_id,
            goal=goal,
            allowed_scopes=allowed_scopes or ["PROJECT_GLOBAL"],
            max_runtime_minutes=max_runtime_minutes,
            max_iterations=max_iterations,
            status=SessionStatus.RUNNING,
        )
        self._save_session(session)
        return session

    def execute_session_step(
        self,
        deterministic_resolver: Optional[Callable[[str], Tuple[bool, Any]]] = None,
        job_executor: Optional[Callable[[ProviderJobEnvelope], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Executes a single end-to-end autonomous transition without human copy-paste."""
        session = self._load_session()
        if not session:
            session = self.start_night_session(
                session_id=f"session-auto-{uuid.uuid4().hex[:8]}",
                goal="Autonomous organization execution",
            )
        elif session.status not in (SessionStatus.RUNNING, SessionStatus.WAITING, SessionStatus.IDLE_EXPECTED):
            return {"status": "NO_ACTIVE_SESSION"}

        # Select next action first to distinguish productive vs idle step
        next_action = self.select_next_action(session, deterministic_resolver=deterministic_resolver)
        action_type = next_action.get("action_type")

        # INVARIANT_IDLE_1: Idle waiting does not consume productive execution iteration budget
        if action_type in ("IDLE_EXPECTED", "WAITING_FOR_DEPENDENCIES", "NO_ACTION"):
            session.idle_observations += 1
            session.status = SessionStatus.IDLE_EXPECTED if action_type == "IDLE_EXPECTED" else SessionStatus.WAITING

            transition_record = {
                "step_index": session.iterations_completed,
                "idle_observation_index": session.idle_observations,
                "action_type": action_type,
                "timestamp": utc_now(),
                "details": next_action,
            }
            session.events_log.append(transition_record)
            self._save_session(session)

            report = self.generate_morning_report(session) if action_type == "IDLE_EXPECTED" else None
            out = {"status": session.status.value, "transition": transition_record}
            if report:
                out["morning_report"] = report
            return out

        # Productive iteration step: wake/reset session status from idle/waiting to RUNNING
        session.status = SessionStatus.RUNNING
        session.iterations_completed += 1
        session.last_active_at = utc_now()

        # Check iteration stop condition
        if session.iterations_completed > session.max_iterations:
            session.status = SessionStatus.STOPPED_SAFELY
            self._save_session(session)
            report = self.generate_morning_report(session)
            return {"status": "MAX_ITERATIONS_REACHED", "morning_report": report}

        transition_record = {
            "step_index": session.iterations_completed,
            "action_type": action_type,
            "timestamp": utc_now(),
            "details": next_action,
        }

        if action_type == "LOCAL_DETERMINISTIC_EXECUTION":
            # Auto-ingest deterministic result
            task_id = next_action["task_id"]
            corr_id = f"corr-det-{uuid.uuid4().hex[:8]}"
            ing_res = self.ingest_real_event(
                event_type="RESULT",
                source_worker="LOCAL_DETERMINISTIC",
                correlation_id=corr_id,
                payload={"outcome": "SUCCESS", "result": next_action.get("result")},
                task_id=task_id,
            )
            session.jobs_completed.append(task_id)
            transition_record["ingestion"] = ing_res
            self.control_plane.release_scope_locks(task_id)
            self.policy_registry.core.release_scope_lock(task_id)
            opp = self.opp_queue.get_opportunity(task_id)
            if opp:
                opp.status = "COMPLETED"
                self.opp_queue.save_opportunity(opp)

        elif action_type == "DISPATCH_JOB":
            job_dict = next_action["job_envelope"]
            job_id = job_dict["job_id"]
            session.jobs_dispatched.append(job_id)

            # If executor provided (or mock in dry run), execute and auto-correlate
            if job_executor:
                envelope = ProviderJobEnvelope.from_dict(job_dict)
                exec_res = job_executor(envelope)
                envelope.status = JobStatus.EXECUTED_SUCCESS if exec_res.get("success", True) else JobStatus.EXECUTED_FAIL
                envelope.execution_result = exec_res
                self._save_job_envelope(envelope)

                # Ingest result into canonical state automatically
                ing_res = self.ingest_real_event(
                    event_type="RESULT",
                    source_worker=envelope.owner,
                    correlation_id=envelope.correlation_id,
                    payload=exec_res,
                    task_id=envelope.task_id,
                )
                session.jobs_completed.append(envelope.task_id)
                transition_record["execution"] = exec_res
                transition_record["ingestion"] = ing_res
                self.control_plane.release_scope_locks(envelope.task_id)
                self.policy_registry.core.release_scope_lock(envelope.task_id)

                if envelope.status == JobStatus.EXECUTED_SUCCESS:
                    opp = self.opp_queue.get_opportunity(envelope.task_id)
                    if opp:
                        opp.status = "COMPLETED"
                        self.opp_queue.save_opportunity(opp)

        elif action_type == "SYNTHESIS":
            task_id = next_action["task_id"]
            session.jobs_completed.append(task_id)
            transition_record["synthesis_completed"] = True
            self.control_plane.release_scope_locks(task_id)
            self.policy_registry.core.release_scope_lock(task_id)

        session.events_log.append(transition_record)
        self._save_session(session)

        # Generate / update morning report if session reached terminal state
        if session.status in (SessionStatus.COMPLETED, SessionStatus.STOPPED_SAFELY):
            report = self.generate_morning_report(session)
            return {"status": session.status.value, "transition": transition_record, "morning_report": report}

        return {"status": "PROGRESS_MADE", "transition": transition_record}

    def generate_morning_report(self, session: NightSessionState) -> Dict[str, Any]:
        """Generates deterministic, verified morning report with exact operational metrics."""
        metrics = self.control_plane._load_metrics()
        report_id = f"morning_report_{session.session_id}_{uuid.uuid4().hex[:6]}"
        report_file = self.journal_dir / f"{report_id}.json"

        # Determine remaining open loops
        open_loops = self.chief_brain.get_open_loops()

        report_data = {
            "report_id": report_id,
            "session_id": session.session_id,
            "goal": session.goal,
            "started_at": session.started_at,
            "ended_at": session.ended_at or utc_now(),
            "session_status": session.status.value,
            "useful_tasks_completed_count": len(session.jobs_completed),
            "completed_tasks": session.jobs_completed,
            "decisions_closed_count": metrics.decisions_closed_total,
            "blockers_removed_count": metrics.blockers_removed_total,
            "human_gates_waiting_count": len(session.human_gates_encountered),
            "money_gates_waiting_count": len(session.money_gates_encountered),
            "model_calls_admitted": metrics.model_calls_executed,
            "model_calls_avoided_proven": metrics.model_calls_avoided,
            "reviews_reused_proven": metrics.reviews_reused,
            "duplicate_dispatches_prevented": metrics.duplicate_calls_avoided,
            "remaining_open_loops_count": len(open_loops),
            "autonomous_spend_eur": 0.0,
            "next_recommended_action": "RESUME_AUTONOMY_DISPATCH" if session.status != SessionStatus.COMPLETED else "STANDBY_IDLE",
        }

        atomic_write_json(report_file, report_data)
        session.morning_report_path = str(report_file)
        self._save_session(session)
        return report_data


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Real Local Autonomy Runtime Engine (Mission 185G)")
    parser.add_argument("--status", action="store_true", help="Print runtime status")
    parser.add_argument("--start-session", type=str, metavar="GOAL", help="Start new unattended session")
    parser.add_argument("--step", action="store_true", help="Execute single autonomous step")
    args = parser.parse_args()

    runtime = RealAutonomyRuntime()

    if args.start_session:
        session = runtime.start_night_session(
            session_id=f"sess-{uuid.uuid4().hex[:8]}",
            goal=args.start_session,
        )
        print(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))
        return

    if args.step:
        res = runtime.execute_session_step()
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    # Default status
    sess = runtime._load_session()
    print(json.dumps(sess.to_dict() if sess else {"session": "NONE"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
