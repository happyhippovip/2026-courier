"""Tests for CP-28 / CQ-28 / GB-RESOURCE-01: Resource Capacity Limiter & Local Execution Policy.

Verifies:
1. Distinct entitlement pools for CHAT, API, and CI capacity.
2. Missing quota / spend data remains strictly UNKNOWN (no Euro invention).
3. PAYG and unknown external costs are blocked (AUTONOMOUS_SPEND_LIMIT_EUR = 0.00).
4. Verifiable local limits: HEAVY_JOB_LIMIT = 1, bounded parallel workers (max=2), slot release.
5. Max attempt limit per task (fails closed after 3 attempts).
6. Evidence generated with ['authorized-entitlements', 'observed-usage', 'resource-policy'].
"""

import pytest

from courier_core.resource_capacity_limiter import (
    AdmissionDecision,
    CapacityPoolType,
    CostStatus,
    EntitlementPool,
    LocalResourceLimits,
    QuotaStatus,
    ResourceCapacityLimiter,
)


def test_distinct_entitlement_pools_chat_api_ci():
    """Separate entitlement pools for CHAT, API, and CI do not cross-contaminate."""
    limiter = ResourceCapacityLimiter()

    # Configure API pool with fixed quota of 2
    limiter.pools[CapacityPoolType.API].total_entitlement_units = 2
    limiter.pools[CapacityPoolType.API].quota_status = QuotaStatus.AVAILABLE

    # Consume API quota
    d1 = limiter.check_dispatch_admission("api-1", CapacityPoolType.API)
    assert d1.allowed is True
    d2 = limiter.check_dispatch_admission("api-2", CapacityPoolType.API)
    assert d2.allowed is True
    d3 = limiter.check_dispatch_admission("api-3", CapacityPoolType.API)
    assert d3.allowed is False
    assert d3.blocked_code == "QUOTA_EXHAUSTED"

    # CHAT and CI pools remain unexhausted
    limiter.release_job("api-1")
    limiter.release_job("api-2")

    d_chat = limiter.check_dispatch_admission("chat-1", CapacityPoolType.CHAT)
    assert d_chat.allowed is True
    assert d_chat.pool_type == CapacityPoolType.CHAT

    d_ci = limiter.check_dispatch_admission("ci-1", CapacityPoolType.CI)
    assert d_ci.allowed is True
    assert d_ci.pool_type == CapacityPoolType.CI


def test_missing_quota_and_cost_remains_strictly_unknown():
    """Unmeasured quota and spend must be documented as UNKNOWN without Euro invention."""
    pool = EntitlementPool(pool_type=CapacityPoolType.API)
    assert pool.quota_status == QuotaStatus.UNKNOWN
    assert pool.cost_status == CostStatus.UNKNOWN
    assert pool.spend_eur is None

    pdict = pool.to_dict()
    assert pdict["total_entitlement_units"] == "UNKNOWN"
    assert pdict["spend_eur"] == "UNKNOWN"
    assert pdict["cost_status"] == "UNKNOWN"


def test_payg_and_unknown_cost_block_execution():
    """PAYG and unknown external costs are blocked without human gate or Euro invention."""
    limiter = ResourceCapacityLimiter()

    # PAYG attempt is strictly blocked
    d_payg = limiter.check_dispatch_admission(
        "task-payg",
        CapacityPoolType.API,
        is_payg=True,
    )
    assert d_payg.allowed is False
    assert d_payg.blocked_code == "PAYG_FORBIDDEN"

    # External paid task with missing (None) cost blocks as UNKNOWN_COST
    d_unknown = limiter.check_dispatch_admission(
        "task-ext",
        CapacityPoolType.API,
        is_external_paid=True,
        estimated_cost_eur=None,
    )
    assert d_unknown.allowed is False
    assert d_unknown.blocked_code == "UNKNOWN_COST_BLOCKED"
    assert d_unknown.cost_status == CostStatus.UNKNOWN

    # External paid task with cost > 0.00 EUR is blocked by autonomous spend limit
    d_cost = limiter.check_dispatch_admission(
        "task-paid",
        CapacityPoolType.API,
        is_external_paid=True,
        estimated_cost_eur=0.50,
    )
    assert d_cost.allowed is False
    assert d_cost.blocked_code == "SPEND_LIMIT_EXCEEDED"


