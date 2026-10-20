"""Task Priority Preemption & Fair-Share Scheduler.

Implements weighted fair-queuing, preemption of lower-priority preemptible tasks,
starvation prevention via aging, and strict worker slot concurrency enforcement.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
import json
from pathlib import Path
from typing import Any


class TaskPriority(IntEnum):
    """Priority weights for scheduled tasks."""

    BACKGROUND = 10
    NORMAL = 20
    HIGH = 50
    CRITICAL = 100


class TaskState(str, Enum):
    """Runtime lifecycle states of scheduled tasks."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PREEMPTED = "PREEMPTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


@dataclass
class ScheduledTask:
    """Descriptor for a task managed by the scheduler."""

    task_id: str
    priority: TaskPriority = TaskPriority.NORMAL
    lane: str = "default"
    preemptible: bool = True
    checkpoint: dict[str, Any] | None = None
    enqueued_at: datetime | None = None
    started_at: datetime | None = None
    state: TaskState = TaskState.PENDING
    preemptions_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.name
        d["state"] = self.state.value
        d["enqueued_at"] = self.enqueued_at.isoformat() if self.enqueued_at else None
        d["started_at"] = self.started_at.isoformat() if self.started_at else None
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduledTask:
        p_val = data.get("priority", "NORMAL")
        priority = TaskPriority[p_val] if isinstance(p_val, str) else TaskPriority(p_val)
        state_val = data.get("state", "PENDING")
        state = TaskState(state_val)

        return cls(
            task_id=data["task_id"],
            priority=priority,
            lane=data.get("lane", "default"),
            preemptible=bool(data.get("preemptible", True)),
            checkpoint=data.get("checkpoint"),
            enqueued_at=_parse_dt(data.get("enqueued_at")),
            started_at=_parse_dt(data.get("started_at")),
            state=state,
            preemptions_count=int(data.get("preemptions_count", 0)),
        )


class PriorityPreemptionScheduler:
    """Scheduler managing slots, priority queuing, and safe preemption."""

    def __init__(
        self,
        max_slots: int = 4,
        starvation_threshold_seconds: float = 60.0,
        state_file: Path | None = None,
    ) -> None:
        self.max_slots = max(1, max_slots)
        self.starvation_threshold_seconds = max(1.0, starvation_threshold_seconds)
        self.state_file = Path(state_file) if state_file else None

        self.ready_queue: list[ScheduledTask] = []
        self.running_tasks: dict[str, ScheduledTask] = {}

        if self.state_file and self.state_file.is_file():
            self._load_state()

    @property
    def active_slots_count(self) -> int:
        return len(self.running_tasks)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def enqueue(self, task: ScheduledTask) -> None:
        """Add a task to the ready queue with strict task_id deduplication."""
        if task.task_id in self.running_tasks:
            return
        for existing in self.ready_queue:
            if existing.task_id == task.task_id:
                if task.priority > existing.priority:
                    existing.priority = task.priority
                self._save_state()
                return
        if task.enqueued_at is None:
            task.enqueued_at = self._now()
        if task.state != TaskState.PREEMPTED:
            task.state = TaskState.PENDING
        self.ready_queue.append(task)
        self._save_state()

    def effective_priority(self, task: ScheduledTask, now: datetime | None = None) -> float:
        """Calculate effective priority with wait-time starvation aging."""
        if now is None:
            now = self._now()
        base_score = float(task.priority.value)
        if task.enqueued_at:
            wait_seconds = max(0.0, (now - task.enqueued_at).total_seconds())
            if wait_seconds > self.starvation_threshold_seconds:
                excess = wait_seconds - self.starvation_threshold_seconds
                base_score += excess * 2.0  # Dynamic aging boost
        return base_score

    def tick(self, now: datetime | None = None) -> list[ScheduledTask]:
        """Evaluate ready queue and running tasks; perform dispatches & preemptions."""
        if now is None:
            now = self._now()

        dispatched: list[ScheduledTask] = []

        while self.ready_queue:
            # Sort ready queue by effective priority descending, then FIFO on enqueue time
            self.ready_queue.sort(
                key=lambda t: (self.effective_priority(t, now), -(t.enqueued_at.timestamp() if t.enqueued_at else 0.0)),
                reverse=True,
            )
            highest_ready = self.ready_queue[0]

            if self.active_slots_count < self.max_slots:
                # Slot available -> allocate and run
                self.ready_queue.pop(0)
                highest_ready.state = TaskState.RUNNING
                highest_ready.started_at = now
                self.running_tasks[highest_ready.task_id] = highest_ready
                dispatched.append(highest_ready)
            else:
                # Slots full -> check if highest_ready can preempt a running task
                # Only tasks running prior to this tick can be preempted (prevent intra-tick thrashing)
                candidates = [
                    t for t in self.running_tasks.values()
                    if t.preemptible and t not in dispatched
                ]
                if not candidates:
                    break

                # Pick candidate with lowest effective priority
                candidates.sort(key=lambda t: self.effective_priority(t, now))
                lowest_running = candidates[0]

                if self.effective_priority(highest_ready, now) > self.effective_priority(lowest_running, now):
                    # Preempt lowest_running
                    self.ready_queue.pop(0)
                    del self.running_tasks[lowest_running.task_id]
                    lowest_running.state = TaskState.PREEMPTED
                    lowest_running.preemptions_count += 1
                    self.ready_queue.append(lowest_running)

                    # Dispatch highest_ready
                    highest_ready.state = TaskState.RUNNING
                    highest_ready.started_at = now
                    self.running_tasks[highest_ready.task_id] = highest_ready
                    dispatched.append(highest_ready)
                else:
                    break

        self._save_state()
        return dispatched

    def complete_task(self, task_id: str) -> bool:
        """Mark a running task as completed, freeing its worker slot."""
        if task_id in self.running_tasks:
            task = self.running_tasks.pop(task_id)
            task.state = TaskState.COMPLETED
            self._save_state()
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending, preempted, or running task."""
        if task_id in self.running_tasks:
            task = self.running_tasks.pop(task_id)
            task.state = TaskState.CANCELLED
            self._save_state()
            return True

        for i, t in enumerate(self.ready_queue):
            if t.task_id == task_id:
                t.state = TaskState.CANCELLED
                self.ready_queue.pop(i)
                self._save_state()
                return True

        return False

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status of current slots and queues."""
        return {
            "max_slots": self.max_slots,
            "active_slots": self.active_slots_count,
            "ready_count": len(self.ready_queue),
            "running": [t.to_dict() for t in self.running_tasks.values()],
            "ready": [t.to_dict() for t in self.ready_queue],
        }

    def _save_state(self) -> None:
        if not self.state_file:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "max_slots": self.max_slots,
            "starvation_threshold_seconds": self.starvation_threshold_seconds,
            "running": [t.to_dict() for t in self.running_tasks.values()],
            "ready": [t.to_dict() for t in self.ready_queue],
        }
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        if not self.state_file or not self.state_file.is_file():
            return
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.max_slots = data.get("max_slots", self.max_slots)
        self.starvation_threshold_seconds = data.get(
            "starvation_threshold_seconds", self.starvation_threshold_seconds
        )
        self.running_tasks = {
            t["task_id"]: ScheduledTask.from_dict(t) for t in data.get("running", [])
        }
        deduped_ready: list[ScheduledTask] = []
        seen_ids: set[str] = set(self.running_tasks.keys())
        for raw_task in data.get("ready", []):
            parsed = ScheduledTask.from_dict(raw_task)
            if parsed.task_id not in seen_ids:
                seen_ids.add(parsed.task_id)
                deduped_ready.append(parsed)
        self.ready_queue = deduped_ready


