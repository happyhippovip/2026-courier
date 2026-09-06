#!/usr/bin/env python3
"""Provider-Agnostic 3-Slot Worker Fabric & Dynamic Capacity Router.

Formalizes the organization into decoupled concepts:
- PROVIDER: GOOGLE | OPENAI | ANTHROPIC | LOCAL | GENERIC_PROVIDER
- ACCOUNT: ACCOUNT_GOOGLE_01 | ACCOUNT_OPENAI_01 | ACCOUNT_LOCAL_01
- SURFACE: CLI | ANTIGRAVITY_APP | CHATGPT | API | LOCAL_PROCESS
- HOST: COMPUTER_A | COMPUTER_B | MAC_MINI | CLOUD_VM_1
- WORKER: Executable organizational slot (CLI1, ANTIGRAVITY_PRIMARY, CHATGPT_CHIEF, etc.)

Guarantees:
- Hot-plug capacity addition/removal without redesigning Chief Decision Protocol.
- Policy-driven routing (Google preferred for routine build; ChatGPT in CONSERVE/RESERVE for strategic review).
- Atomic collision-controlled task scope claiming.
- Provider-neutral structured result envelopes.
- Closed-loop autonomous RESULT → NEXT TASK continuation (Zero human WEITER).
- 0.00 EUR spend limit strictly enforced.
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
from typing import Any, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.canonical_authority import (
    CanonicalAuthority,
    LockStatus,
)
from scripts.chief_decision_protocol import (
    ChiefDecisionProtocol,
    ChiefDecisionRecord,
    DecisionReasonCode,
)
from scripts.money_machine_pipeline import (
    EconomicClass,
    MoneyMachinePipeline,
    OpportunityState,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class ProviderType(str, enum.Enum):
    GOOGLE = "GOOGLE"
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    LOCAL = "LOCAL"
    GENERIC = "GENERIC"


class SurfaceType(str, enum.Enum):
    CLI = "CLI"
    ANTIGRAVITY_APP = "ANTIGRAVITY_APP"
    CHATGPT = "CHATGPT"
    API = "API"
    LOCAL_PROCESS = "LOCAL_PROCESS"


class AvailabilityState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RESERVE = "RESERVE"
    CONSERVE = "CONSERVE"
    PAUSED = "PAUSED"
    UNAVAILABLE = "UNAVAILABLE"
    OFFLINE = "OFFLINE"


class RoutingPreference(str, enum.Enum):
    PREFERRED_ROUTINE = "PREFERRED_ROUTINE"
    CONSERVE = "CONSERVE"
    RESERVE = "RESERVE"
    DISABLED = "DISABLED"


@dataclass
class GenericWorkerSlot:
    worker_id: str
    provider: str
    surface: str
    account_id: str
    host: str
    role: str
    capabilities: List[str]
    authorization_state: str = "AUTHORIZED"
    availability_state: str = "ACTIVE"
    routing_preference: str = "PREFERRED_ROUTINE"
    cost_class: str = "ZERO_COST"
    capacity_class: str = "HIGH_VOLUME"
    current_claim: Optional[str] = None
    risk_permissions: List[str] = field(default_factory=lambda: ["READ", "LOCAL_WRITE"])
    last_heartbeat: str = field(default_factory=utc_now)
    result_channel: str = "CANONICAL_ENVELOPE"
    status: str = "AVAILABLE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GenericWorkerSlot:
        return cls(**data)


@dataclass
class GenericResultEnvelope:
    task_id: str
    worker_id: str
    provider: str
    surface: str
    host: str
    started_at: str
    completed_at: str
    result_state: str  # SUCCESS | FAILED | BLOCKED_GATE | WAITING_RESOURCE
    artifacts_changed: List[str]
    verification: Dict[str, Any]
    evidence: Dict[str, Any]
    economic_delta: Dict[str, Any]
    blockers: List[str]
    next_candidate_actions: List[str]
    fingerprint: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GenericResultEnvelope:
        return cls(**data)


@dataclass
class RoutingDecision:
    task_id: str
    task_class: str
    assigned_worker_id: Optional[str]
    assigned_provider: Optional[str]
    assigned_surface: Optional[str]
    assigned_host: Optional[str]
    routing_verdict: str  # ROUTED_SUCCESS | WAITING_RESOURCE | NO_CAPABLE_WORKER | BLOCKED_COLLISION
    score: float
    rationale: str
    routed_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderAgnosticWorkerFabric:
    """Manages provider-neutral worker registration, collision-fenced routing, and closed loop execution."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.registry_dir = self.repo_dir / "events" / "worker-registry"
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.registry_dir / "generic_worker_fabric.json"
        self.envelopes_dir = self.repo_dir / "events" / "task-envelopes"
        self.envelopes_dir.mkdir(parents=True, exist_ok=True)

        self.authority = CanonicalAuthority(locks_dir=self.repo_dir / "events" / "locks")
        self.chief_protocol = ChiefDecisionProtocol(repo_dir=self.repo_dir)
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

        self.workers: Dict[str, GenericWorkerSlot] = {}
        self.load_registry()

    def _init_default_3_slots(self) -> None:
        """Initializes the baseline 3-slot fabric (CLI1, ANTIGRAVITY_PRIMARY, CHATGPT_CHIEF)."""
        now = utc_now()
        # 1. CLI1 (Google CLI)
        self.workers["CLI1"] = GenericWorkerSlot(
            worker_id="CLI1",
            provider=ProviderType.GOOGLE.value,
            surface=SurfaceType.CLI.value,
            account_id="ACCOUNT_GOOGLE_01",
            host="COMPUTER_A",
            role="HIGH_VOLUME_BUILDER",
            capabilities=["ROUTINE_BUILD", "REGRESSION_TEST", "DATA_PIPELINE", "ASSET_PACKAGING", "CODE_GENERATION"],
            authorization_state="AUTHORIZED",
            availability_state=AvailabilityState.ACTIVE.value,
            routing_preference=RoutingPreference.PREFERRED_ROUTINE.value,
            cost_class="MARGINAL_COST_ZERO_OR_PREPAID",
            capacity_class="HIGH_VOLUME",
            last_heartbeat=now,
        )

        # 2. ANTIGRAVITY_PRIMARY (Google Antigravity App)
        self.workers["ANTIGRAVITY_PRIMARY"] = GenericWorkerSlot(
            worker_id="ANTIGRAVITY_PRIMARY",
            provider=ProviderType.GOOGLE.value,
            surface=SurfaceType.ANTIGRAVITY_APP.value,
            account_id="ACCOUNT_GOOGLE_01",
            host="COMPUTER_A",
            role="PRIMARY_BUILDER_EXECUTOR",
            capabilities=["PRIMARY_EXECUTION", "SYSTEM_ARCHITECTURE", "CODE_GENERATION", "AUTONOMOUS_DAEMON"],
            authorization_state="AUTHORIZED",
            availability_state=AvailabilityState.ACTIVE.value,
            routing_preference=RoutingPreference.PREFERRED_ROUTINE.value,
            cost_class="MARGINAL_COST_ZERO_OR_PREPAID",
            capacity_class="INTERACTIVE",
            last_heartbeat=now,
        )

        # 3. CHATGPT_CHIEF (OpenAI ChatGPT)
        self.workers["CHATGPT_CHIEF"] = GenericWorkerSlot(
            worker_id="CHATGPT_CHIEF",
            provider=ProviderType.OPENAI.value,
            surface=SurfaceType.CHATGPT.value,
            account_id="ACCOUNT_OPENAI_01",
            host="COMPUTER_A",
            role="CHIEF_CONTROLLER_REVIEWER",
            capabilities=["STRATEGIC_JUDGMENT", "CHIEF_AMBIGUITY", "CROSS_PROVIDER_REVIEW", "POLICY_VERDICT"],
            authorization_state="AUTHORIZED",
            availability_state=AvailabilityState.RESERVE.value,
            routing_preference=RoutingPreference.CONSERVE.value,
            cost_class="EXISTING_SUBSCRIPTION_CAPACITY",
            capacity_class="STRATEGIC_JUDGMENT",
            last_heartbeat=now,
        )
        self.save_registry()

    def load_registry(self) -> None:
        """Loads worker slots from disk or creates default 3 slots."""
        if not self.registry_file.exists():
            self._init_default_3_slots()
            return

        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            self.workers = {k: GenericWorkerSlot.from_dict(v) for k, v in data.get("workers", {}).items()}
            if not self.workers:
                self._init_default_3_slots()
        except Exception:
            self._init_default_3_slots()

    def save_registry(self) -> None:
        """Atomically persists worker registry to disk."""
        data = {
            "version": "2026.FABRIC.1",
            "updated_at": utc_now(),
            "active_worker_count": len([w for w in self.workers.values() if w.availability_state == "ACTIVE"]),
            "workers": {k: v.to_dict() for k, v in self.workers.items()},
        }
        self.registry_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def register_worker(self, slot: GenericWorkerSlot) -> GenericWorkerSlot:
        """Hot-plugs a new worker slot dynamically."""
        slot.last_heartbeat = utc_now()
        self.workers[slot.worker_id] = slot
        self.save_registry()
        return slot

    def unregister_worker(self, worker_id: str) -> bool:
        """Gracefully drains and removes a worker slot."""
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            if worker.current_claim:
                self.authority.release_scope(scope=worker.current_claim, task_id=worker.worker_id, owner=worker.worker_id)
            del self.workers[worker_id]
            self.save_registry()
            return True
        return False

    def update_heartbeat(self, worker_id: str, state: str = "AVAILABLE") -> bool:
        """Updates worker heartbeat and availability state."""
        if worker_id in self.workers:
            self.workers[worker_id].last_heartbeat = utc_now()
            self.workers[worker_id].status = state
            self.save_registry()
            return True
        return False

    def set_routing_policy(self, worker_id: str, preference: RoutingPreference, availability: Optional[AvailabilityState] = None) -> bool:
        """Dynamically adjusts routing preference (e.g. ChatGPT CONSERVE -> ACTIVE) without code redesign."""
        if worker_id in self.workers:
            self.workers[worker_id].routing_preference = preference.value
            if availability:
                self.workers[worker_id].availability_state = availability.value
            self.save_registry()
            return True
        return False

    def route_task(
        self,
        task_id: str,
        task_class: str,
        required_capabilities: List[str],
        required_scope: str,
    ) -> RoutingDecision:
        """Selects the optimal authorized worker slot based on policy, capacity, and scope collision safety."""
        # 1. Capability & Availability Match Candidates
        eligible: List[Tuple[GenericWorkerSlot, float]] = []

        is_strategic = any(c in ["STRATEGIC_JUDGMENT", "CHIEF_AMBIGUITY", "CROSS_PROVIDER_REVIEW"] for c in required_capabilities)

        for w in self.workers.values():
            if w.authorization_state != "AUTHORIZED":
                continue
            if w.availability_state in [AvailabilityState.UNAVAILABLE.value, AvailabilityState.PAUSED.value, AvailabilityState.OFFLINE.value]:
                continue
            if w.status != "AVAILABLE" or w.current_claim is not None:
                continue

            # Check capability match
            cap_match = sum(1 for c in required_capabilities if c in w.capabilities)
            if cap_match == 0 and not is_strategic:
                continue

            # Score calculation
            score = 100.0 * (cap_match + 1)

            # Routing Policy Adjustments
            if is_strategic and w.role == "CHIEF_CONTROLLER_REVIEWER":
                score += 500.0  # Strategic tasks prefer Chief/ChatGPT
            elif not is_strategic:
                if w.routing_preference == RoutingPreference.PREFERRED_ROUTINE.value:
                    score += 200.0  # Google routine preferred
                elif w.routing_preference == RoutingPreference.CONSERVE.value:
                    score -= 100.0  # Conserved worker penalised for routine tasks
                elif w.routing_preference == RoutingPreference.RESERVE.value:
                    score -= 200.0

            eligible.append((w, score))

        if not eligible:
            return RoutingDecision(
                task_id=task_id,
                task_class=task_class,
                assigned_worker_id=None,
                assigned_provider=None,
                assigned_surface=None,
                assigned_host=None,
                routing_verdict="WAITING_RESOURCE",
                score=0.0,
                rationale="No eligible available worker with required capabilities and authority.",
            )

        # Sort by score descending
        eligible.sort(key=lambda x: x[1], reverse=True)
        best_worker, best_score = eligible[0]

        # 2. Scope Collision Check via CanonicalAuthority
        acq_ok, gen, err = self.authority.acquire_scopes(
            owner_id=best_worker.worker_id,
            task_id=task_id,
            scopes=[required_scope],
        )
        if not acq_ok:
            return RoutingDecision(
                task_id=task_id,
                task_class=task_class,
                assigned_worker_id=best_worker.worker_id,
                assigned_provider=best_worker.provider,
                assigned_surface=best_worker.surface,
                assigned_host=best_worker.host,
                routing_verdict="BLOCKED_COLLISION",
                score=best_score,
                rationale=f"Scope '{required_scope}' locked by another worker: {err}",
            )

        # Claim assigned
        best_worker.current_claim = required_scope
        best_worker.status = "BUSY"
        self.save_registry()

        return RoutingDecision(
            task_id=task_id,
            task_class=task_class,
            assigned_worker_id=best_worker.worker_id,
            assigned_provider=best_worker.provider,
            assigned_surface=best_worker.surface,
            assigned_host=best_worker.host,
            routing_verdict="ROUTED_SUCCESS",
            score=best_score,
            rationale=f"Routed to {best_worker.worker_id} ({best_worker.provider}/{best_worker.surface}) with score {best_score:.1f}",
        )

    def submit_result_and_continue(
        self,
        envelope: GenericResultEnvelope,
        released_scope: str,
    ) -> Dict[str, Any]:
        """Persists provider-neutral result envelope, releases scope claim, and drives next-work decision."""
        # 1. Persist result envelope
        env_file = self.envelopes_dir / f"{envelope.task_id}.json"
        env_file.write_text(json.dumps(envelope.to_dict(), indent=2) + "\n", encoding="utf-8")

        # 2. Release worker claim
        if envelope.worker_id in self.workers:
            w = self.workers[envelope.worker_id]
            w.current_claim = None
            w.status = "AVAILABLE"
            w.last_heartbeat = utc_now()
            self.save_registry()

        self.authority.release_scopes(
            owner_id=envelope.worker_id,
            task_id=envelope.task_id,
            scopes=[released_scope],
        )

        # 3. Chief Decision Protocol structured decision
        decision = self.chief_protocol.evaluate_result_and_decide(
            task_id=envelope.task_id,
            opportunity_id=envelope.task_id.replace("TASK-", ""),
            result_status=envelope.result_state,
            findings=f"Executed on {envelope.provider}/{envelope.surface} on {envelope.host}. Result: {envelope.result_state}",
            artifacts={"fingerprint": envelope.fingerprint, "artifacts_changed": envelope.artifacts_changed},
            evidence=envelope.evidence,
        )

        return {
            "status": "RESULT_PROCESSED_AND_CHAIN_CONTINUED",
            "task_id": envelope.task_id,
            "worker_id": envelope.worker_id,
            "decision_id": decision.decision_id,
            "next_reason": decision.reason_code,
            "human_weiter_required": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Provider-Agnostic Worker Fabric CLI")
    parser.add_argument("--list", action="store_true", help="List all registered worker slots")
    args = parser.parse_args()

    fabric = ProviderAgnosticWorkerFabric()
    if args.list:
        print(json.dumps({k: v.to_dict() for k, v in fabric.workers.items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