def test_verifiable_local_concurrency_and_heavy_job_limits():
    """Local limits enforce HEAVY_JOB_LIMIT = 1 and max parallel workers = 2."""
    limiter = ResourceCapacityLimiter(
        limits=LocalResourceLimits(max_parallel_workers=2, max_heavy_jobs=1)
    )

    # Dispatch heavy job 1
    d1 = limiter.check_dispatch_admission("heavy-1", CapacityPoolType.CI, is_heavy_job=True)
    assert d1.allowed is True
    assert limiter.observed.active_heavy_jobs == 1
    assert limiter.observed.active_parallel_workers == 1

    # Second heavy job blocked
    d2 = limiter.check_dispatch_admission("heavy-2", CapacityPoolType.CI, is_heavy_job=True)
    assert d2.allowed is False
    assert d2.blocked_code == "HEAVY_JOB_LIMIT_EXCEEDED"

    # Light job can fill the second worker slot
    d3 = limiter.check_dispatch_admission("light-1", CapacityPoolType.CI, is_heavy_job=False)
    assert d3.allowed is True
    assert limiter.observed.active_parallel_workers == 2

    # Third job blocked by concurrency limit
    d4 = limiter.check_dispatch_admission("light-2", CapacityPoolType.CI, is_heavy_job=False)
    assert d4.allowed is False
    assert d4.blocked_code == "PARALLELISM_LIMIT_EXCEEDED"

    # Release heavy job: allows another heavy job
    limiter.release_job("heavy-1", is_heavy_job=True, tokens_consumed=1500, duration_seconds=12.5)
    assert limiter.observed.active_heavy_jobs == 0
    assert limiter.observed.active_parallel_workers == 1
    assert limiter.observed.measured_tokens == 1500
    assert limiter.observed.total_completed_jobs == 1

    d5 = limiter.check_dispatch_admission("heavy-2", CapacityPoolType.CI, is_heavy_job=True)
    assert d5.allowed is True


def test_max_attempt_boundary_per_task():
    """Fails closed once a task exceeds the max attempt limit (default: 3)."""
    limiter = ResourceCapacityLimiter(
        limits=LocalResourceLimits(max_attempts_per_task=3)
    )

    for i in range(1, 4):
        decision = limiter.check_dispatch_admission("flaky-task", CapacityPoolType.CI)
        assert decision.allowed is True
        limiter.release_job("flaky-task")

    # 4th attempt is blocked
    d4 = limiter.check_dispatch_admission("flaky-task", CapacityPoolType.CI)
    assert d4.allowed is False
    assert d4.blocked_code == "MAX_ATTEMPTS_EXCEEDED"


def test_evidence_generation():
    """Generates required evidence with authorized-entitlements, observed-usage, and resource-policy."""
    limiter = ResourceCapacityLimiter()
    limiter.check_dispatch_admission("test-task", CapacityPoolType.CHAT)
    limiter.release_job("test-task", tokens_consumed=350, duration_seconds=1.2)

    evidence = limiter.generate_resource_evidence()
    required_keys = ["authorized-entitlements", "observed-usage", "resource-policy"]
    for key in required_keys:
        assert key in evidence

    assert "CHAT" in evidence["authorized-entitlements"]
    assert "API" in evidence["authorized-entitlements"]
    assert "CI" in evidence["authorized-entitlements"]
    assert evidence["resource-policy"]["euro_invention_prohibited"] is True
    assert evidence["resource-policy"]["autonomous_spend_limit_eur"] == "0.00"
    assert evidence["observed-usage"]["total_completed_jobs"] == 1
    assert evidence["observed-usage"]["measured_tokens"] == 350
