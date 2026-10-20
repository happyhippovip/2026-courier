"""Adaptive Concurrency Scaler and Permit Controller.

Dynamically modulates concurrent task slots based on resource health,
headroom metrics, and queued task demand.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Sequence


@dataclass
class ScalerTelemetry:
    """Operational metrics for concurrency scaling."""

    current_slots: int
    active_count: int
    queued_count: int
    min_slots: int
    max_slots: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConcurrencyScaler:
    """Manages dynamic concurrency permits and queue scheduling."""

    def __init__(
        self,
        min_slots: int = 1,
        max_slots: int = 8,
        initial_slots: int = 2,
    ):
        self.min_slots = max(1, min_slots)
        self.max_slots = max(self.min_slots, max_slots)
        self.current_slots = max(self.min_slots, min(initial_slots, self.max_slots))
        self.active_permits: dict[str, float] = {}
        self.queued_tasks: list[str] = []

    def acquire_permit(self, task_id: str) -> bool:
        """Attempt to acquire a concurrency execution permit."""
        if len(self.active_permits) < self.current_slots:
            self.active_permits[task_id] = time.time()
            return True

        if task_id not in self.queued_tasks:
            self.queued_tasks.append(task_id)
        return False

    def release_permit(self, task_id: str) -> str | None:
        """Release active permit and promote next queued task if available."""
        self.active_permits.pop(task_id, None)

        if self.queued_tasks and len(self.active_permits) < self.current_slots:
            promoted = self.queued_tasks.pop(0)
            self.active_permits[promoted] = time.time()
            return promoted
        return None

    def adjust_capacity(
        self,
        resource_state: str,
        headroom_pct: float = 1.0,
    ) -> int:
        """Adaptively scale slots up or down based on resource telemetry."""
        state = resource_state.upper()

        if state == "NORMAL":
            if headroom_pct > 0.5 and self.current_slots < self.max_slots:
                self.current_slots += 1
        elif state == "PRESSURED":
            self.current_slots = max(self.min_slots, self.current_slots // 2)
        elif state == "COOLDOWN":
            # Freeze capacity during hysteresis cooldown
            pass

        return self.current_slots

    def get_telemetry(self) -> ScalerTelemetry:
        """Export current capacity, active count, and queue size."""
        return ScalerTelemetry(
            current_slots=self.current_slots,
            active_count=len(self.active_permits),
            queued_count=len(self.queued_tasks),
            min_slots=self.min_slots,
            max_slots=self.max_slots,
        )


def acquire_permit(scaler: ConcurrencyScaler, task_id: str) -> bool:
    return scaler.acquire_permit(task_id)


def release_permit(scaler: ConcurrencyScaler, task_id: str) -> str | None:
    return scaler.release_permit(task_id)


def adjust_capacity(scaler: ConcurrencyScaler, resource_state: str, headroom_pct: float = 1.0) -> int:
    return scaler.adjust_capacity(resource_state=resource_state, headroom_pct=headroom_pct)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adaptive Concurrency Scaler CLI.")
    parser.add_argument("--min-slots", type=int, default=1)
    parser.add_argument("--max-slots", type=int, default=8)
    parser.add_argument("--initial-slots", type=int, default=2)
    parser.add_argument("--action", choices=["telemetry", "acquire", "release"], default="telemetry")
    parser.add_argument("--task", default="sample_task")

    args = parser.parse_args(argv)

    scaler = ConcurrencyScaler(
        min_slots=args.min_slots,
        max_slots=args.max_slots,
        initial_slots=args.initial_slots,
    )

    if args.action == "telemetry":
        telem = scaler.get_telemetry()
        print(json.dumps(telem.to_dict()))
    elif args.action == "acquire":
        granted = scaler.acquire_permit(args.task)
        print(json.dumps({"granted": granted, "telemetry": scaler.get_telemetry().to_dict()}))
    elif args.action == "release":
        promoted = scaler.release_permit(args.task)
        print(json.dumps({"promoted": promoted, "telemetry": scaler.get_telemetry().to_dict()}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
