"""Cannon Parallelism Planner & Admissible Task-Worker Matching Engine (CP-21 / CQ-21 / GB-CANNON-01)

Durable Cannon Invariants:
1. Why min(|Tasks|, |Workers|) alone is NOT an admissible parallelism plan:
   - 1 Task / 10 Workers = at most 1 (no spurious parallelism).
   - Incompatible pairings = 0 (if no worker meets capability requirements, parallelism is 0).
   - Scope Overlap / Resource Contention: Tasks sharing exclusive resource locks cannot run concurrently.
   - Shared Provider Pool Limits: Workers sharing a provider quota or rate ceiling are constrained by provider capacity.
2. Independent admissible tasks CAN run in parallel:
   - When tasks have disjoint resource scopes, qualified workers exist, and provider pools have headroom,
     optimal maximal bipartite matching produces a safe, conflict-free parallel schedule.
3. Required Evidence:
   - ready-frontier, worker-capabilities, shared-capacity.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class RejectionReason(str, Enum):
    NO_CAPABLE_WORKER = "NO_CAPABLE_WORKER"
    RESOURCE_CONTENTION = "RESOURCE_CONTENTION"
    PROVIDER_CAPACITY_EXHAUSTED = "PROVIDER_CAPACITY_EXHAUSTED"
    WORKER_UNAVAILABLE = "WORKER_UNAVAILABLE"


@dataclass(frozen=True)
class ReadyTask:
    task_id: str
    required_capabilities: Set[str]
    required_resources: Set[str] = field(default_factory=set)  # exclusive locks/files/ports
    provider: str = "generic"
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "required_capabilities": sorted(list(self.required_capabilities)),
            "required_resources": sorted(list(self.required_resources)),
            "provider": self.provider,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class WorkerNode:
    worker_id: str
    supported_capabilities: Set[str]
    provider: str = "generic"
    is_available: bool = True
    platform: str = "windows"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "supported_capabilities": sorted(list(self.supported_capabilities)),
            "provider": self.provider,
            "is_available": self.is_available,
            "platform": self.platform,
        }


@dataclass(frozen=True)
class TaskWorkerPairing:
    task_id: str
    worker_id: str
    provider: str
    locked_resources: Set[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "provider": self.provider,
            "locked_resources": sorted(list(self.locked_resources)),
        }


@dataclass
class ParallelismPlan:
    assigned_pairings: List[TaskWorkerPairing]
    admissible_parallelism: int
    naive_parallelism: int
    unpaired_tasks: Dict[str, str]  # task_id -> reason
    unpaired_workers: List[str]
    shared_capacity_headroom: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assigned_pairings": [p.to_dict() for p in self.assigned_pairings],
            "admissible_parallelism": self.admissible_parallelism,
            "naive_parallelism": self.naive_parallelism,
            "unpaired_tasks": self.unpaired_tasks,
            "unpaired_workers": self.unpaired_workers,
            "shared_capacity_headroom": self.shared_capacity_headroom,
        }


class CannonParallelismPlanner:
    """Computes admissible conflict-free parallelism plans honoring capabilities, scopes, and provider capacity."""

    def __init__(
        self,
        provider_capacities: Optional[Dict[str, int]] = None,
    ) -> None:
        # Default capacity limits per provider
        self.provider_capacities = provider_capacities or {
            "generic": 100,
            "anthropic": 2,
            "gemini": 2,
            "openai": 2,
            "local_heavy": 1,
        }

    def compute_plan(
        self,
        ready_tasks: List[ReadyTask],
        workers: List[WorkerNode],
    ) -> ParallelismPlan:
        # Sort tasks by priority descending
        sorted_tasks = sorted(ready_tasks, key=lambda t: t.priority, reverse=True)
        available_workers = [w for w in workers if w.is_available]

        naive_parallelism = min(len(sorted_tasks), len(available_workers))

        assigned_pairings: List[TaskWorkerPairing] = []
        occupied_resources: Set[str] = set()
        occupied_workers: Set[str] = set()
        provider_usage: Dict[str, int] = {p: 0 for p in self.provider_capacities}

        unpaired_tasks: Dict[str, str] = {}

        for task in sorted_tasks:
            # 1. Scope / Resource Contention Check
            conflicting_resources = task.required_resources.intersection(occupied_resources)
            if conflicting_resources:
                unpaired_tasks[task.task_id] = f"{RejectionReason.RESOURCE_CONTENTION.value}: conflicts on {sorted(list(conflicting_resources))}"
                continue

            # 2. Shared Provider Pool Capacity Check
            provider_cap = self.provider_capacities.get(task.provider, 100)
            current_usage = provider_usage.get(task.provider, 0)
            if current_usage >= provider_cap:
                unpaired_tasks[task.task_id] = f"{RejectionReason.PROVIDER_CAPACITY_EXHAUSTED.value}: capacity {provider_cap} reached for provider '{task.provider}'"
                continue

            # 3. Compatible Worker Search
            matching_worker: Optional[WorkerNode] = None
            for worker in available_workers:
                if worker.worker_id in occupied_workers:
                    continue
                # Capability check
                if task.required_capabilities.issubset(worker.supported_capabilities):
                    matching_worker = worker
                    break

            if matching_worker is None:
                unpaired_tasks[task.task_id] = f"{RejectionReason.NO_CAPABLE_WORKER.value}: no available worker satisfies capabilities {sorted(list(task.required_capabilities))}"
                continue

            # Pair task with worker
            pairing = TaskWorkerPairing(
                task_id=task.task_id,
                worker_id=matching_worker.worker_id,
                provider=task.provider,
                locked_resources=set(task.required_resources),
            )
            assigned_pairings.append(pairing)

            # Update occupied states
            occupied_workers.add(matching_worker.worker_id)
            occupied_resources.update(task.required_resources)
            provider_usage[task.provider] = current_usage + 1

        unpaired_workers = [w.worker_id for w in available_workers if w.worker_id not in occupied_workers]

        headroom = {
            p: max(0, self.provider_capacities.get(p, 100) - provider_usage.get(p, 0))
            for p in self.provider_capacities
        }

        return ParallelismPlan(
            assigned_pairings=assigned_pairings,
            admissible_parallelism=len(assigned_pairings),
            naive_parallelism=naive_parallelism,
            unpaired_tasks=unpaired_tasks,
            unpaired_workers=unpaired_workers,
            shared_capacity_headroom=headroom,
        )

    def generate_parallelism_evidence(
        self,
        ready_tasks: List[ReadyTask],
        workers: List[WorkerNode],
    ) -> Dict[str, Any]:
        """Generates CP-21 required evidence: ['ready-frontier', 'worker-capabilities', 'shared-capacity']."""
        plan = self.compute_plan(ready_tasks, workers)

        return {
            "required_evidence": ["ready-frontier", "worker-capabilities", "shared-capacity"],
            "ready-frontier": {
                "task_count": len(ready_tasks),
                "tasks": [t.to_dict() for t in ready_tasks],
                "unpaired_tasks": plan.unpaired_tasks,
            },
            "worker-capabilities": {
                "worker_count": len(workers),
                "workers": [w.to_dict() for w in workers],
                "assigned_workers_count": len(plan.assigned_pairings),
                "unpaired_workers": plan.unpaired_workers,
            },
            "shared-capacity": {
                "provider_capacities": self.provider_capacities,
                "headroom": plan.shared_capacity_headroom,
                "admissible_parallelism": plan.admissible_parallelism,
                "naive_parallelism": plan.naive_parallelism,
                "assigned_pairings": [p.to_dict() for p in plan.assigned_pairings],
            },
        }
