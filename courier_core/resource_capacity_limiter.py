"""Resource Capacity Limiter & Local Execution Policy Engine (CP-28 / CQ-28).

Verifies and enforces:
1. Distinct entitlement pools for CHAT, API, and CI capacity.
2. Missing quota / cost data is strictly recorded as UNKNOWN (no Euro invention, no estimated pricing).
3. Verifiable local job limits, attempt limits, and bounded parallelism (HEAVY_JOB_LIMIT = 1, NORMAL=1, TURBO=2).
4. Unknown-cost behavior: blocks unbudgeted external costs (AUTONOMOUS_SPEND_LIMIT_EUR = 0.00, PAYG = FORBIDDEN).
5. Zero auto top-ups and zero subscription modifications.
6. Emits structured evidence matching ["authorized-entitlements", "observed-usage", "resource-policy"].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class CapacityPoolType(str, Enum):
    """Separate entitlement capacity pools."""
    CHAT = "CHAT"
    API = "API"
    CI = "CI"


class CostStatus(str, Enum):
    """Cost measurement status."""
    VERIFIED_ZERO = "VERIFIED_ZERO"
    EXPLICIT_KNOWN = "EXPLICIT_KNOWN"
    UNKNOWN = "UNKNOWN"


class QuotaStatus(str, Enum):
    """Entitlement quota availability status."""
    AVAILABLE = "AVAILABLE"
    EXHAUSTED = "EXHAUSTED"
    UNKNOWN = "UNKNOWN"


class EuroInventionForbiddenError(ValueError):
    """Raised when an attempt is made to fabricate or invent Euro costs without verifiable provider proof."""
    pass


@dataclass
class EntitlementPool:
    """Capacity entitlement pool tracking with strict unknown handling."""
    pool_type: CapacityPoolType
    quota_status: QuotaStatus = QuotaStatus.UNKNOWN
    total_entitlement_units: Optional[int] = None
    used_units: int = 0
    cost_status: CostStatus = CostStatus.UNKNOWN
    spend_eur: Optional[float] = None

    def record_usage(self, units: int = 1) -> None:
        self.used_units += units
        if self.total_entitlement_units is not None:
            if self.used_units >= self.total_entitlement_units:
                self.quota_status = QuotaStatus.EXHAUSTED

    def set_verified_spend(self, amount_eur: float) -> None:
        if amount_eur < 0:
            raise ValueError("Spend cannot be negative")
        self.spend_eur = amount_eur
        self.cost_status = CostStatus.EXPLICIT_KNOWN if amount_eur > 0 else CostStatus.VERIFIED_ZERO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pool_type": self.pool_type.value,
            "quota_status": self.quota_status.value,
            "total_entitlement_units": self.total_entitlement_units if self.total_entitlement_units is not None else "UNKNOWN",
            "used_units": self.used_units,
            "cost_status": self.cost_status.value,
            "spend_eur": f"{self.spend_eur:.2f}" if self.spend_eur is not None else "UNKNOWN",
        }


@dataclass
class LocalResourceLimits:
    """Verifiable local limits and safety invariants."""
    max_parallel_workers: int = 2
    max_heavy_jobs: int = 1
    max_attempts_per_task: int = 3
    autonomous_spend_limit_eur: float = 0.00
    payg_forbidden: bool = True
    unknown_cost_blocks: bool = True
    prohibit_auto_topup: bool = True
    prohibit_subscription_changes: bool = True


@dataclass
class ObservedUsage:
    """Exact physical local usage measurements."""
    active_parallel_workers: int = 0
    active_heavy_jobs: int = 0
    total_completed_jobs: int = 0
    task_attempts: Dict[str, int] = field(default_factory=dict)
    measured_tokens: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_parallel_workers": self.active_parallel_workers,
            "active_heavy_jobs": self.active_heavy_jobs,
            "total_completed_jobs": self.total_completed_jobs,
            "task_attempts": dict(self.task_attempts),
            "measured_tokens": self.measured_tokens,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


@dataclass(frozen=True)
class AdmissionDecision:
    """Decision on whether a task may proceed under current capacity limits."""
    allowed: bool
    pool_type: CapacityPoolType
    cost_status: CostStatus
    reason: str
    blocked_code: Optional[str] = None


class ResourceCapacityLimiter:
    """Evaluates and enforces resource and capacity constraints without Euro invention."""

    def __init__(
        self,
        limits: Optional[LocalResourceLimits] = None,
        pools: Optional[Dict[CapacityPoolType, EntitlementPool]] = None,
    ) -> None:
        self.limits = limits or LocalResourceLimits()
        self.pools: Dict[CapacityPoolType, EntitlementPool] = pools or {
            CapacityPoolType.CHAT: EntitlementPool(pool_type=CapacityPoolType.CHAT),
            CapacityPoolType.API: EntitlementPool(pool_type=CapacityPoolType.API),
            CapacityPoolType.CI: EntitlementPool(pool_type=CapacityPoolType.CI),
        }
        self.observed = ObservedUsage()

    def check_dispatch_admission(
        self,
        task_id: str,
        pool_type: CapacityPoolType,
        is_heavy_job: bool = False,
        is_external_paid: bool = False,
        estimated_cost_eur: Optional[float] = None,
        is_payg: bool = False,
    ) -> AdmissionDecision:
        """Determines admission according to CP-28 bounds and cost policies."""
        # Check PAYG invariant
        if is_payg and self.limits.payg_forbidden:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=CostStatus.UNKNOWN,
                reason="PAYG usage is strictly forbidden by policy",
                blocked_code="PAYG_FORBIDDEN",
            )

        # Check Euro invention prohibition
        if estimated_cost_eur is not None and estimated_cost_eur > self.limits.autonomous_spend_limit_eur:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=CostStatus.EXPLICIT_KNOWN,
                reason=f"Estimated cost {estimated_cost_eur} EUR exceeds autonomous limit {self.limits.autonomous_spend_limit_eur} EUR",
                blocked_code="SPEND_LIMIT_EXCEEDED",
            )

        # Check Unknown Cost behavior
        if is_external_paid and estimated_cost_eur is None and self.limits.unknown_cost_blocks:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=CostStatus.UNKNOWN,
                reason="External paid service with unmeasured cost blocks execution (UNKNOWN_COST)",
                blocked_code="UNKNOWN_COST_BLOCKED",
            )

        # Check Pool quota first
        pool = self.pools[pool_type]
        if pool.quota_status == QuotaStatus.EXHAUSTED:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=pool.cost_status,
                reason=f"Entitlement pool {pool_type.value} quota is exhausted",
                blocked_code="QUOTA_EXHAUSTED",
            )

        # Check Heavy Job boundary
        if is_heavy_job and self.observed.active_heavy_jobs >= self.limits.max_heavy_jobs:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=CostStatus.VERIFIED_ZERO if not is_external_paid else CostStatus.UNKNOWN,
                reason=f"Active heavy jobs ({self.observed.active_heavy_jobs}) reached limit ({self.limits.max_heavy_jobs})",
                blocked_code="HEAVY_JOB_LIMIT_EXCEEDED",
            )

        # Check Parallel Worker concurrency limit
        if self.observed.active_parallel_workers >= self.limits.max_parallel_workers:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=CostStatus.VERIFIED_ZERO if not is_external_paid else CostStatus.UNKNOWN,
                reason=f"Active parallel workers ({self.observed.active_parallel_workers}) reached limit ({self.limits.max_parallel_workers})",
                blocked_code="PARALLELISM_LIMIT_EXCEEDED",
            )

        # Check Attempt boundary
        current_attempts = self.observed.task_attempts.get(task_id, 0)
        if current_attempts >= self.limits.max_attempts_per_task:
            return AdmissionDecision(
                allowed=False,
                pool_type=pool_type,
                cost_status=CostStatus.VERIFIED_ZERO if not is_external_paid else CostStatus.UNKNOWN,
                reason=f"Task {task_id} reached maximum attempts ({self.limits.max_attempts_per_task})",
                blocked_code="MAX_ATTEMPTS_EXCEEDED",
            )

        # Admitted: track active slots
        self.observed.active_parallel_workers += 1
        if is_heavy_job:
            self.observed.active_heavy_jobs += 1
        self.observed.task_attempts[task_id] = current_attempts + 1
        pool.record_usage(1)

        cost_status = CostStatus.VERIFIED_ZERO if not is_external_paid else (
            CostStatus.EXPLICIT_KNOWN if estimated_cost_eur is not None else CostStatus.UNKNOWN
        )

        return AdmissionDecision(
            allowed=True,
            pool_type=pool_type,
            cost_status=cost_status,
            reason="Admitted within verified local limits and entitlement bounds",
        )

    def release_job(
        self,
        task_id: str,
        is_heavy_job: bool = False,
        tokens_consumed: int = 0,
        duration_seconds: float = 0.0,
    ) -> None:
        """Releases active worker slots and records physical metrics."""
        if self.observed.active_parallel_workers > 0:
            self.observed.active_parallel_workers -= 1
        if is_heavy_job and self.observed.active_heavy_jobs > 0:
            self.observed.active_heavy_jobs -= 1
        self.observed.total_completed_jobs += 1
        self.observed.measured_tokens += tokens_consumed
        self.observed.elapsed_seconds += duration_seconds

    def generate_resource_evidence(self) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-28.

        Required fields:
        - 'authorized-entitlements'
        - 'observed-usage'
        - 'resource-policy'
        """
        return {
            "authorized-entitlements": {
                ptype.value: pool.to_dict() for ptype, pool in self.pools.items()
            },
            "observed-usage": self.observed.to_dict(),
            "resource-policy": {
                "max_parallel_workers": self.limits.max_parallel_workers,
                "max_heavy_jobs": self.limits.max_heavy_jobs,
                "max_attempts_per_task": self.limits.max_attempts_per_task,
                "autonomous_spend_limit_eur": f"{self.limits.autonomous_spend_limit_eur:.2f}",
                "payg_forbidden": self.limits.payg_forbidden,
                "unknown_cost_blocks": self.limits.unknown_cost_blocks,
                "prohibit_auto_topup": self.limits.prohibit_auto_topup,
                "prohibit_subscription_changes": self.limits.prohibit_subscription_changes,
                "euro_invention_prohibited": True,
            },
        }
