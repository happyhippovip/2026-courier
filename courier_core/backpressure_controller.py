"""Dynamic Backpressure Flow Controller and Rate Governor for Courier Symphony.

Provides adaptive permit admission (AIMD), dynamic inflight capacity management,
and fail-closed load shedding under critical queue pressure or cluster degradation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class FlowState(str, Enum):
    HEALTHY = "HEALTHY"
    THROTTLED = "THROTTLED"
    SHED_LOAD = "SHED_LOAD"
    DRAINING = "DRAINING"


class BackpressureError(Exception):
    """Base error for backpressure violations."""
    pass


class PermitExhaustedError(BackpressureError):
    """Raised when maximum inflight concurrency is reached."""
    pass


class BackpressureShedLoadError(BackpressureError):
    """Raised when the controller sheds load under critical degradation."""
    pass


@dataclass
class BackpressureDirective:
    state: FlowState
    current_rate: float
    inflight_count: int
    max_inflight: int
    reason: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class BackpressureController:
    """Dynamic AIMD backpressure flow controller and rate governor."""

    def __init__(
        self,
        store_path: Optional[str] = None,
        initial_rate: float = 10.0,
        min_rate: float = 1.0,
        max_rate: float = 100.0,
        additive_step: float = 2.0,
        backoff_factor: float = 0.5,
        max_inflight: int = 20,
        latency_threshold_ms: float = 1000.0,
        error_threshold_shed: float = 0.5,
    ):
        self.store_path = store_path
        self.initial_rate = initial_rate
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.additive_step = additive_step
        self.backoff_factor = backoff_factor
        self.max_inflight = max_inflight
        self.latency_threshold_ms = latency_threshold_ms
        self.error_threshold_shed = error_threshold_shed

        self.state: FlowState = FlowState.HEALTHY
        self.last_reason: str = "Initial healthy startup"
        self.active_inflight: Set[str] = set()
        self.recent_feedback: List[Dict[str, Any]] = []

        if self.store_path and Path(self.store_path).exists():
            self.load()

    @property
    def inflight_count(self) -> int:
        return len(self.active_inflight)

    def report_feedback(self, latency_ms: float, is_error: bool) -> None:
        """Report execution feedback and adapt rate via AIMD."""
        now = datetime.now(timezone.utc).isoformat()
        self.recent_feedback.append({
            "latency_ms": latency_ms,
            "is_error": is_error,
            "timestamp": now,
        })
        if len(self.recent_feedback) > 30:
            self.recent_feedback.pop(0)

        # Rate adaptation: Additive-Increase / Multiplicative-Decrease
        if is_error or latency_ms > self.latency_threshold_ms:
            self.current_rate = max(self.min_rate, round(self.current_rate * self.backoff_factor, 2))
            self.last_reason = f"Degradation detected: latency={latency_ms:.1f}ms, error={is_error}"
        else:
            self.current_rate = min(self.max_rate, round(self.current_rate + self.additive_step, 2))
            self.last_reason = f"Normal execution: latency={latency_ms:.1f}ms"

        # Check for error burst triggering SHED_LOAD
        if len(self.recent_feedback) >= 3:
            errors = sum(1 for f in self.recent_feedback if f["is_error"])
            error_ratio = errors / len(self.recent_feedback)
            if error_ratio >= self.error_threshold_shed:
                self.state = FlowState.SHED_LOAD
                self.last_reason = f"Critical error burst: {error_ratio*100:.1f}% errors exceed {self.error_threshold_shed*100:.1f}% threshold"
                return

        # State transition according to current rate and manual draining
        if self.state != FlowState.DRAINING:
            if self.current_rate < (self.initial_rate * 0.75):
                self.state = FlowState.THROTTLED
            else:
                self.state = FlowState.HEALTHY

    def acquire_permit(self, task_id: str) -> bool:
        """Acquire an execution permit under backpressure rules."""
        if self.state == FlowState.SHED_LOAD:
            raise BackpressureShedLoadError(f"Rejected: system is in SHED_LOAD ({self.last_reason})")

        if len(self.active_inflight) >= self.max_inflight:
            raise PermitExhaustedError(
                f"Rejected: inflight limit of {self.max_inflight} tasks reached (currently {len(self.active_inflight)})"
            )

        self.active_inflight.add(task_id)
        return True

    def release_permit(self, task_id: str) -> None:
        """Release an inflight permit upon task completion or failure."""
        self.active_inflight.discard(task_id)

    def set_state(self, state: FlowState, reason: str = "") -> None:
        """Manually override or transition the flow state."""
        self.state = state
        if reason:
            self.last_reason = reason

    def get_directive(self) -> BackpressureDirective:
        """Return the current backpressure control directive."""
        return BackpressureDirective(
            state=self.state,
            current_rate=self.current_rate,
            inflight_count=self.inflight_count,
            max_inflight=self.max_inflight,
            reason=self.last_reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def save(self) -> None:
        """Persist backpressure governor state to disk."""
        if not self.store_path:
            return
        p = Path(self.store_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_rate": self.current_rate,
            "min_rate": self.min_rate,
            "max_rate": self.max_rate,
            "state": self.state.value,
            "last_reason": self.last_reason,
            "active_inflight": sorted(list(self.active_inflight)),
            "recent_feedback": self.recent_feedback,
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        """Load backpressure governor state from disk."""
        if not self.store_path or not Path(self.store_path).exists():
            return
        raw = json.loads(Path(self.store_path).read_text(encoding="utf-8"))
        self.current_rate = float(raw.get("current_rate", self.current_rate))
        self.min_rate = float(raw.get("min_rate", self.min_rate))
        self.max_rate = float(raw.get("max_rate", self.max_rate))
        self.state = FlowState(raw.get("state", self.state.value))
        self.last_reason = raw.get("last_reason", self.last_reason)
        self.active_inflight = set(raw.get("active_inflight", []))
        self.recent_feedback = raw.get("recent_feedback", [])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Dynamic Backpressure Flow Controller CLI")
    parser.add_argument("--store", default="registries/backpressure_state.json", help="Path to state JSON")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # status
    sub.add_parser("status", help="Display current backpressure directive and status")

    # acquire
    p_acq = sub.add_parser("acquire", help="Attempt to acquire an execution permit")
    p_acq.add_argument("--task-id", required=True, help="Task identifier")

    # release
    p_rel = sub.add_parser("release", help="Release an inflight execution permit")
    p_rel.add_argument("--task-id", required=True, help="Task identifier")

    # feedback
    p_fb = sub.add_parser("feedback", help="Report execution telemetry feedback")
    p_fb.add_argument("--latency-ms", type=float, required=True, help="Task duration in ms")
    p_fb.add_argument("--error", action="store_true", help="Flag if task resulted in failure")

    # reset
    sub.add_parser("reset", help="Reset controller to initial healthy state")

    args = parser.parse_args(argv)
    controller = BackpressureController(store_path=args.store)

    if args.subcommand == "status":
        directive = controller.get_directive()
        print(f"Backpressure State: {directive.state.value}")
        print(f"Rate: {directive.current_rate:.1f} permits/sec | Inflight: {directive.inflight_count}/{directive.max_inflight}")
        print(f"Reason: {directive.reason}")
        return 0

    elif args.subcommand == "acquire":
        try:
            controller.acquire_permit(args.task_id)
            controller.save()
            print(f"ACQUIRED permit for task {args.task_id} (inflight={controller.inflight_count})")
            return 0
        except BackpressureError as err:
            print(f"REJECTED: {err}", file=sys.stderr)
            return 1

    elif args.subcommand == "release":
        controller.release_permit(args.task_id)
        controller.save()
        print(f"RELEASED permit for task {args.task_id} (inflight={controller.inflight_count})")
        return 0

    elif args.subcommand == "feedback":
        controller.report_feedback(latency_ms=args.latency_ms, is_error=args.error)
        controller.save()
        print(f"UPDATED rate to {controller.current_rate:.1f} permits/sec (state={controller.state.value})")
        return 0

    elif args.subcommand == "reset":
        controller.state = FlowState.HEALTHY
        controller.current_rate = controller.initial_rate
        controller.active_inflight.clear()
        controller.recent_feedback.clear()
        controller.last_reason = "Manual reset"
        controller.save()
        print("RESET backpressure governor to initial healthy state")
        return 0

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