_DEFAULT_STATE_FILE = Path("./run/scheduler_state.json")
_CLI_SCHEDULER_INSTANCE: PriorityPreemptionScheduler | None = None


def get_cli_scheduler(state_path: Path | None = None) -> PriorityPreemptionScheduler:
    global _CLI_SCHEDULER_INSTANCE
    target = state_path or _DEFAULT_STATE_FILE
    if _CLI_SCHEDULER_INSTANCE is None or _CLI_SCHEDULER_INSTANCE.state_file != target:
        _CLI_SCHEDULER_INSTANCE = PriorityPreemptionScheduler(max_slots=2, state_file=target)
    return _CLI_SCHEDULER_INSTANCE


def main() -> None:
    parser = argparse.ArgumentParser(description="Task Priority Preemption & Fair-Share Scheduler")
    parser.add_argument("--state-file", default=None, help="Path to state file")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # enqueue
    enq_p = subparsers.add_parser("enqueue", help="Enqueue a new task")
    enq_p.add_argument("--task-id", required=True, help="Unique task identifier")
    enq_p.add_argument(
        "--priority",
        choices=["BACKGROUND", "NORMAL", "HIGH", "CRITICAL"],
        default="NORMAL",
        help="Task priority",
    )
    enq_p.add_argument("--lane", default="default", help="Lane or category")
    enq_p.add_argument("--preemptible", action="store_true", default=True, help="Is preemptible")

    # status
    subparsers.add_parser("status", help="Get current scheduler status")

    # tick
    subparsers.add_parser("tick", help="Execute scheduler dispatch tick")

    # complete
    comp_p = subparsers.add_parser("complete", help="Complete a running task")
    comp_p.add_argument("--task-id", required=True, help="Task identifier")

    args = parser.parse_args()
    state_file = Path(args.state_file) if args.state_file else None
    scheduler = get_cli_scheduler(state_file)

    if args.action == "enqueue":
        task = ScheduledTask(
            task_id=args.task_id,
            priority=TaskPriority[args.priority],
            lane=args.lane,
            preemptible=args.preemptible,
        )
        scheduler.enqueue(task)
        print(f"Enqueued {args.task_id} with priority {args.priority}")
    elif args.action == "status":
        print(json.dumps(scheduler.get_status(), indent=2))
    elif args.action == "tick":
        dispatched = scheduler.tick()
        print(f"Dispatched {len(dispatched)} tasks: {[t.task_id for t in dispatched]}")
    elif args.action == "complete":
        ok = scheduler.complete_task(args.task_id)
        print(f"Completed {args.task_id}: {ok}")


if __name__ == "__main__":
    main()
