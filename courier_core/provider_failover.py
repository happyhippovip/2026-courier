"""Dynamic Provider Fallback and Circuit-Breaker Failover Router (P31)

Provides cascade routing across multiple execution providers with zero-cost
spending gate enforcement, circuit-breaker isolation, and comprehensive attempt
auditing to ensure resilient, fail-closed autonomous task execution.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from courier_core.provider_cost_guard import evaluate_cost_gate


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitBreakerState.CLOSED

    def can_attempt(self) -> bool:
        now = time.time()
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if now - self.last_failure_time >= self.cooldown_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


@dataclass
class ProviderCandidate:
    provider_id: str
    cost_estimate_eur: Optional[float] = None
    model: str = "default"
    handler: Optional[Callable[[], Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "cost_estimate_eur": self.cost_estimate_eur,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProviderCandidate:
        return cls(
            provider_id=str(data.get("provider_id", "")),
            cost_estimate_eur=data.get("cost_estimate_eur"),
            model=str(data.get("model", "default")),
        )


@dataclass
class RoutingResult:
    success: bool
    chosen_provider: Optional[str] = None
    output: Any = None
    error: Optional[str] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "chosen_provider": self.chosen_provider,
            "error": self.error,
            "attempts": list(self.attempts),
        }


class ProviderFailoverRouter:
    """Manages fallback routing, zero-cost budget guards, and circuit breaking across providers."""

    def __init__(
        self,
        autonomous_spend_limit_eur: float = 0.0,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.spend_limit_eur = autonomous_spend_limit_eur
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._circuits: Dict[str, CircuitBreaker] = {}

    def _get_circuit(self, provider_id: str) -> CircuitBreaker:
        if provider_id not in self._circuits:
            self._circuits[provider_id] = CircuitBreaker(
                failure_threshold=self.failure_threshold,
                cooldown_seconds=self.cooldown_seconds,
            )
        return self._circuits[provider_id]

    def get_circuit_state(self, provider_id: str) -> CircuitBreakerState:
        cb = self._get_circuit(provider_id)
        # Refresh half-open if cooldown passed
        cb.can_attempt()
        return cb.state

    def execute_with_failover(
        self,
        candidates: List[ProviderCandidate],
        idempotent: bool = True,
    ) -> RoutingResult:
        attempts: List[Dict[str, Any]] = []

        for candidate in candidates:
            provider_id = candidate.provider_id

            # 1. Cost Gate check
            provider_spec = {
                "provider": provider_id,
                "model": candidate.model,
                "cost_estimate_eur": candidate.cost_estimate_eur,
            }
            verdict = evaluate_cost_gate(provider_spec, self.spend_limit_eur)
            if not verdict.allowed:
                attempts.append({
                    "provider": provider_id,
                    "status": "COST_GATE_BLOCKED",
                    "reason": verdict.reason,
                })
                continue

            # 2. Circuit Breaker check
            cb = self._get_circuit(provider_id)
            if not cb.can_attempt():
                attempts.append({
                    "provider": provider_id,
                    "status": "CIRCUIT_OPEN_SKIPPED",
                    "reason": f"Circuit breaker for '{provider_id}' is OPEN",
                })
                continue

            # 3. Execution or Selection
            if candidate.handler is None:
                # Dry run / candidate selection mode
                attempts.append({"provider": provider_id, "status": "SELECTED"})
                return RoutingResult(
                    success=True,
                    chosen_provider=provider_id,
                    output=None,
                    attempts=attempts,
                )

            try:
                result = candidate.handler()
                cb.record_success()
                attempts.append({"provider": provider_id, "status": "SUCCESS"})
                return RoutingResult(
                    success=True,
                    chosen_provider=provider_id,
                    output=result,
                    attempts=attempts,
                )
            except Exception as e:
                cb.record_failure()
                attempts.append({
                    "provider": provider_id,
                    "status": "FAILED",
                    "error": str(e),
                })
                if not idempotent:
                    return RoutingResult(
                        success=False,
                        chosen_provider=None,
                        error="NON_IDEMPOTENT_HANDLER_FAILED_NO_FAILOVER",
                        attempts=attempts,
                    )
                continue

        return RoutingResult(
            success=False,
            chosen_provider=None,
            error="ALL_PROVIDERS_EXHAUSTED_OR_BLOCKED",
            attempts=attempts,
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Provider Failover Router CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    select_parser = subparsers.add_parser("select", help="Select best available provider candidate")
    select_parser.add_argument("--candidates", required=True, help="JSON file containing candidate list")
    select_parser.add_argument("--spend-limit", type=float, default=0.0, help="Autonomous spend limit EUR")

    args = parser.parse_args(argv)

    if args.command == "select":
        data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
        raw_candidates = data.get("candidates", [])
        candidates = [ProviderCandidate.from_dict(c) for c in raw_candidates]

        router = ProviderFailoverRouter(autonomous_spend_limit_eur=args.spend_limit)
        result = router.execute_with_failover(candidates)

        print(json.dumps({
            "status": "SELECTED" if result.success else "REJECTED",
            "selected_provider": result.chosen_provider,
            "error": result.error,
            "attempts": result.attempts,
        }, indent=2))
        return 0 if result.success else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
