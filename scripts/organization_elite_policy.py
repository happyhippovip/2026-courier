#!/usr/bin/env python3
"""Mission 190G: Organization-Wide Elite Autonomy Activation & Final Integration.

Makes Elite Execution principles the central inherited default across all existing
and future logical agents:
- Central Policy Registry & Dynamic Inheritance (zero manual duplication across bots).
- Absolute Priority Hierarchy:
  1. QUALITY / CORRECTNESS / SAFETY
  2. ACTUAL GOAL PROGRESS
  3. COST EFFICIENCY
  4. SPEED
  5. RESOURCE UTILIZATION
- FAST_FINISH Mode (Critical-path acceleration, safe scope parallelism, zero busywork, strict Quality Floor).
- Snitch-on-Anomaly Subsystem (NORMAL, UNKNOWN, SUSPICIOUS, CRITICAL, branch-local fail-closed, anti-false-alarm deduplication).
- Hard Firewalls: AUTONOMOUS_SPEND_LIMIT = 0 EUR, PUBLICATION_INFERENCE = DENY, ZERO_SECRETS.
- Negative Work & Provable Avoided Waste Telemetry.
"""

from __future__ import annotations

import datetime as dt
import enum
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent

from scripts.evidence_provenance import check_for_secrets
from scripts.elite_execution_core import (
    CapabilityType,
    EliteActionSpec,
    EliteExecutionCore,
    IntelligenceLadderLevel,
    QualityFloorClass,
    SchedulerDecision,
    SemanticDeltaClassifier,
    SemanticDeltaType,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def compute_sha256(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class AnomalySeverity(str, enum.Enum):
    NORMAL = "NORMAL"
    UNKNOWN = "UNKNOWN"
    SUSPICIOUS = "SUSPICIOUS"
    CRITICAL = "CRITICAL"


class AnomalyDomain(str, enum.Enum):
    PROCESS_BEHAVIOR = "PROCESS_BEHAVIOR"
    STATE_CONTRADICTION = "STATE_CONTRADICTION"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    PUBLICATION_ATTEMPT = "PUBLICATION_ATTEMPT"
    SPEND_ANOMALY = "SPEND_ANOMALY"
    SECRET_EXPOSURE = "SECRET_EXPOSURE"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"
    DUPLICATE_WORK = "DUPLICATE_WORK"
    MODEL_FANOUT = "MODEL_FANOUT"
    CHATTER_LOOP = "CHATTER_LOOP"
    CORRUPTED_EVIDENCE = "CORRUPTED_EVIDENCE"
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
    DEPENDENCY_ANOMALY = "DEPENDENCY_ANOMALY"
    SECURITY_BOUNDARY_VIOLATION = "SECURITY_BOUNDARY_VIOLATION"


@dataclass
class SnitchAnomalyEvent:
    anomaly_id: str
    timestamp: str
    reporting_agent: str
    severity: AnomalySeverity
    domain: AnomalyDomain
    observed_state: str
    expected_state: str
    evidence_references: List[str]
    affected_scope: str
    affected_branch: str
    local_checks_performed: List[str]
    risk_level: str
    recommended_next_action: str
    fingerprint: str = ""

    def compute_fingerprint(self) -> str:
        payload = f"{self.domain.value}:{self.observed_state}:{self.expected_state}:{self.affected_scope}:{self.affected_branch}:{sorted(self.evidence_references)}"
        self.fingerprint = compute_sha256(payload)
        return self.fingerprint

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["domain"] = self.domain.value
        return d


@dataclass
class OrganizationPolicyConfig:
    priority_ladder: List[str] = field(
        default_factory=lambda: [
            "QUALITY_CORRECTNESS_SAFETY",
            "ACTUAL_GOAL_PROGRESS",
            "COST_EFFICIENCY",
            "SPEED",
            "RESOURCE_UTILIZATION",
        ]
    )
    fast_finish_mode: bool = False
    autonomous_spend_limit_eur: float = 0.0
    publication_inference: str = "DENY"
    secret_storage: str = "DENY"
    model_heavy_per_provider_limit: int = 1
    mutation_scope_owner_limit: int = 1
    render_heavy_limit: int = 1


class SnitchAnomalyManager:
    """Centralized anomaly detection, anti-false-alarm deduplication & branch-local fail-closed engine."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.events_dir = repo_dir / "events" / "anomalies"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.events_dir / "anomaly_ledger.json"
        self.ledger: Dict[str, Dict[str, Any]] = self._load_ledger()

        # Branch quarantine status (reconstructed deterministically from durable ledger)
        self.quarantined_branches: Dict[str, str] = {}  # branch_id -> reason
        self.quarantined_scopes: Dict[str, str] = {}  # scope -> reason
        self._reconstruct_quarantine_from_ledger()

        # Metrics
        self.anomalies_detected: int = 0
        self.anomalies_suppressed_duplicate: int = 0
        self.anomalies_escalated: int = 0

    def _load_ledger(self) -> Dict[str, Dict[str, Any]]:
        if self.ledger_file.is_file():
            try:
                return json.loads(self.ledger_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_ledger(self) -> None:
        self.ledger_file.write_text(json.dumps(self.ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _reconstruct_quarantine_from_ledger(self) -> None:
        """Deterministically reconstructs active branch and scope quarantines from durable ledger on startup."""
        self.quarantined_branches.clear()
        self.quarantined_scopes.clear()
        for fp, entry in self.ledger.items():
            if entry.get("severity") == AnomalySeverity.CRITICAL.value and not entry.get("resolved", False):
                branch = entry.get("affected_branch")
                scope = entry.get("affected_scope")
                reason = f"CRITICAL anomaly in domain {entry.get('domain')} ({entry.get('anomaly_id')})"
                if branch:
                    self.quarantined_branches[branch] = reason
                if scope:
                    self.quarantined_scopes[scope] = reason

    def resolve_anomaly(self, identifier: str, resolution_notes: str = "Resolved by authorized operator") -> bool:
        """Resolves an anomaly and clears its quarantine deterministically."""
        resolved_any = False
        for fp, entry in self.ledger.items():
            if fp == identifier or entry.get("anomaly_id") == identifier or identifier in entry.get("affected_branch", ""):
                entry["resolved"] = True
                entry["resolved_at"] = utc_now()
                entry["resolution_notes"] = resolution_notes
                resolved_any = True
        if resolved_any:
            self._save_ledger()
            self._reconstruct_quarantine_from_ledger()
        return resolved_any

    def report_observation(
        self,
        reporting_agent: str,
        domain: AnomalyDomain,
        observed: str,
        expected: str,
        affected_scope: str = "GLOBAL",
        affected_branch: str = "MAIN",
        evidence_refs: Optional[List[str]] = None,
        local_checks: Optional[List[str]] = None,
    ) -> Tuple[AnomalySeverity, Optional[SnitchAnomalyEvent], str]:
        """Evaluates an observation, enforces anti-false-alarm deduplication, and applies branch fail-closed."""
        self.anomalies_detected += 1
        evidence_refs = evidence_refs or []
        local_checks = local_checks or []

        # Check and redact secrets in observation text
        for kw in ("client_secret", "private_key", "bearer_token", "api_key_secret"):
            if kw in observed.lower():
                parts = observed.split(kw)
                observed = parts[0] + kw + "=[REDACTED_SECRET_VALUE]"
            if kw in expected.lower():
                parts = expected.split(kw)
                expected = parts[0] + kw + "=[REDACTED_SECRET_VALUE]"

        # Classify severity
        if observed == expected or not observed:
            return AnomalySeverity.NORMAL, None, "Observation matches expected state. Continue normally."

        # Determine domain risk
        if domain in (
            AnomalyDomain.SPEND_ANOMALY,
            AnomalyDomain.PUBLICATION_ATTEMPT,
            AnomalyDomain.SECRET_EXPOSURE,
            AnomalyDomain.SECURITY_BOUNDARY_VIOLATION,
        ):
            severity = AnomalySeverity.CRITICAL
            risk = "CRITICAL"
            rec_action = f"FAIL_CLOSED: Freeze affected branch '{affected_branch}' and scope '{affected_scope}' immediately."
        elif domain in (
            AnomalyDomain.STATE_CONTRADICTION,
            AnomalyDomain.SCOPE_CONFLICT,
            AnomalyDomain.FINGERPRINT_MISMATCH,
            AnomalyDomain.CORRUPTED_EVIDENCE,
        ):
            severity = AnomalySeverity.SUSPICIOUS
            risk = "HIGH"
            rec_action = "EMIT_SNITCH_EVENT: Escalate structured artifact to control plane."
        else:
            severity = AnomalySeverity.UNKNOWN
            risk = "MEDIUM"
            rec_action = "LOCAL_INVESTIGATION: Perform bounded local checks without model chatter."

        event = SnitchAnomalyEvent(
            anomaly_id=f"anomaly-{domain.value.lower()}-{int(dt.datetime.now().timestamp())}",
            timestamp=utc_now(),
            reporting_agent=reporting_agent,
            severity=severity,
            domain=domain,
            observed_state=observed,
            expected_state=expected,
            evidence_references=evidence_refs,
            affected_scope=affected_scope,
            affected_branch=affected_branch,
            local_checks_performed=local_checks,
            risk_level=risk,
            recommended_next_action=rec_action,
        )
        fp = event.compute_fingerprint()

        # Anti-False-Alarm Deduplication (Phase E)
        if fp in self.ledger and self.ledger[fp].get("severity") == severity.value and not self.ledger[fp].get("resolved", False):
            self.anomalies_suppressed_duplicate += 1
            return severity, event, "DUPLICATE_SUPPRESSED: Anomaly previously reported with identical fingerprint. No repeat escalation."

        self.ledger[fp] = event.to_dict()
        self._save_ledger()
        self.anomalies_escalated += 1

        # Apply Branch-Local Fail-Closed if CRITICAL (Phase F)
        if severity == AnomalySeverity.CRITICAL:
            self.quarantined_branches[affected_branch] = f"CRITICAL anomaly in domain {domain.value}"
            if affected_scope:
                self.quarantined_scopes[affected_scope] = f"CRITICAL anomaly in domain {domain.value}"

        return severity, event, rec_action

    def is_branch_quarantined(self, branch_id: str) -> bool:
        return branch_id in self.quarantined_branches

    def is_scope_quarantined(self, scope_id: str) -> bool:
        return scope_id in self.quarantined_scopes


class FastFinishEngine:
    """Dynamic Critical-Path Aware Fast Finish & Parallel Acceleration Engine."""

    def __init__(self, core: EliteExecutionCore, config: Optional[OrganizationPolicyConfig] = None):
        self.core = core
        self.config = config or OrganizationPolicyConfig(fast_finish_mode=True)

    def can_authorize_action(self) -> bool:
        """FastFinish is an optimization engine, NEVER an authorization bypass."""
        return False

    def optimize_action_plan(
        self,
        candidate_actions: List[EliteActionSpec],
        goal_target: str,
    ) -> Dict[str, Any]:
        """Calculates the shortest safe high-quality path, prioritizing critical path and parallelizing independent work."""
        if not candidate_actions:
            return {"status": "NO_ACTIONS", "selected_actions": []}

        # 1. Identify Critical Path (tasks that block others or have zero dependencies with high value)
        for a in candidate_actions:
            if a.decision_value_class in ("CRITICAL_UNBLOCK", "HIGH_VALUE") or len(a.dependencies) > 0:
                a.is_on_critical_path = True

        # 2. Select Primary Action via Fastest Path Planner
        primary_action = self.core.select_fastest_path_action(candidate_actions)
        if not primary_action:
            return {"status": "NO_ELIGIBLE_ACTION", "selected_actions": []}

        selected = [primary_action]
        active_scopes = set(primary_action.mutation_scope)

        # 3. Parallel Acceleration: Search for independent valuable work on disjoint scopes
        for candidate in candidate_actions:
            if candidate.action_id == primary_action.action_id:
                continue
            if candidate.decision_value_class == "ZERO_GAIN":
                continue

            # Scope disjoint check
            if not any(s in active_scopes for s in candidate.mutation_scope):
                # Independent work can run safely in parallel!
                selected.append(candidate)
                active_scopes.update(candidate.mutation_scope)

        return {
            "status": "PLAN_OPTIMIZED",
            "fast_finish_active": self.config.fast_finish_mode,
            "selected_count": len(selected),
            "primary_action": primary_action.action_id,
            "parallel_actions": [a.action_id for a in selected[1:]],
            "active_scopes": list(active_scopes),
        }

    def evaluate_and_schedule_plan(
        self,
        candidate_actions: List[EliteActionSpec],
        goal_target: str,
        deterministic_resolver: Optional[Callable[[str], Tuple[bool, Any]]] = None,
        snitch_manager: Optional[SnitchAnomalyManager] = None,
    ) -> Dict[str, Any]:
        """Optimizes plan AND passes all selected actions through canonical admission gates."""
        plan = self.optimize_action_plan(candidate_actions, goal_target)
        if plan.get("status") != "PLAN_OPTIMIZED":
            return plan

        action_map = {a.action_id: a for a in candidate_actions}
        primary_id = plan["primary_action"]
        parallel_ids = plan.get("parallel_actions", [])

        admissions: Dict[str, Any] = {}
        for aid, spec in action_map.items():
            # Check Snitch quarantine
            if snitch_manager:
                if any(snitch_manager.is_scope_quarantined(s) for s in spec.mutation_scope):
                    admissions[aid] = {
                        "decision": SchedulerDecision.PARK_HUMAN_GATE.value,
                        "ladder_level": IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE.value,
                        "payload": {"reason": "QUARANTINED_BY_SNITCH", "status": "PARKED_SAFE"},
                        "admitted": False,
                    }
                    continue

            lvl, dec, payload = self.core.evaluate_ladder_level(spec, deterministic_resolver=deterministic_resolver)
            admissions[aid] = {
                "decision": dec.value,
                "ladder_level": lvl.value,
                "payload": payload,
                "admitted": dec in (SchedulerDecision.RUN_NOW, SchedulerDecision.LOCALIZE, SchedulerDecision.REUSE_CACHE),
            }

        plan["admissions"] = admissions
        return plan


class CentralElitePolicyRegistry:
    """Central authoritative policy registry dynamically inherited by all current and future logical agents."""

    _instance: Optional[CentralElitePolicyRegistry] = None

    def __new__(cls, repo_dir: Path = COURIER_DIR) -> CentralElitePolicyRegistry:
        if cls._instance is None:
            cls._instance = super(CentralElitePolicyRegistry, cls).__new__(cls)
            cls._instance._init(repo_dir=repo_dir)
        return cls._instance

    def _init(self, repo_dir: Path = COURIER_DIR) -> None:
        self.repo_dir = repo_dir
        self.config = OrganizationPolicyConfig()
        self.core = EliteExecutionCore(repo_dir=repo_dir)
        self.snitch_manager = SnitchAnomalyManager(repo_dir=repo_dir)
        self.fast_finish_engine = FastFinishEngine(core=self.core, config=self.config)
        self.registered_agents: Dict[str, Dict[str, Any]] = {}

        # Register known baseline 25 logical agent types
        self._register_default_agent_roles()

    def _register_default_agent_roles(self) -> None:
        default_roles = [
            "CHIEF_COMMANDER", "COURIER", "TWO_COMPUTER_DISPATCHER", "RESOURCE_INTELLIGENCE_OFFICER",
            "CREATOR_DIRECTOR", "QC_INSPECTOR", "PUBLICATION_OFFICER", "SECURITY_AUDITOR",
            "AUTONOMY_SUPERVISOR", "CONTROLLING_STEWARD", "OPPORTUNITY_SCOUT", "DISASTER_RECOVERY_ENGINEER",
            "DETERMINISTIC_BUILDER", "FAST_FINISH_SCHEDULER", "QUALITY_GATEKEEPER", "DECISION_SYNTHESIZER",
            "CONTEXT_STEWARD", "RESULT_CORRELATOR", "SCOPE_LOCK_MANAGER", "CIRCUIT_BREAKER_OFFICER",
            "EVIDENCE_PROVENANCE_AUDITOR", "SNITCH_ANOMALY_OFFICER", "STORAGE_STEWARD", "NETWORK_FIREWALL_OFFICER",
            "IDENTITY_LEGAL_STEWARD",
        ]
        for role in default_roles:
            self.register_agent(agent_id=f"agent-{role.lower().replace('_', '-')}", role=role)

    def register_agent(self, agent_id: str, role: str) -> Dict[str, Any]:
        """Registers an agent and binds it to the inherited central Elite Policy."""
        entry = {
            "agent_id": agent_id,
            "role": role,
            "registered_at": utc_now(),
            "inherited_policy": {
                "priority_ladder": self.config.priority_ladder,
                "spend_limit_eur": self.config.autonomous_spend_limit_eur,
                "publication_inference": self.config.publication_inference,
                "secret_storage": self.config.secret_storage,
                "wake_on_evidence": True,
                "anti_swarm_enabled": True,
                "quality_floor_enforced": True,
                "snitch_on_anomaly_active": True,
            },
        }
        self.registered_agents[agent_id] = entry
        return entry

    def inherit_policy_for_agent(self, agent_id: str, role: Optional[str] = None) -> Dict[str, Any]:
        """Returns the central policy bindings for any existing or future agent."""
        if agent_id not in self.registered_agents:
            return self.register_agent(agent_id=agent_id, role=role or "FUTURE_AUTONOMOUS_AGENT")
        return self.registered_agents[agent_id]

    def set_fast_finish_mode(self, enabled: bool) -> None:
        self.config.fast_finish_mode = enabled
        self.fast_finish_engine.config.fast_finish_mode = enabled
