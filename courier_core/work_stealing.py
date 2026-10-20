"""Cross-Worker Work Stealing & Dynamic Load Balancer.

Implements decentralized work stealing from peer ready queues, fencing tokens
for atomic ownership reassignment, capability constraints, and load equilibrium.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


class WorkStealingError(Exception):
    """Base exception for work stealing engine."""


class NoStealableTaskError(WorkStealingError):
    """Raised when victim worker has no ready or eligible tasks to steal."""


class IncompatibleCapabilityError(WorkStealingError):
    """Raised when stealer worker lacks required capabilities for a task."""


class CapacityExceededError(WorkStealingError):
    """Raised when stealer worker is already at full capacity."""


class StaleFencingTokenError(WorkStealingError):
    """Raised when an execution attempt uses an obsolete fencing token or wrong owner."""


@dataclass
class StealableTask:
    """Descriptor for a task that can be scheduled or stolen across workers."""

    task_id: str
    owner: str
    required_capabilities: set[str] = field(default_factory=set)
    fencing_token: int = 0
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "owner": self.owner,
            "required_capabilities": sorted(list(self.required_capabilities)),
            "fencing_token": self.fencing_token,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StealableTask:
        return cls(
            task_id=data["task_id"],
            owner=data["owner"],
            required_capabilities=set(data.get("required_capabilities", [])),
            fencing_token=int(data.get("fencing_token", 0)),
            payload=data.get("payload", {}),
        )


@dataclass
class WorkerNodeDescriptor:
    """Descriptor tracking worker capacity, capabilities, and local queues."""

    worker_id: str
    capacity: int = 4
    capabilities: set[str] = field(default_factory=set)
    ready_tasks: list[StealableTask] = field(default_factory=list)
    running_tasks: dict[str, StealableTask] = field(default_factory=dict)

    @property
    def ready_count(self) -> int:
        return len(self.ready_tasks)

    @property
    def running_count(self) -> int:
        return len(self.running_tasks)

    @property
    def total_load(self) -> int:
        return self.ready_count + self.running_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "capacity": self.capacity,
            "capabilities": sorted(list(self.capabilities)),
            "ready_count": self.ready_count,
            "running_count": self.running_count,
            "total_load": self.total_load,
            "ready_tasks": [t.to_dict() for t in self.ready_tasks],
            "running_tasks": [t.to_dict() for t in self.running_tasks.values()],
        }


class WorkStealingCluster:
    """Cluster coordinator managing peer worker descriptors, stealing, and rebalancing."""

    def __init__(self) -> None:
        self.workers: dict[str, WorkerNodeDescriptor] = {}
        self.task_registry: dict[str, StealableTask] = {}

    def register_worker(
        self,
        worker_id: str,
        capacity: int = 4,
        capabilities: set[str] | list[str] | None = None,
    ) -> WorkerNodeDescriptor:
        """Register or update a worker node."""
        caps = set(capabilities) if capabilities else set()
        existing = self.workers.get(worker_id)
        if existing is not None:
            # Re-register (e.g. after reconnect) must not wipe owned queues:
            # update capacity/capabilities in place so ready/running tasks and
            # registry ownership stay consistent.
            existing.capacity = max(1, capacity)
            existing.capabilities = caps
            return existing
        node = WorkerNodeDescriptor(
            worker_id=worker_id,
            capacity=max(1, capacity),
            capabilities=caps,
        )
        self.workers[worker_id] = node
        return node

    def get_worker(self, worker_id: str) -> WorkerNodeDescriptor:
        if worker_id not in self.workers:
            raise KeyError(f"Unknown worker: {worker_id}")
        return self.workers[worker_id]

    def enqueue_task(self, worker_id: str, task: StealableTask) -> None:
        """Enqueue a task onto a worker's local ready queue."""
        if task.task_id in self.task_registry:
            raise KeyError(f"Duplicate task_id: {task.task_id}")
        worker = self.get_worker(worker_id)
        task.owner = worker_id
        self.task_registry[task.task_id] = task
        worker.ready_tasks.append(task)

    def start_task(self, worker_id: str, task_id: str) -> StealableTask:
        """Transition a task from ready to running."""
        worker = self.get_worker(worker_id)
        match_idx = next(
            (i for i, t in enumerate(worker.ready_tasks) if t.task_id == task_id), None
        )
        if match_idx is None:
            raise KeyError(f"Task {task_id} not in ready queue of {worker_id}")

        task = worker.ready_tasks.pop(match_idx)
        worker.running_tasks[task_id] = task
        return task

    def complete_task(self, worker_id: str, task_id: str) -> bool:
        """Mark a running task as completed."""
        worker = self.get_worker(worker_id)
        if task_id in worker.running_tasks:
            del worker.running_tasks[task_id]
            self.task_registry.pop(task_id, None)
            return True
        return False

    def steal_task(self, stealer_id: str, victim_id: str) -> StealableTask:
        """Steal an eligible task from the tail of victim's ready queue."""
        stealer = self.get_worker(stealer_id)
        victim = self.get_worker(victim_id)

        if stealer.total_load >= stealer.capacity:
            raise CapacityExceededError(
                f"Stealer {stealer_id} at capacity ({stealer.total_load}/{stealer.capacity})"
            )

        if not victim.ready_tasks:
            raise NoStealableTaskError(f"Victim {victim_id} has no ready tasks to steal")

        # Search from tail of victim's ready queue (reverse order)
        chosen_idx: int | None = None
        for idx in range(len(victim.ready_tasks) - 1, -1, -1):
            candidate = victim.ready_tasks[idx]
            if candidate.required_capabilities.issubset(stealer.capabilities):
                chosen_idx = idx
                break

        if chosen_idx is None:
            raise IncompatibleCapabilityError(
                f"Stealer {stealer_id} lacks required capabilities for victim tasks"
            )

        stolen = victim.ready_tasks.pop(chosen_idx)
        stolen.owner = stealer_id
        stolen.fencing_token += 1
        stealer.ready_tasks.append(stolen)

        return stolen

    def verify_execution_token(self, task_id: str, worker_id: str, token: int) -> bool:
        """Verify that a worker holds the valid fencing token to execute task."""
        if task_id not in self.task_registry:
            raise KeyError(f"Task not found: {task_id}")
        task = self.task_registry[task_id]
        if task.owner != worker_id or task.fencing_token != token:
            raise StaleFencingTokenError(
                f"Stale or unauthorized execution for {task_id}: expected owner {task.owner} token {task.fencing_token}, got {worker_id} token {token}"
            )
        return True

    def rebalance(self) -> int:
        """Redistribute load across workers towards equilibrium."""
        transferred = 0
        changed = True

        while changed:
            changed = False
            active_nodes = [w for w in self.workers.values() if w.capacity > 0]
            if len(active_nodes) < 2:
                break

            active_nodes.sort(key=lambda w: w.total_load, reverse=True)
            most_loaded = active_nodes[0]
            least_loaded = active_nodes[-1]

            diff = most_loaded.total_load - least_loaded.total_load
            if diff > 1 and least_loaded.total_load < least_loaded.capacity and most_loaded.ready_count > 0:
                try:
                    self.steal_task(stealer_id=least_loaded.worker_id, victim_id=most_loaded.worker_id)
                    transferred += 1
                    changed = True
                except WorkStealingError:
                    break

        return transferred

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic metrics of cluster state."""
        return {
            "workers_count": len(self.workers),
            "total_tasks_tracked": len(self.task_registry),
            "workers": {w_id: w.to_dict() for w_id, w in self.workers.items()},
        }


_GLOBAL_CLUSTER_INSTANCE: WorkStealingCluster | None = None


def get_global_cluster() -> WorkStealingCluster:
    global _GLOBAL_CLUSTER_INSTANCE
    if _GLOBAL_CLUSTER_INSTANCE is None:
        _GLOBAL_CLUSTER_INSTANCE = WorkStealingCluster()
    return _GLOBAL_CLUSTER_INSTANCE


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-Worker Work Stealing & Load Balancer")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # register
    reg_p = subparsers.add_parser("register", help="Register a worker node")
    reg_p.add_argument("--worker-id", required=True, help="Worker ID")
    reg_p.add_argument("--capacity", type=int, default=4, help="Capacity limit")
    reg_p.add_argument("--capabilities", default="cpu", help="Comma-separated capabilities")

    # enqueue
    enq_p = subparsers.add_parser("enqueue", help="Enqueue task to worker")
    enq_p.add_argument("--worker-id", required=True, help="Target worker ID")
    enq_p.add_argument("--task-id", required=True, help="Task ID")
    enq_p.add_argument("--capabilities", default="cpu", help="Comma-separated required capabilities")

    # steal
    stl_p = subparsers.add_parser("steal", help="Steal task from victim worker")
    stl_p.add_argument("--stealer", required=True, help="Stealer worker ID")
    stl_p.add_argument("--victim", required=True, help="Victim worker ID")

    # rebalance
    subparsers.add_parser("rebalance", help="Trigger cluster rebalance")

    # status
    subparsers.add_parser("status", help="Get cluster status")

    args = parser.parse_args()
    cluster = get_global_cluster()

    if args.action == "register":
        caps = set(args.capabilities.split(",")) if args.capabilities else set()
        cluster.register_worker(args.worker_id, capacity=args.capacity, capabilities=caps)
        print(f"Registered worker {args.worker_id}")
    elif args.action == "enqueue":
        caps = set(args.capabilities.split(",")) if args.capabilities else set()
        t = StealableTask(task_id=args.task_id, owner=args.worker_id, required_capabilities=caps)
        cluster.enqueue_task(args.worker_id, t)
        print(f"Enqueued {args.task_id} on {args.worker_id}")
    elif args.action == "steal":
        stolen = cluster.steal_task(args.stealer, args.victim)
        print(f"Worker {args.stealer} stole task {stolen.task_id} (fencing token: {stolen.fencing_token})")
    elif args.action == "rebalance":
        n = cluster.rebalance()
        print(f"Rebalanced cluster, transferred {n} tasks")
    elif args.action == "status":
        print(json.dumps(cluster.get_status(), indent=2))


if __name__ == "__main__":
    main()
